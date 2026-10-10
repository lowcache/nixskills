# System: boot, kernel, hardware, users, networking

## Never
- Change `system.stateVersion` / `home.stateVersion` to "upgrade" — it pins stateful defaults (DB formats, paths). Change only with the release notes' migration steps.
- Edit `hardware-configuration.nix` for logic — regenerate with `nixos-generate-config --show-hardware-config` and keep logic elsewhere.

## Boot
- systemd-boot: `boot.loader.systemd-boot.{enable,configurationLimit = 10}` (limit protects the ESP from filling; full ESP = failed switch).
- lanzaboote (Secure Boot; volnixos): `boot.lanzaboote.{enable,pkiBundle}` with `systemd-boot.enable = lib.mkForce false`. Check `sbctl status` / `sbctl verify` after kernel or bootloader changes; a missing PKI bundle on `/persist` = unbootable signed entries.
- `boot.initrd.systemd.enable = true` for modern initrd (needed by some impermanence/rollback setups).
- Kernel: `boot.kernelPackages = pkgs.linuxPackages_latest` (or a pinned series); out-of-tree modules (nvidia, zfs) must come from the same `config.boot.kernelPackages`, never a different `linuxPackages`.
- Params: `boot.kernelParams`; modules: `boot.kernelModules`, `boot.initrd.availableKernelModules`, `boot.blacklistedKernelModules`.

## GPU (NVIDIA)
- `hardware.graphics.enable = true;` (renamed from `hardware.opengl` in 24.11 — check the lock's release), `services.xserver.videoDrivers = [ "nvidia" ];`, `hardware.nvidia.open` set explicitly (required on recent releases), `hardware.nvidia.modesetting.enable = true` for Wayland.
- Prime: `hardware.nvidia.prime = { offload.enable = true; offload.enableOffloadCmd = true; intelBusId/amdgpuBusId; nvidiaBusId; };` — bus IDs from `lspci`, converted to `PCI:b:d:f` decimal.
- Debug: `nvidia-smi`, `journalctl -b -k | grep -i nvrm`, `cat /proc/driver/nvidia/version`.

## Disks
- Declarative partitioning: `disko` if the repo uses it — then `fileSystems` come from disko; don't duplicate.
- Mount options in Nix, not `/etc/fstab` (generated).

## Users
- `users.mutableUsers = false` with `hashedPasswordFile` (sops, `neededForUsers`) for reproducible users — required in practice with impermanence (`/etc/shadow` is regenerated).
- `/var/lib/nixos` must be persisted so uid/gid allocation is stable.

## Networking
- Pick one manager per interface: NetworkManager for user-facing Wi-Fi, systemd-networkd for VM/TAP/bridges, with NM `unmanaged` for those.
- Firewall: `networking.firewall.{allowedTCPPorts,interfaces.<if>.allowedTCPPorts}` — prefer per-interface. Custom rules via `networking.nftables` if the repo uses nftables; don't mix iptables `extraCommands`.
- Tailscale: `services.tailscale.{enable,authKeyFile,useRoutingFeatures}`; `networking.firewall.trustedInterfaces = [ "tailscale0" ]` only if intended.

## Debug
`journalctl -b -p err`, `systemctl --failed`, `bootctl status`, `nixos-version --json`, `ls /nix/var/nix/profiles/system-*-link`.
