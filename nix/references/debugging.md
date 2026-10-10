# Debugging

Classify first, then narrow. Every Nix failure is one of: **parse → eval → build → activate → runtime**.
Fix at the stage that failed; don't edit runtime config to silence an eval error.

## 1. Parse
- `scripts/nixops.py parse <files…>` (`nix-instantiate --parse`) — fastest syntax check, no eval.
- Typical: missing `;` after attr, `}` vs `};`, `let … in` without `in`, string interpolation `${}` inside `''…''` needing `''${`.

## 2. Evaluation
Reproduce narrowly — evaluate the smallest attr that fails, not the whole system:
```
nix eval .#nixosConfigurations.volnix.config.<path> --show-trace
nix flake check --no-build --show-trace        # all outputs, eval only
```
Read traces **bottom-up**: the last `while evaluating …` frame in *your* files is usually the cause; the top is the symptom.

Tools:
- `nix repl` → `:lf .` → explore `nixosConfigurations.volnix.config`, `.options.<p>.definitionsWithLocations` (who set this value and where), `.options.<p>.declarations`.
- `lib.traceVal x`, `lib.traceSeq x y` (deep), `builtins.trace "msg" y` — temporary; deadnix/statix won't catch leftovers, remove before gate.
- `--debugger` + `builtins.break x` drops into a REPL at that point with local scope (`:bt`, `:env`, `:c`).
- Assertions/warnings: `nix eval --json .#nixosConfigurations.volnix.config.warnings`.

| Error | Cause → fix |
|---|---|
| `infinite recursion encountered` | `config.*` read in `imports`, in an option *declaration*, or to decide whether a module defines a value at top level (`if config.x then {…} else {…}`). Use `config = lib.mkIf …` / `mkMerge`; pass static data via `specialArgs`. `pkgs` used in `imports` is the same class. |
| `The option 'x' does not exist` | typo, renamed option, or module not imported. `options` search via mcp-nixos; check `nix flake metadata` for which nixpkgs/HM rev is locked — option may be newer than the lock. |
| `defined multiple times` / `conflicting definition values` | non-mergeable type set twice. `options.<p>.definitionsWithLocations` finds both; delete one or use `mkDefault`/`mkForce` with a reason. |
| `attribute 'x' missing` | renamed/removed package, wrong `pkgs` (overlay not applied, wrong channel), or typo. Check `nix eval .#nixosConfigurations.volnix.pkgs.<x>.meta.position`. |
| `value is a function while a set was expected` | module written as `{ … }:` imported where a set is expected, or forgot to call `callPackage`. |
| `path '/nix/store/…-source/x' does not exist` | file untracked by git → `git add`. |
| `cannot coerce a set to a string` | interpolated a derivation-less attrset; use `"${pkgs.x}/bin/x"` or `lib.getExe pkgs.x`. |
| `evaluation aborted with: … is marked as insecure/broken/unfree` | allow narrowly: `nixpkgs.config.permittedInsecurePackages` / `allowUnfreePredicate` for the specific name. Never global `allowBroken`. |

## 3. Build
```
nix build .#<attr> -L                 # stream full logs
nix log <drv-or-out-path>             # log of an earlier failure
nix build .#<attr> -L --keep-failed   # keeps /tmp/nix-build-* for inspection
nix develop .#<pkg>                   # enter build env; run phases: unpackPhase; cd "$sourceRoot"; configurePhase; buildPhase
```
- `hash mismatch` → use the `got:` hash. Upstream tag re-pushed is the other cause — say so rather than silently updating.
- Works locally, fails in sandbox → missing `nativeBuildInputs`/network access in build; never disable the sandbox to "fix" it.
- Cache miss rebuilding the world → overlay touching a low-level package, or `follows` mismatch giving a second nixpkgs. `nix path-info --store https://cache.nixos.org <out>` tells you whether it should be cached.
- Closure bloat / unexpected dependency: `nix why-depends <toplevel> <path>`, `nix path-info -rsSh <path> | sort -k2 -h | tail`.

## 4. Activation (`switch`, `dry-activate`)
- `make dry-activate` first: lists units that would restart/stop — catch display-manager/networkd restarts before they kill the session.
- Failed units after switch: `systemctl --failed`, `journalctl -b -u <unit> -e`, `systemctl --user --failed` for HM.
- `make switch-detached` when the switch may restart greetd or the session.
- HM activation conflicts: "existing file is in the way" → `home-manager.backupFileExtension`.
- Impermanence boot failures: bind target missing on `/persist`; sops can't decrypt because key path isn't the persisted one.

## 5. Runtime
- Service won't start: `systemctl cat <unit>` — the *generated* unit is the truth, not the Nix you wrote. Check `ExecStart` store paths and PATH (bare command names fail; use `lib.getExe`).
- File/state lost after reboot → impermanence: persist it (see `impermanence.md`).
- Config file contents: `readlink -f /etc/<file>` → inspect the store path.

## Recovery
- Previous generation at boot menu, or `sudo nixos-rebuild switch --rollback` (or `/nix/var/nix/profiles/system-<N>-link/bin/switch-to-configuration switch`).
- Bisect a regression from an input update: `git log -p flake.lock`; check out the old lock for one input at a time (`nix flake update <input> --override-input <input> <old-ref>` or revert the lock hunk), build, compare.
- Bisect a config change: `git bisect run scripts/nixops.py build` (exit code is the verdict).
