# Options, types, packages

## Lookup order (never guess)
1. `mcp-nixos` — NixOS/home-manager/darwin options and packages, version-aware.
2. Evaluated value in *this* config: `scripts/nixops.py opt services.greetd.settings` (`--hm <user>` for HM).
3. Declaration/type/default: `nix repl` → `:lf .` → `nixosConfigurations.volnix.options.<path>.{type.description,default,declarations}`.
4. Package attr in the locked nixpkgs: `nix eval --raw .#nixosConfigurations.volnix.pkgs.<attr>.version`, `nix search nixpkgs <term>` (unlocked — confirm against the lock).

## Idiom
- Group siblings: `services.greetd = { enable = true; settings.default_session = { … }; };`.
- Types: strings vs paths (`./x` copies to store; `"/abs"` doesn't), `listOf str`, `int`, `bool`; `lib.types.submodule` for structured options.
- Conditionals: `lib.mkIf cfg.enable { … }` inside `config`; `lib.mkMerge` for multiple conditional blocks; `lib.optionals`/`optionalAttrs` for small pieces.
- Priorities: `mkDefault` (1000) in shared modules so hosts override; `mkForce` (50) only with a one-line comment naming what it overrides.
- Custom options: `options.<ns>.<x> = lib.mkOption { type; default; description; };` + `config = lib.mkIf …`. Read `config` only inside `config`, never in `imports` or option declarations (infinite recursion).

## nix-ld
- `programs.nix-ld.enable = true; programs.nix-ld.libraries = with pkgs; [ … ];` — list only libs the binary actually needs (`ldd <bin>` shows `not found` entries; map each to its package).

## Formatting & lint
- `nix fmt` / `make fmt` (nixfmt RFC 166). Formatting failures in the gate are blocking.
- `statix check` (anti-patterns; `statix fix` for safe autofixes), `deadnix --fail` (unused bindings/args).
