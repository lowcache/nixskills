# Best practices

Apply when writing or reviewing any module. Repo conventions win where they differ.

## Modules
- One feature per module, owning its option, its condition, its persistence entry, and its firewall rule. Hosts toggle features; they don't contain them.
- Feature modules expose `options.<ns>.<feature>.enable = lib.mkEnableOption "…";` and wrap everything in `config = lib.mkIf cfg.enable { … };`.
- Shared modules set `mkDefault`; hosts set plain values; `mkForce` is rare and commented.
- No `with pkgs;` at module scope (shadowing, hides origins); fine in short lists: `environment.systemPackages = with pkgs; [ … ];`.
- No `rec { }` attrsets in modules; use `let … in`.
- `lib.getExe pkgs.x` / `lib.getExe' pkgs.x "bin"` instead of `"${pkgs.x}/bin/x"`.
- Paths: `./relative` for repo files (copied to store, pure); absolute strings only for live-edit symlinks and runtime paths.
- No `builtins.getEnv`, `builtins.currentSystem`, `<nixpkgs>`, or `--impure` — flakes are pure; pass via `specialArgs`.
- `fetchFromGitHub`/inputs with pinned rev + hash; never `builtins.fetchGit` without rev.

## systemd services
- `ExecStart` with full store paths; `path = [ … ]` or `writeShellApplication` `runtimeInputs` for scripts.
- Hardening by default for new services: `DynamicUser`, `StateDirectory`, `ProtectSystem = "strict"`, `ProtectHome`, `PrivateTmp`, `NoNewPrivileges`, `RestrictAddressFamilies`. Check with `systemd-analyze security <unit>`.
- `StateDirectory` ⇒ persistence entry (impermanence).

## Secrets
- Never in the store: no secrets in Nix strings, `environment.etc` text, or `builtins.readFile` of a secret (world-readable `/nix/store`). Use sops-nix paths (`config.sops.secrets.<n>.path`) and `*File` options (`passwordFile`, `environmentFile`).

## Packages & overlays
- Overlays: `final: prev:`; reference `prev.x` when overriding x, `final.y` for deps. Overriding a low-level package rebuilds the world — prefer per-consumer overrides.
- Pin a single package to another nixpkgs via a second input + `follows`-free import, only with a comment why.

## Flake hygiene
- Every input `follows` nixpkgs unless commented; `nix flake metadata` should show one nixpkgs.
- Lock updates are their own commit, separate from config changes, so they bisect cleanly.

## Comments
- Explain why/what-breaks, not what. Link the upstream issue for workarounds so they can be removed later.
