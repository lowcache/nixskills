#!/usr/bin/env python3
"""Nix workflow helper: gate, parse, fmt, opt, drv, build, cache, evaltime, why,
untracked, doctor, recall.

Run from the flake root. Host: --host, else $NIX_HOST, else auto-detected
(sole nixosConfiguration, or "volnix" when present). Exit code is the verdict.
"""
import argparse
import fnmatch
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

# Pins system.configurationRevision so drvPaths compare equal across commits and
# clean/dirty trees; configs without extendModules are evaluated as-is.
PIN_REV = (
    "c: (if c ? extendModules then (c.extendModules { modules = [ "
    '{ system.configurationRevision = c.pkgs.lib.mkForce "nixops-compare"; } ]; }) '
    "else c).config.system.build.toplevel.drvPath"
)


def run(cmd, check=False, capture=False, env=None):
    print("$ " + " ".join(cmd), file=sys.stderr)
    r = subprocess.run(cmd, text=True, capture_output=capture, env=env)
    if check and r.returncode != 0:
        if capture:
            sys.stderr.write(r.stderr)
        sys.exit(r.returncode)
    return r


def make_has(target):
    if not Path("Makefile").exists() or not shutil.which("make"):
        return False
    return subprocess.run(["make", "-n", target], capture_output=True).returncode == 0


def make_var(name):
    """Value of a Makefile variable, or None (GNU make --eval)."""
    if not Path("Makefile").exists() or not shutil.which("make"):
        return None
    r = subprocess.run(
        ["make", "-s", "--no-print-directory", "--eval", f"__nixops_var: ; @echo $({name})", "__nixops_var"],
        text=True, capture_output=True,
    )
    return (r.stdout.strip() or None) if r.returncode == 0 else None


def build_env():
    """Build temp dir: $TMPDIR if set, else the Makefile's REBUILD_TMPDIR (keeps tmpfs roots clear)."""
    env = dict(os.environ)
    if "TMPDIR" not in env:
        tmp = make_var("REBUILD_TMPDIR")
        if tmp and Path(tmp).is_dir():
            env["TMPDIR"] = tmp
    return env


def git(*args):
    r = subprocess.run(["git", *args], text=True, capture_output=True)
    return [l for l in r.stdout.splitlines() if l] if r.returncode == 0 else []


def lint_ignores():
    """Glob patterns the repo already excludes from Nix linting (statix.toml `ignore`)."""
    p = Path("statix.toml")
    if not p.exists():
        return []
    m = re.search(r"^\s*ignore\s*=\s*\[(.*?)\]", p.read_text(), re.S | re.M)
    return re.findall(r'"([^"]+)"', m.group(1)) if m else []


def untracked_nix():
    """Untracked .nix/flake.lock files, split into (relevant, ignored-by-repo-lint-scope)."""
    files = git("ls-files", "--others", "--exclude-standard", "--", "*.nix", "flake.lock")
    ign = lint_ignores()
    skipped = [f for f in files if any(fnmatch.fnmatch(f, g) for g in ign)]
    return [f for f in files if f not in skipped], skipped


def changed_nix():
    rel, _ = untracked_nix()
    files = set(git("diff", "--name-only", "HEAD", "--", "*.nix")) | set(rel)
    return sorted(f for f in files if f.endswith(".nix") and Path(f).exists())


def host(args):
    if getattr(args, "host", None):
        return args.host
    if os.environ.get("NIX_HOST"):
        return os.environ["NIX_HOST"]
    r = run(["nix", "eval", "--json", ".#nixosConfigurations", "--apply", "builtins.attrNames"], capture=True)
    names = json.loads(r.stdout) if r.returncode == 0 else []
    if len(names) == 1:
        return names[0]
    if "volnix" in names:
        return "volnix"
    sys.exit(f"cannot pick a host from {names or 'nothing'}; pass --host")


def toplevel(h, flake="."):
    return f"{flake}#nixosConfigurations.{h}.config.system.build.toplevel"


def drv_path(h, pin=True):
    if pin:
        cmd = ["nix", "eval", "--raw", f".#nixosConfigurations.{h}", "--apply", PIN_REV, "--show-trace"]
    else:
        cmd = ["nix", "eval", "--raw", toplevel(h) + ".drvPath", "--show-trace"]
    return run(cmd, check=True, capture=True).stdout.strip()


def cmd_untracked(args):
    rel, skipped = untracked_nix()
    for f in rel:
        print(f)
    if skipped:
        print(f"({len(skipped)} untracked under statix.toml ignore globs, not counted)", file=sys.stderr)
    if rel:
        print("^ invisible to flake evaluation until `git add`", file=sys.stderr)
    return 1 if rel and not getattr(args, "allow_untracked", False) else 0


def cmd_parse(args):
    files = args.files or changed_nix()
    bad = 0
    for f in files:
        r = subprocess.run(["nix-instantiate", "--parse", f], text=True, capture_output=True)
        if r.returncode:
            bad += 1
            print(f"FAIL {f}\n{r.stderr.strip()}")
    print(f"parse: {len(files) - bad}/{len(files)} ok")
    return 1 if bad else 0


def cmd_gate(args):
    if cmd_untracked(args):
        return 1
    if cmd_parse(argparse.Namespace(files=[])):
        return 1
    if make_has("check"):
        return run(["make", "check"]).returncode
    rc = run(["nix", "flake", "check", "--show-trace"]).returncode
    for tool, extra in (("statix", ["check", "."]), ("deadnix", ["--fail", "."])):
        if rc == 0 and shutil.which(tool):
            rc = run([tool, *extra]).returncode
    return rc


def cmd_fmt(args):
    if args.paths:
        return run(["nixfmt", *args.paths]).returncode
    if make_has("fmt"):
        return run(["make", "fmt"]).returncode
    return run(["nix", "fmt"]).returncode


def cmd_opt(args):
    h = host(args)
    base = f".#nixosConfigurations.{h}.config"
    if args.hm:
        base += f".home-manager.users.{args.hm}"
    return run(["nix", "eval", "--json", f"{base}.{args.path}", "--show-trace"]).returncode


def cmd_drv(args):
    h = host(args)
    cur = drv_path(h, pin=not args.with_rev)
    print(cur)
    if args.save:
        Path(args.save).write_text(cur + "\n")
        print(f"saved to {args.save}", file=sys.stderr)
    if args.compare:
        old = Path(args.compare).read_text().strip()
        if old == cur:
            print("IDENTICAL: behavior-preserving")
            return 0
        print(f"DIFFERS:\n  before {old}\n  after  {cur}")
        if shutil.which("nix-diff"):
            run(["nix-diff", old, cur])
        else:
            print("install nix-diff (nix shell nixpkgs#nix-diff) to explain the difference")
        return 1
    return 0


def closure_diff(old, new):
    if shutil.which("nvd"):
        return run(["nvd", "diff", old, new]).returncode
    return run(["nix", "store", "diff-closures", old, new]).returncode


def build_rev(h, rev, out, env):
    """Build toplevel at a git rev in a throwaway worktree; returns rc."""
    wt = tempfile.mkdtemp(prefix="nixops-wt-", dir=env.get("TMPDIR"))
    try:
        if run(["git", "worktree", "add", "--detach", wt, rev], capture=True).returncode:
            return 1
        return run(["nix", "build", toplevel(h, wt), "--out-link", out], env=env).returncode
    finally:
        subprocess.run(["git", "worktree", "remove", "--force", wt], capture_output=True)


def cmd_build(args):
    h = host(args)
    env = build_env()
    out = args.out_link
    rc = run(["nix", "build", toplevel(h), "-L", "--out-link", out, "--show-trace"], env=env).returncode
    if rc:
        print(f"build failed; full log: nix log {toplevel(h)}", file=sys.stderr)
        return rc
    against = args.against
    if against == "auto":
        dirty = bool(git("status", "--porcelain", "--untracked-files=no"))
        against = "HEAD" if dirty else "current"
    if against == "none":
        return 0
    if against == "current":
        if not Path("/run/current-system").exists():
            print("no /run/current-system; skipping diff", file=sys.stderr)
            return 0
        print("== closure diff: running system -> this build", file=sys.stderr)
        closure_diff("/run/current-system", out)
        return 0
    base = out + "-base"
    if build_rev(h, against, base, env):
        print(f"could not build {against}; no diff", file=sys.stderr)
        return 0
    print(f"== closure diff: {against} -> working tree", file=sys.stderr)
    closure_diff(base, out)
    return 0


def probe_substituters():
    """Return [(url, error)] for effective substituters whose nix-cache-info is unreachable."""
    import urllib.request

    r = subprocess.run(["nix", "config", "show", "substituters"], text=True, capture_output=True)
    bad = []
    for url in r.stdout.split():
        if not url.startswith("http"):
            continue
        try:
            urllib.request.urlopen(url.rstrip("/") + "/nix-cache-info", timeout=10).read(64)
        except Exception as e:  # any failure means Nix will silently skip this cache
            bad.append((url, str(e)[:120]))
    return bad


def cmd_cache(args):
    """List derivations that would be compiled locally instead of substituted."""
    h = host(args)
    for url, err in probe_substituters():
        print(f"WARN substituter unreachable, its paths will count as builds: {url} ({err})", file=sys.stderr)
    r = run(["nix", "build", "--dry-run", toplevel(h)], capture=True, env=build_env())
    if r.returncode:
        sys.stderr.write(r.stderr)
        return r.returncode
    built, section = [], None
    for line in r.stderr.splitlines():
        if "will be built" in line:
            section = "build"
        elif "will be fetched" in line:
            section = "fetch"
        elif section == "build" and line.strip().startswith("/nix/store/"):
            built.append(line.strip())
    for d in built:
        print(d)
    print(f"{len(built)} derivation(s) would be built locally", file=sys.stderr)
    heavy = [d for d in built if re.search(args.fail_on, d)] if args.fail_on else []
    if heavy:
        print(f"FAIL: matches --fail-on {args.fail_on!r}: {heavy}", file=sys.stderr)
        return 1
    return 0


def cmd_evaltime(args):
    h = host(args)
    with tempfile.NamedTemporaryFile(suffix=".json") as stats:
        env = dict(os.environ, NIX_SHOW_STATS="1", NIX_SHOW_STATS_PATH=stats.name)
        t = time.monotonic()
        r = run(["nix", "eval", "--raw", toplevel(h) + ".drvPath"], capture=True, env=env)
        wall = time.monotonic() - t
        if r.returncode:
            sys.stderr.write(r.stderr)
            return r.returncode
        data = {}
        try:
            data = json.loads(Path(stats.name).read_text() or "{}")
        except (OSError, ValueError):
            pass
    out = {"wallSeconds": round(wall, 2)}
    for k in ("cpuTime", "nrThunks", "nrFunctionCalls"):
        if k in data:
            out[k] = data[k]
    if isinstance(data.get("gc"), dict):
        out["gcHeapBytes"] = data["gc"].get("heapSize")
    print(json.dumps(out))
    if args.save:
        Path(args.save).write_text(json.dumps(out))
    if args.compare:
        old = json.loads(Path(args.compare).read_text())
        for k in out:
            if k in old and old[k]:
                print(f"{k}: {old[k]} -> {out[k]} ({(out[k] - old[k]) / old[k]:+.0%})")
    return 0


def cmd_why(args):
    h = host(args)
    return run(["nix", "why-depends", toplevel(h), f".#nixosConfigurations.{h}.pkgs.{args.pkg}"]).returncode


def cmd_doctor(_):
    rc = run(["nix", "config", "check"]).returncode
    if rc:
        rc = run(["nix", "doctor"]).returncode
    return rc


def cmd_recall(args):
    hits = 0
    for f in sorted(Path(".memory").glob("*.md")):
        for n, line in enumerate(f.read_text(errors="replace").splitlines(), 1):
            if all(k.lower() in line.lower() for k in args.keywords):
                hits += 1
                print(f"{f}:{n}: {line.strip()[:240]}")
    if not hits:
        print("no matches in .memory/*.md")
    return 0


def main():
    p = argparse.ArgumentParser(prog="nixops", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    def add(name, fn, help_, host_arg=False):
        s = sub.add_parser(name, help=help_)
        if host_arg:
            s.add_argument("--host")
        s.set_defaults(fn=fn)
        return s

    s = add("gate", cmd_gate, "untracked + parse + make check / flake check")
    s.add_argument("--allow-untracked", action="store_true")
    s = add("untracked", cmd_untracked, "list .nix files flakes cannot see")
    s.add_argument("--allow-untracked", action="store_true")
    add("parse", cmd_parse, "syntax-check files (default: changed .nix)").add_argument("files", nargs="*")
    add("fmt", cmd_fmt, "make fmt / nix fmt / nixfmt paths").add_argument("paths", nargs="*")
    s = add("opt", cmd_opt, "evaluate an option value as JSON", True)
    s.add_argument("path")
    s.add_argument("--hm", metavar="USER", help="evaluate under home-manager.users.USER")
    s = add("drv", cmd_drv, "toplevel drvPath (revision pinned); --save/--compare for refactor proof", True)
    s.add_argument("--save")
    s.add_argument("--compare")
    s.add_argument("--with-rev", action="store_true", help="don't pin system.configurationRevision")
    s = add("build", cmd_build, "build toplevel, then closure diff", True)
    s.add_argument("--out-link", default="result")
    s.add_argument(
        "--against", default="auto",
        help="auto (HEAD if tree dirty, else current) | current | none | <git rev>",
    )
    s = add("cache", cmd_cache, "list derivations that would build locally (cache misses)", True)
    s.add_argument("--fail-on", metavar="REGEX", help="exit 1 if a would-build drv matches")
    s = add("evaltime", cmd_evaltime, "evaluation cost of the toplevel (wall, cpu, thunks)", True)
    s.add_argument("--save")
    s.add_argument("--compare")
    add("why", cmd_why, "why the toplevel depends on a package", True).add_argument("pkg")
    add("doctor", cmd_doctor, "nix config check (falls back to nix doctor)")
    add("recall", cmd_recall, "search .memory/*.md for all keywords").add_argument("keywords", nargs="+")

    args = p.parse_args()
    sys.exit(args.fn(args))


if __name__ == "__main__":
    main()
