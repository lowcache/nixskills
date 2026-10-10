# Store, generations, caches, updates

## Disk / GC
- Declarative: `nix.gc = { automatic = true; dates = "weekly"; options = "--delete-older-than 14d"; };` and `nix.optimise.automatic = true;` (or `programs.nh.clean` if the repo uses nh — not both).
- Manual: `sudo nix-collect-garbage --delete-older-than 14d` (system profiles need root), `nix store optimise`.
- What's holding space: `nix path-info -rsSh /run/current-system | sort -k2 -h | tail`, `nix-store --gc --print-roots | grep -v /proc` (stale `result` symlinks and direnv roots are common), `nix-tree` interactive.
- Full ESP: lower `boot.loader.systemd-boot.configurationLimit` (or `boot.lanzaboote.configurationLimit` with lanzaboote), GC old generations, rebuild to rewrite entries.

## Generations
- System: `nixos-rebuild list-generations` (or `ls -l /nix/var/nix/profiles/system-*-link`); HM: `home-manager generations`.
- Compare two: `nix store diff-closures /nix/var/nix/profiles/system-{N,M}-link` or `nvd diff`.

## Caches / substituters
- `nix.settings.substituters` + `trusted-public-keys` (or `extra-` variants) — keys must match or downloads are rejected silently and everything builds locally.
- Check a path is cached: `nix path-info --store https://cache.nixos.org <out-path>`.
- Settings in effect: `nix config show | grep -E 'substituters|trusted|max-jobs|cores'`.

## Update routine
1. `nix flake update` (or one input) in its own commit.
2. `nixops.py build` → read the closure diff; check nixpkgs release notes / option renames for warnings (`config.warnings`).
3. `make dry-activate`, then switch when asked.
4. Breakage → `debugging.md` §Recovery (rollback, bisect the lock).

## Health
`nix config check` (formerly `nix doctor`), `nix store verify --all --no-trust` (slow; corruption check), `nix store repair <path>`.
