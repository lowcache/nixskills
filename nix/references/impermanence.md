# Impermanence

## Root
- `/` is tmpfs: `fileSystems."/" = { device = "none"; fsType = "tmpfs"; options = [ "defaults" "size=4G" "mode=755" ]; };`. Size against RAM; anything writing large files to `/` (build dirs, caches) must be redirected or persisted, or the host OOMs.
- `/nix` and `/persist` are real filesystems; `/persist` needs `neededForBoot = true`.

## Persistence
- System: `environment.persistence."/persist" = { directories = [ … ]; files = [ … ]; };` — `/etc/machine-id`, `/etc/ssh/ssh_host_*`, `/var/lib/nixos` (uid/gid stability), `/var/log`, `/var/lib/systemd`, service state.
- User: `home.persistence."/persist/home/<user>"` (or the NixOS-side `users.<user>` form — follow the repo's existing convention). Repos, browser profiles, `.local/share/<app>`, keyrings.
- Directory entries take `{ directory = "…"; user; group; mode; }` for non-root ownership.

## Where entries go (follow the repo)
volnixos: base system entries in `nixos/hardware-configuration.nix`; a feature module persists its own state next to the service (e.g. `backup.nix` → `/var/lib/vol-backup`); user entries in `home/persist.nix` (`home.persistence."/persist"`, paths relative to `$HOME`). Big or mmap-heavy data → `~/Storage` (symlink/redirect), not `/persist` binds and never tmpfs. Two stores, kept separate: `/persist` (machine/user state) vs `~/Storage` (bulk data, caches, tmp).

## Every new stateful service
Check for `StateDirectory`, `/var/lib/<svc>`, `/var/cache/<svc>`, `~/.local/share/<app>`, `~/.cache/<app>` (only if expensive to rebuild). Add a persistence entry or explicitly decide it's ephemeral. Conversely, flag persisted paths that are pure cache.

## Permissions
- `~/.ssh`, `~/.gnupg`: `0700`; private keys `0600`. Set `mode` on the persistence entry — bind mounts inherit the source's perms, so fix them on `/persist`.
- Never persist a parent so broadly that it exposes these (e.g. all of `$HOME`).

## Secrets
- SOPS (`sops-nix`): decrypted to `/run/secrets/*` (tmpfs), owner-scoped via `sops.secrets.<n>.{owner,mode}`. Persist only the decryption key (e.g. `/persist/var/lib/sops-nix/key.txt` or SSH host key used as age key), never decrypted output.
- `sops.age.sshKeyPaths` must point at the **persisted** path when host keys live under `/persist`, or decryption fails at early boot.

## Debug
- `findmnt -R /` — bind points; `df -h /` — tmpfs usage.
- Find unpersisted writes: `sudo find / -xdev -newer /run/booted-system -type f 2>/dev/null | grep -v -e ^/nix -e ^/persist -e ^/proc -e ^/sys` after using the system for a while.
- Bind mount failing at boot: target dir missing on `/persist` — create it (or use the module's `hideMounts`/creation options).
- Newly persisted dir that HM also populates in the same switch: HM links land on the tmpfs view and get hidden by the mount → restart `home-manager-<user>` once; verify with `ls`.
- tmpfs root filling: `sudo du -xh --max-depth=2 / 2>/dev/null | sort -h | tail` → move the culprit to `~/Storage` or persist it.
