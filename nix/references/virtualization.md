# Virtualization (microvm.nix, containers)

## Structure
- Host capability (`microvm.nixosModules.host`) separate from guests (`microvm.vms.<name>.config`). Inside a guest's `config`, `config` refers to the **guest**; capture host values in a `let` outside.
- Runners exposed as flake packages (`…config.microvm.vms.<n>.config.config.microvm.declaredRunner`) so CI builds them and `nix run .#<n>` works.
- Any guest change → build the guest runner **and** the host toplevel.

## volnixos guests
| Guest | Role | Notes |
|---|---|---|
| `net-gate` | Tor gateway (TransPort 9040, DNSPort 5353, SOCKS 9050) | vsock CID 10; does **not** restart on switch → `make gate-restart` |
| `tailscale` (pkg `tailscale-vm`) | Tailscale gateway | vsock CID 11 |
| `anon-box` | anonymity workstation | CID from `vol.anon-mode.workstation.vsockCid`; restarts on switch (unit deps re-emit `restartIfChanged`) |

## cloud-hypervisor constraints (load-bearing)
- Interfaces: only `tap`/`macvtap`; `type = "bridge"` is rejected. Bridges are built host-side (networkd enslaves taps into e.g. `br-anon`; host holds no address on it).
- vsock is a hybrid Unix-socket protocol (CONNECT/OK handshake), not kernel `AF_VSOCK` — `socat VSOCK-CONNECT` and `systemd-ssh-proxy` don't work.
- Shares have no read-only flag: make a host `bind,ro` mount and share that.
- `microvm.vsock.cid` must be set (unique, ≥3) for systemd-notify readiness.
- `X-RestartIfChanged=false` on `microvm@.service`: switching updates `/var/lib/microvms/<n>/current` but the old guest keeps running.

## Networking
- Host side: `systemd.network.networks` matching the tap name; mark VM interfaces unmanaged in NetworkManager.
- iptables `REDIRECT` targets the arriving interface's primary address — a dual-leg gateway needs listeners on both legs.
- Reverse-path filter must be loose for asymmetric paths (`networking.firewall.checkReversePath = "loose"`), or return traffic on the tap is silently dropped.
- Tor: don't hand-set `SOCKSPort` alongside the module's `client.socksListenAddress` (list merge → double bind, tor dies).
- Prove negative paths, not just "it has a Tor IP": DNS leak, IPv6 refused, WAN bind blackholed, no clearnet fallback when the gateway is down (`make anon-selftest`).

## Containers / GPU
- NVIDIA in OCI: `hardware.nvidia-container-toolkit.enable = true;` then CDI `--device nvidia.com/gpu=all`. After a driver bump, the CDI generator fails until reboot (kernel/userspace mismatch).
- Volumes: explicit host paths, minimal perms.

## Debug
- `systemctl status 'microvm@<n>'`, `journalctl -u microvm@<n> -b`; guest journal may be exported host-side (volnixos: `/persist/var/log/net-gate-journal` → `make anon-guest-logs`).
- Is the running guest the new one? Compare `readlink /var/lib/microvms/<n>/current` with the booted runner (`systemctl show -p ExecStart microvm@<n>`); if they differ, restart.
- `ip -br link`, `ip -br addr`, `networkctl status <tap>`, `ip rule`, `ip route show table <n>`, `nft list ruleset`.
