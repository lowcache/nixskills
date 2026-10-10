---
name: nix-quality-review
description: Strict maintainability review of Nix configuration changes — oversized modules, inline shell, conditional sprawl, hardcoded host values, impermanence gaps. Pushes for restructurings that delete complexity, verified by an unchanged toplevel drvPath. Use for a harsh or deep quality review of a Nix repo or branch.
disable-model-invocation: true
---

# nix-quality-review

Review for structure, not correctness — `/code-review` hunts bugs. Be ambitious: the best
finding removes a layer, branch, or file outright. Rearranging the same complexity is not a win.

## Scope

Default: the branch diff plus working tree (`git diff main...HEAD`, `git diff`). A path argument
narrows it. Read whole touched files; judge the diff in context.

## Checks

1. **File size.** Flag any `.nix` file the change pushes past 1000 lines, or grows while already
   past it. Propose a split along an existing seam (`foo/default.nix` + submodules), not a new abstraction.
2. **Delete first.** Options nobody sets, `mkIf` on conditions that are always true on every host,
   duplicated blocks that collapse into `map`/`genAttrs`, wrappers that only pass arguments through.
3. **Inline shell.** Scripts over ~30 lines in Nix strings move to `writeShellApplication`
   (shellcheck + `runtimeInputs`) or a `.sh` file. Flag `writeShellScript(Bin)` (unchecked) and bare
   command names in systemd units that rely on an implicit PATH.
4. **Conditional sprawl.** The same condition repeated across modules belongs in one module that
   owns the feature. One-off special cases inside an unrelated flow are a design problem, not a nit.
5. **Hardcoded host values.** Usernames, paths, device IDs, addresses inside generic modules →
   the `username` specialArg, a module option, or the host/hardware file.
6. **Overrides.** `mkForce`/`mkOverride` without a one-line reason naming what it overrides.
7. **Impermanence.** A new stateful service (`StateDirectory`, `/var/lib/*`, `~/.local/share/*`)
   with no persistence entry, or persisted paths that should be ephemeral.
8. **Inputs.** A new flake input without `follows`, or without the comment explaining why not.
9. **Comments.** Flag comments that restate code, or narrate history whose conclusion fits in one
   line (history goes to `.memory/` or the commit). Keep load-bearing "what breaks if changed" reasoning.

Follow the repo's existing conventions (e.g. where persistence is declared); flag deviations from
them, not the conventions themselves. Skip anything formatting or statix/deadnix already catch.

## Verification

For every proposed restructuring that claims to preserve behavior, the proof is an identical
`nix eval --raw .#nixosConfigurations.<host>.config.system.build.toplevel.drvPath` before and
after. If it differs, explain each difference (`nix-diff`) or drop the claim. Run the repo's
check gates (`make check` or `.#checks`) on anything applied.

## Output

Findings ranked by how much complexity they remove. Each: `file:line`, the problem in one
sentence, the concrete restructure, and the estimated line delta. No edits unless asked.
