# Flakes

## Inputs
- Explicit URLs (`github:NixOS/nixpkgs/nixos-unstable`).
- `inputs.<x>.inputs.nixpkgs.follows = "nixpkgs"` on every input that takes nixpkgs; if omitted deliberately, a one-line comment says why.
- Update one input: `nix flake update <input>` (`make update-nixpkgs` in volnixos); `nix flake lock --update-input <input>` on older implementations. Update all: `nix flake update`.
- Some inputs intentionally lack `follows` (volnixos: `nix-cachyos-kernel`, so its kernel matches a binary cache). Never add `follows` to an input whose comment explains its absence; check cache impact (`nix build --dry-run` lists what would be built) before changing any `follows`.
- After any lock change: `git diff flake.lock` to confirm only intended inputs moved, then gate + build.

## Outputs (current schema)
- `nixosConfigurations.<host>`, `homeConfigurations."<user>@<host>"` (standalone HM only)
- `packages.<system>.<name>`, `packages.<system>.default` — not deprecated `defaultPackage`
- `devShells.<system>.default`, `apps.<system>.<name>`, `formatter.<system>`, `checks.<system>.<name>`
- `overlays.<name>` / `overlays.default`, `nixosModules.<name>`, `homeManagerModules.<name>`
- Validate with `nix flake show` and `nix flake check`.

## Systems
- Generic outputs: map over systems (`nixpkgs.lib.genAttrs [ "x86_64-linux" "aarch64-linux" ]`, or `flake-utils`/`flake-parts` if the repo already uses them). Don't add a framework input to save three lines.
- Host configs are inherently single-system; set `nixpkgs.hostPlatform` in the hardware file, not hardcoded in shared modules.
- Keep `hardware-configuration.nix` separate from logical profiles.

## Packaging
- `callPackage` + `stdenv.mkDerivation` / language builders (`buildGoModule`, `rustPlatform.buildRustPackage`, `buildPythonApplication`).
- Fixed-output hashes: start with `lib.fakeHash`, copy `got:` from the error.
- Scripts: `writeShellApplication` (shellcheck + `runtimeInputs`), not `writeShellScript(Bin)`.
- Expose via overlay only when the package must be visible inside `pkgs` for other modules; otherwise `packages.<system>`.

## Debugging
- `nix flake metadata` — locked revs; `nix flake check --show-trace`.
- `nix eval .#<attr> --show-trace`; `nix repl` → `:lf .`.
- `nix why-depends .#nixosConfigurations.volnix.config.system.build.toplevel nixpkgs#<pkg>` — why something is in the closure.
- `nix store diff-closures <old> <new>` — what an update changed.
