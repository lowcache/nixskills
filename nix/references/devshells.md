# Dev shells & direnv

## devShells
```nix
devShells.${system}.default = pkgs.mkShell {
  packages = [ pkgs.nixfmt-rfc-style pkgs.statix pkgs.deadnix ];
  inputsFrom = [ self.packages.${system}.foo ];   # reuse a package's build deps
  shellHook = ''export FOO=bar'';
};
```
- `packages` for tools; `inputsFrom` instead of copying a package's `buildInputs`.
- Language toolchains: pin via nixpkgs (`python3.withPackages (ps: [ … ])`, `rustc`/`cargo` or a rust overlay if the repo has one).
- Native libs for pip/npm wheels: `LD_LIBRARY_PATH = lib.makeLibraryPath [ … ];` in the shell, or nix-ld system-wide.
- `nix develop` (flake), `nix shell nixpkgs#x` (ad-hoc tool), `nix run nixpkgs#x -- args` (one-shot).

## direnv
- Enable: `programs.direnv = { enable = true; nix-direnv.enable = true; };` (HM or NixOS) — nix-direnv caches the env and adds a GC root so shells survive `nix-collect-garbage`.
- `.envrc`: `use flake` (or `use flake .#name`). `direnv allow`.
- Stale env after editing flake: `direnv reload`; nix-direnv re-evaluates on `flake.nix`/`flake.lock` changes automatically.
- With impermanence: persist `~/.local/share/direnv` (allow-list) or every repo needs `direnv allow` after reboot.

## Templates
`templates.<name> = { path = ./templates/<name>; description = "…"; };` → `nix flake init -t <flake>#<name>`.
