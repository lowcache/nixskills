---
name: nix
description: Single entry point for all Nix work — authoring, debugging, testing, reviewing, and applying NixOS, flake, home-manager, impermanence, MicroVM, packaging, secrets (sops-nix), boot/kernel/GPU, dev shell, and store-maintenance changes. Trigger on any creation, edit, or review of `.nix` files or `flake.lock`; NixOS/home-manager option or package lookups; evaluation, build, activation, or boot failures; and any work in the volnixos / volnix configuration (~/.nix-config) — niri/Noctalia desktop, net-gate/tailscale/anon-box MicroVMs, tmpfs root + /persist, `make check`/`make switch` workflows. `/nix review [path]` runs a strict maintainability review.
argument-hint: "[review|debug|test|<topic>] [path]"
---

# Nix

One skill, routed by task. Read this file fully, then load only the references the task touches.

## Routing

| Task touches | Load |
|---|---|
| **the volnixos repo** (only there; skip for any other repo) | `references/volnixos.md` |
| new subsystem, greenfield flake/host, architecture choice, "is there a better way" | `references/design.md` |
| anything failing: parse/eval/build/activation/boot/runtime | `references/debugging.md` |
| verifying a change, writing tests, "is it safe to switch" | `references/testing.md` |
| writing or restructuring modules (any non-trivial edit) | `references/practices.md` |
| `/nix review`, maintainability/quality audit, post-major-change pass | `references/review.md` |
| `flake.nix`, `flake.lock`, inputs, outputs, overlays wiring | `references/flakes.md` |
| new package, override, patch, version bump, hashes | `references/packaging.md` |
| option paths/types/priorities, package lookups, nix-ld | `references/options.md` |
| home-manager, dotfiles, fish, niri/Noctalia, portals, theming | `references/home-manager.md` |
| tmpfs root, `/persist`, `~/Storage`, new stateful service | `references/impermanence.md` |
| sops-nix, credentials, keys | `references/secrets.md` |
| microvm.nix guests, taps/bridges, Tor/Tailscale gateways, OCI GPU | `references/virtualization.md` |
| boot/lanzaboote, kernel, NVIDIA, disks, users, networking | `references/system.md` |
| devShells, direnv, flake templates | `references/devshells.md` |
| GC/disk space, generations, substituters/caches, update routine | `references/maintenance.md` |

Multi-domain tasks load several. A new stateful service always pulls in `impermanence.md`; a guest change always pulls in `virtualization.md` + `testing.md`.

## Invariants

1. **Never guess** an option path, type, default, or package attr. Verify via `mcp-nixos` (behind `mcp-gateway`; `tool_count=0` can mean lazy-loaded, not failure), `nixops.py opt`, or `nix repl`, against the **locked** nixpkgs.
2. **Repo memory first.** In volnixos, search `.memory/mistakes.md` for the symptom (`nixops.py recall <kw>`) before diagnosing; most recurring failures are already solved there.
3. **Stage new files** before evaluating — flakes ignore untracked files.
4. **Formatter is `nixfmt` (RFC 166)** via `make fmt` / `nix fmt`. Not `nixpkgs-fmt`.
5. **Done = evidence.** Minimum: `nixops.py gate` + `nixops.py build` (host changes) with the closure diff read. Report failures verbatim. Never claim success on an unrun check — say what was not run and why.
6. **Refactors prove themselves:** identical toplevel drvPath before/after (`drv --save` / `drv --compare`), or every difference explained.
7. **No live activation unasked.** `build`/`dry-activate` is the default stopping point. When asked: `make switch-detached` if greetd/dbus/display/session/glibc could restart; `make gate-restart` after net-gate guest changes.
8. **Fix the cause at its stage** (parse → eval → build → activate → runtime). No `mkForce`, `--impure`, sandbox disabling, or `allowBroken` to silence an error.
9. **Context, not ceiling.** A repo profile (e.g. `volnixos.md`) describes how a repo works *today* — follow it for routine edits so the system keeps working. It does not limit design: when a convention is the problem, or a different paradigm is clearly better, say so explicitly (what, why, migration path, cost to the existing workflow) and implement it when the task is design work or the user agrees. Judge every idea on Nix merits first (`design.md`), then fit it to the repo — never the reverse.
10. **Commits:** stage everything touched, `--no-gpg-sign`, first-person message, no agent branding. `gh` + `$GH_TOKEN` as fallback. Don't push unless authorized.

## Workflow

1. **Orient** — repo profile + agent docs (`.model/CLAUDE.md`, `CLAUDE.md`) + `.memory/` if present; read the target module and its importers. For design work, start from the problem and `design.md`, then map onto the repo.
2. **Verify facts** — options/packages (invariant 1); `git log -p -- <file>` for why things are the way they are.
3. **Edit** — minimal, idiomatic (`practices.md`); comments only for non-obvious why.
4. **Test** — escalate per `testing.md`: parse → gate → build+closure diff → dry-activate → VM/NixOS test.
5. **Debug** failures per `debugging.md`; record new root causes as a dated note in `.memory/inbox/`.
6. **Review** after major additions (`review.md`), and update `.model/CLAUDE.md` if a subsystem changed.

## Helper: `scripts/nixops.py`

Run from the flake root; exit code is the verdict. Host: `--host`, `$NIX_HOST`, or auto-detect (sole config, or `volnix`).

| Command | Does |
|---|---|
| `gate` | untracked `.nix` check → parse changed files → `make check` (fallback `nix flake check` + statix + deadnix) |
| `parse [files…]` | `nix-instantiate --parse` (default: changed/untracked `.nix`) — instant syntax check |
| `fmt [paths…]` | `make fmt` / `nix fmt`, or `nixfmt` on given paths |
| `opt <path> [--hm USER]` | option value in this config as JSON (NixOS, or under `home-manager.users.USER`) |
| `drv [--save F \| --compare F]` | toplevel drvPath; compare prints `IDENTICAL` or runs `nix-diff` |
| `build [--no-diff]` | build toplevel with logs → closure diff vs `/run/current-system` (`nvd` if present) |
| `why <pkg>` | `nix why-depends` toplevel → `pkgs.<pkg>` |
| `untracked` | `.nix`/`flake.lock` files flakes can't see |
| `doctor` | `nix config check` (falls back to `nix doctor`, e.g. on Lix) |
| `recall <kw…>` | grep `.memory/*.md` for lines containing all keywords |

Also: `nix repl` → `:lf .`, `nix eval --show-trace`, `nix log`, `nix build -L --keep-failed`, `nix flake {show,metadata,check --no-build}`, `nix store diff-closures`, `nix path-info -rsSh`, `statix`, `deadnix`, `nix-diff`, `nvd`, `nix-tree`, `nurl`, `nix-update`.
