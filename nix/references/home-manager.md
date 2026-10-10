# Home Manager

## Mode
Determine integration first: NixOS module (`home-manager.users.<user>`, applied by system switch; volnixos uses this with `useGlobalPkgs = true`, `useUserPackages = true`) vs standalone (`home-manager switch`). Never mix. With `useGlobalPkgs`, `nixpkgs.*` settings inside HM are ignored — overlays/unfree go on the NixOS side.

## Layout
- One concern per file (`shell.nix`, `pkgs.nix`, `persist.nix`, `scripts.nix`), wired through `imports`.
- Username/home from `config.home.username` / `config.home.homeDirectory` (or the `username` specialArg); never hardcode `/home/<user>` in shared modules.

## Dotfiles
- Live-editable configs: `xdg.configFile."<app>".source = config.lib.file.mkOutOfStoreSymlink "${config.home.homeDirectory}/.nix-config/dots/<app>";` — edits apply without rebuild. The argument must be an absolute **string**; a path literal (`./dots/x`) copies into the store and silently becomes read-only.
- volnixos convention: dotfiles live in the `dots/` subtree and are out-of-store symlinked. Don't replace with generated `programs.<app>.settings` unless asked.
- Don't manage the same file both via `programs.<app>` and a symlink (collision → "would be clobbered").
- `force = true` on a `home.file` entry overwrites an existing non-HM file; use it deliberately, not as a collision fix.

## Desktop (Wayland)
- volnixos: **niri** (config `dots/niri/config.kdl`, KDL) + **Noctalia v5** shell (via `inputs.noctalia.homeModules.default`, `home/shell.nix`). Noctalia and other session programs start from niri `spawn-at-startup`, not systemd user units — restart them with `niri msg action spawn -- <cmd>` after killing.
- Validate niri config after edits: `niri validate` (catches KDL errors before the next login).
- Portals: one `xdg.portal` definition (NixOS side) with an explicit `config.common.default`. If file pickers fail with `AccessDenied … /proc/<pid>/root`, it's the dbus-broker pidfd bug, not the portal backend — see volnixos.md.
- Theme: one palette source feeds kitty, starship, Noctalia (volnixos: Noctalia emits M3 roles; starship consumes role names).

## Shell (fish)
- `programs.fish.{functions,shellAbbrs,shellAliases,interactiveShellInit}`. Greeting/banners in `interactiveShellInit`, guarded by `status is-interactive` and `command -v <tool>`.
- Shell code in Nix strings is not checked by any gate. For functions: write a fish file under `dots/` or validate with `fish --no-execute <file>`; for bash, use `writeShellApplication` (shellcheck runs at build).
- Escaping: in `''…''` strings, `''${` emits a literal `${`; `\\` survives as `\` in `"…"` strings.

## Debug
- Activation log: `journalctl -u home-manager-<user> -b`; re-run: `sudo systemctl restart home-manager-<user>`.
- What HM generated: `ls -l ~/.local/state/home-manager/gcroots/current-home/home-files/` or `readlink -f ~/.config/<file>`.
- "Existing file … would be clobbered": set `home-manager.backupFileExtension`, or remove the stray file after checking it isn't state.
- With impermanence: HM symlinks are recreated every boot; persist only state. Newly persisted dir + HM links in the same switch → links hidden under the bind mount until HM re-runs.
- `home-manager generations` (standalone) / system generations (module mode).
