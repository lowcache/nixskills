# Design & paradigms

For new subsystems, greenfield flakes/hosts, and "is there a better way" questions. Reason from the problem, not from what the current repo happens to do.

## Method
1. **State the problem and constraints** (hosts, architectures, who edits it, failure cost, offline/cache needs, secrets boundary).
2. **List 2–3 real options**, including "keep current approach". Check each is maintained and compatible with the locked nixpkgs (mcp-nixos / upstream README) — don't recommend from memory alone.
3. **Compare on**: lines/complexity removed, eval/build cost, cache hits, failure modes, reversibility, learning cost, migration effort.
4. **Recommend one**, with a migration path that keeps the system building at every step (incremental, drvPath-checked where behavior should not change).
5. In an existing repo: design greenfield-optimal first, then adapt to the repo's operations interface (Makefile, CI, memory) — adapting the *integration*, not compromising the design, unless the cost is stated and accepted.

## Option map (verify current status before recommending)
| Concern | Options | Reach for the alternative when |
|---|---|---|
| Flake structure | plain `outputs` · `flake-parts` | many per-system outputs, reusable flake modules, or several hosts sharing parts |
| Formatting/lint wiring | hand-rolled `checks` · `treefmt-nix` · `git-hooks.nix` (pre-commit) | multiple languages to format; catching gate failures before commit/CI |
| Disks | hand-written `fileSystems` · `disko` | reinstalling/provisioning machines declaratively; LUKS/btrfs layouts |
| Impermanence root | tmpfs `/` · btrfs/zfs rollback snapshot | RAM pressure from tmpfs; want "diff since boot" to find unpersisted state |
| Secrets | sops-nix · agenix | agenix: simpler age-only, one-file-per-secret; sops: structured files, multiple key types, templates |
| Deploy / multi-host | `nixos-rebuild --target-host` · deploy-rs · colmena · nixos-anywhere (install) | more than one machine, rollback on failed activation, remote install |
| Rebuild UX | `nixos-rebuild` · `nh` | readable diffs/trees during switch, built-in clean |
| Variants of one host | separate configs · `specialisation.<name>` | same machine, alternate boot modes (e.g. GPU on/off, minimal) |
| Tests | build-only · `runNixOSTest` · `nix-unit` / `lib.debug.runTests` | behavior worth guarding (network isolation, services); pure lib functions |
| Dev envs | `mkShell` · devenv | services (DBs) and process management in the dev shell |
| Images | — · `nixos-generators` / `system.build.images` | ISO/VM/cloud images from the same config |
| Nix implementation | CppNix · Lix | feature/CLI differences matter; check both before relying on a subcommand |

## Signals a paradigm shift is due
- The same workaround appears in 3+ places, or a module needs long comments to explain how not to break it.
- A failure mode recurs in memory/mistakes logs despite prevention rules — the rule is compensating for a design.
- Gate/CI cost grows faster than the config (e.g. an hour to find a lint error).
- Manual steps after switch (restart X, re-run Y) that the system could own.

## Guardrails
- New paradigm ≠ big-bang rewrite. Land it beside the old one, migrate piece by piece, delete the old path last.
- Don't add a framework input to save a few lines; the payoff must exceed the new dependency's update/break surface.
- Record the decision (problem, options, choice, why) where the repo keeps decisions (`.memory/inbox/` in memd repos, else commit message/README).
