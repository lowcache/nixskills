# Maintainability review (`/nix review [path]`)

Review for structure, not correctness — `/code-review` hunts bugs. Be ambitious: the best
finding removes a layer, branch, or file outright. Rearranging the same complexity is not a win.

## Scope

Default: branch diff plus working tree (`git diff main...HEAD`, `git diff`). A path argument
narrows it. Read whole touched files; judge the diff in context.

## Checks

1. **File size.** Flag any `.nix` file the change pushes past 1000 lines, or grows while already
   past it. Propose a split along an existing seam (`foo/default.nix` + submodules), not a new abstraction.
2. **Delete first.** Options nobody sets, `mkIf` on conditions true on every host, duplicated
   blocks that collapse into `map`/`genAttrs`, wrappers that only pass arguments through.
3. **Inline shell.** Scripts over ~30 lines in Nix strings → `writeShellApplication`
   (shellcheck + `runtimeInputs`) or a `.sh` file. Flag `writeShellScript(Bin)` (unchecked) and bare
   command names in systemd units relying on an implicit PATH.
4. **Conditional sprawl.** The same condition repeated across modules belongs in one module that
   owns the feature. One-off special cases inside an unrelated flow are a design problem, not a nit.
5. **Hardcoded host values.** Usernames, paths, device IDs, addresses in generic modules →
   the `username` specialArg, a module option, or the host/hardware file.
6. **Overrides.** `mkForce`/`mkOverride` without a one-line reason naming what it overrides.
7. **Impermanence.** New stateful service (`StateDirectory`, `/var/lib/*`, `~/.local/share/*`)
   without a persistence entry, or persisted paths that should be ephemeral.
8. **Inputs.** New flake input without `follows`, or without a comment explaining why not.
9. **Comments.** Comments that restate code, or narrate history whose conclusion fits one line
   (history goes to `.memory/` or the commit). Keep load-bearing "what breaks if changed" reasoning.

Flag deviations from the repo's conventions, not the conventions themselves. Skip anything
nixfmt/statix/deadnix already catch.

## Verification

Every restructuring claimed to preserve behavior needs an identical toplevel drvPath:
`scripts/nixops.py drv --save /tmp/before` → apply → `scripts/nixops.py drv --compare /tmp/before`.
If it differs, explain each difference (`nix-diff`) or drop the claim. Run `nixops.py gate` on anything applied.

## Output

Findings ranked by complexity removed. Each: `file:line`, the problem in one sentence, the
concrete restructure, estimated line delta. No edits unless asked.
