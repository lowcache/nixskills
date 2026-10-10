# volnixos profile

Load whenever the working tree is volnixos (`~/.nix-config`, `/persist/home/lowcache/.nix-config`, or a clone with `nixosConfigurations.volnix`). These facts override generic advice in other references. Re-verify against `.model/CLAUDE.md` and `.memory/` — they are the source of truth and move faster than this file.

## Before work
Read `.model/CLAUDE.md` and `.memory/{state,decisions,mistakes,todo}.md`. `mistakes.md` is the repo's debugging history — search it for the symptom before diagnosing (`grep -n -i '<keyword>' .memory/mistakes.md`). Memory writes go only to `.memory/inbox/` (dated notes); `memd` owns curation and memory commits.

## Layout
| Path | Owns |
|---|---|
| `flake.nix` | inputs, `nixosConfigurations.volnix`, `nixOnDroidConfigurations.default`, `packages.x86_64-linux.{net-gate,tailscale-vm}`, `templates`, `formatter` (nixfmt-tree), `checks.{formatting,lint}` |
| `nixos/modules/*.nix` | one concern per file; feature options under the `vol.*` namespace (`vol.anon-mode`, `vol.ai-stack`, `vol.audio`, `vol.backup`, `vol.persistLuks`) |
| `nixos/hosts/volnix.nix` | what THIS machine is: hostname, `vol.*` switches, host values. `system.stateVersion = "24.11"` — never bump |
| `nixos/hardware/asus-ryzen-nvidia/` | kernel (CachyOS), GPU, keyboard RGB |
| `nixos/hardware-configuration.nix` | filesystems (tmpfs `/`, `/persist` `neededForBoot`), base `environment.persistence."/persist"` (`hideMounts = true`) |
| `nixos/vms.nix` | MicroVM guests `net-gate`, `tailscale`, `anon-box` (cloud-hypervisor) |
| `nixos/overlays/` | overlays wired in `flake.nix`; each has a revert condition in its header |
| `home/` | Home Manager (NixOS-module mode, `useGlobalPkgs`); `home/persist.nix` = user persistence + `~/Storage` redirections |
| `dots/` | git **subtree**; live dotfiles reached via `mkOutOfStoreSymlink`. Use `make dots-*` targets. Excluded from statix (`statix.toml`) |
| `droid/` | Nix-on-Droid (aarch64), separate `nixpkgs-droid` (25.11, glibc 2.40) — never substitute workstation nixpkgs |
| `templates/` | `nix flake init -t ~/.nix-config#<lang>`; their `.nix` files must pass this repo's gates (no unused lambda args) |
| `docs/wikifixins/` | markdown notes for wiki-affecting changes |

`specialArgs = { inherit inputs username; }`; HM gets `extraSpecialArgs = { inherit inputs; }`.

## Stack facts that change answers
- Desktop: **niri** (sole WM) + **Noctalia v5**; Hyprland/UWSM/quickshell were removed. Noctalia is spawned by niri, not a systemd unit. XWayland via `xwayland-satellite`.
- Nix implementation: **Lix** from nixpkgs (`nix.package = pkgs.lixPackageSets.stable.lix`, `nixos/modules/nix-settings.nix`). CLI flags/subcommands may differ slightly from CppNix; check `nix --version`.
- Boot: **lanzaboote** (Secure Boot) replaces systemd-boot (`boot.nix` disables systemd-boot). Kernel: `pkgs.cachyosKernels.linuxPackages-cachyos-latest` via `nix-cachyos-kernel.overlays.pinned`; that input deliberately has **no** `follows` (cache hits from the lantian attic depend on it).
- `/persist` is LUKS2 (`vol.persistLuks`).
- GPU: AMD iGPU + NVIDIA RTX 4050; `nvidiaPackages.stable` from `config.boot.kernelPackages`. Ollama: `pkgs.ollama-cuda`, keep `OLLAMA_KEEP_ALIVE=5m`; never add processes that hold `/dev/nvidia*` (blocks RTD3 power-off).
- Session bus: `services.dbus.implementation` forced to `"dbus"` — portal pidfd bug (mistakes #10). Don't "clean up" that `mkForce`.
- tmpfs root is ~4G: build temp goes to `/nix/tmp` (daemon) and `~/Storage/tmp` (user, `REBUILD_TMPDIR`). Large/mmap state goes to `~/Storage`, not tmpfs.

## Operations (Makefile — always prefer these)
| Need | Target |
|---|---|
| Gate | `make check` (= `nix flake check` + `deadnix --fail .` + `statix check .`) |
| Format | `make fmt` (`nix fmt` + `statix fix .`) |
| Build / inspect / temp-activate / next-boot | `make build` / `make dry-activate` / `make test` / `make boot` |
| Apply | `make switch`; `make switch-detached` when greetd/dbus/display/session/glibc may restart (mistakes #1). Only when the user asks |
| Guest change | `make gate-restart` after any `microvm.vms.net-gate.config` change — `microvm@` has `X-RestartIfChanged=false`, switch leaves the OLD guest running. `anon-box` does restart on switch; `make anon-box-rebuild` forces it |
| Anon mode | `make anon-status` (read-only), `anon-arm`, `anon-selftest` (negative-path leak tests), `anon-logs`, `anon-guest-logs` |
| Secrets | `make sops-edit` (host), `sops-edit-vm` (guest-readable), `sops-rekey`, `sops-view[-vm]` |
| Droid | `make droid-check`, `make droid-plan` (laptop eval only; `--impure` required) |
| Inputs | `make update`, `make update-nixpkgs` |
| GC | `make trash` |
| Git | `make comm`, `make push`, `make git`; `make ci` watches CI. Don't push unless authorized |

## Secrets
Split by trust boundary: `nixos/host-secrets.yaml` (admin + host key) vs `nixos/vm-secrets.yaml` (admin + net-gate key — readable by the guest). Never create a new secrets file or move secrets across files; `sops <missing-path>` silently creates a decoy.

## CI (`.github/workflows/build.yml`)
On push to `main` (non-doc paths): builds `checks.formatting` + `checks.lint` first, asserts the CachyOS kernel is a cache hit (`nix build --dry-run` grep), builds toplevel, then MicroVM runners; pushes to `cachix:volnixos`. Substituters there must stay in sync with `nix-settings.nix`. A gate failure in CI after an hour is the cost of skipping `make check` locally.

## Known traps (from mistakes.md)
- Lix pinning: never change without `nix eval …toplevel.drvPath` first; "pinned in lock" ≠ "in cache".
- Newly persisted dir that HM also populates: first activation's links are hidden under the bind mount → restart `home-manager-lowcache.service` once, verify with `ls`.
- Shell inside Nix strings (`home/shell.nix`, `home/common/fish.nix`) isn't checked by the gate — exercise each function; `\\` escaping.
- NVIDIA userspace/kernel mismatch after switch (`NVML: Driver/library version mismatch`) → needs reboot, not a config fix.
- `asus-shutdown.service` can hang activation (SendSIGKILL=no).
- Never derive kill targets from `pgrep -f` patterns a harness process can match.
- Never track agent state dirs (`.gemini`, `.claude`) in git — the repo is public.

## Commits
First-person messages describing the user's change; no model/agent branding. Stage everything touched (`git add`) and commit with `--no-gpg-sign` (avoids pinentry hangs headless). `gh` + `$GH_TOKEN` is the fallback when `git` needs an interactive passphrase. Update `.model/CLAUDE.md` when a major subsystem changes (that file is required to stay current).
