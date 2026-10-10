# Packaging & overrides

## Choose the smallest tool
| Need | Use |
|---|---|
| Change a build flag/dep | `pkgs.x.override { foo = true; }` (function args) |
| Patch, bump version, change phases | `pkgs.x.overrideAttrs (old: { … })` |
| Python/Go/Rust deps override | language-specific: `python3.override { packageOverrides = …; }`, `buildGoModule` `vendorHash`, `cargoHash` |
| New package from source | `callPackage ./pkgs/x.nix { }` + language builder |
| Prebuilt binary | `stdenv.mkDerivation` + `autoPatchelfHook` (+ `buildInputs` for libs) |
| Binary that insists on FHS | `buildFHSEnv` |
| Script | `writeShellApplication { name; runtimeInputs; text; }` |

## Patterns
```nix
pkgs.x.overrideAttrs (old: {
  version = "1.2.3";
  src = pkgs.fetchFromGitHub { owner = "…"; repo = "…"; rev = "v1.2.3"; hash = lib.fakeHash; };
  patches = (old.patches or [ ]) ++ [
    (pkgs.fetchpatch { url = "…/commit/<sha>.patch"; hash = lib.fakeHash; })
  ];
})
```
- Hash workflow: `lib.fakeHash` → build → copy `got:`. Same for `vendorHash`/`cargoHash`. `nurl <url> [rev]` generates a fetcher call with hash directly.
- Version bump of a package with a sub-hash (Go/Rust/npm): update **both** `src.hash` and the deps hash.
- Local source: `src = lib.fileset.toSource { root = ./.; fileset = lib.fileset.gitTracked ./.; };` — avoids rebuilds when unrelated files change.
- `nix-init` scaffolds a package from a URL; `nix-update <attr>` bumps version + hashes.
- `meta = { description; homepage; license; mainProgram; };` — `mainProgram` makes `lib.getExe` work.

## Where it lives
- Repo-local: `pkgs/<name>/package.nix`, exposed in `packages.<system>` and, if modules need it in `pkgs`, an overlay.
- Overrides affecting one consumer: override at the use site, not globally in an overlay (global overlay on a widely used lib = mass rebuild, no cache).

## Verify
`nix build .#<pkg> -L`, run `./result/bin/<prog> --version`; `nix path-info -Sh ./result` for size; `nix log` on failure (see `debugging.md` §Build).
