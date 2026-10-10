#!/usr/bin/env python3
"""Nix workflow helper: gate, fmt, parse, opt, drv, build, why, untracked, doctor, recall.

Run from the flake root. Host: --host, else $NIX_HOST, else auto-detected
(sole nixosConfiguration, or "volnix" when present). Exit code is the verdict.
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


def run(cmd, check=False, capture=False):
    print("$ " + " ".join(cmd), file=sys.stderr)
    r = subprocess.run(cmd, text=True, capture_output=capture)
    if check and r.returncode != 0:
        if capture:
            sys.stderr.write(r.stderr)
        sys.exit(r.returncode)
    return r


def make_has(target):
    if not Path("Makefile").exists() or not shutil.which("make"):
        return False
    return subprocess.run(["make", "-n", target], capture_output=True).returncode == 0


def git(*args):
    r = subprocess.run(["git", *args], text=True, capture_output=True)
    return [l for l in r.stdout.splitlines() if l] if r.returncode == 0 else []


def untracked_nix():
    return git("ls-files", "--others", "--exclude-standard", "--", "*.nix", "flake.lock")


def changed_nix():
    files = set(git("diff", "--name-only", "HEAD", "--", "*.nix")) | set(untracked_nix())
    return sorted(f for f in files if f.endswith(".nix") and Path(f).exists())


def host(args):
    if args.host:
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


def toplevel(h):
    return f".#nixosConfigurations.{h}.config.system.build.toplevel"


def drv_path(h):
    r = run(["nix", "eval", "--raw", toplevel(h) + ".drvPath", "--show-trace"], check=True, capture=True)
    return r.stdout.strip()


def cmd_untracked(_):
    files = untracked_nix()
    for f in files:
        print(f)
    if files:
        print("^ invisible to flake evaluation until `git add`", file=sys.stderr)
    return 1 if files else 0


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
    cur = drv_path(h)
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


def cmd_build(args):
    h = host(args)
    out = args.out_link
    rc = run(["nix", "build", toplevel(h), "-L", "--out-link", out, "--show-trace"]).returncode
    if rc:
        print(f"build failed; full log: nix log {toplevel(h)}", file=sys.stderr)
        return rc
    if Path("/run/current-system").exists() and not args.no_diff:
        if shutil.which("nvd"):
            run(["nvd", "diff", "/run/current-system", out])
        else:
            run(["nix", "store", "diff-closures", "/run/current-system", out])
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
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    def add(name, fn, help_, host_arg=False):
        s = sub.add_parser(name, help=help_)
        if host_arg:
            s.add_argument("--host")
        s.set_defaults(fn=fn)
        return s

    add("gate", cmd_gate, "untracked + parse + make check / flake check")
    add("untracked", cmd_untracked, "list .nix files flakes cannot see")
    add("parse", cmd_parse, "syntax-check files (default: changed .nix)").add_argument("files", nargs="*")
    add("fmt", cmd_fmt, "make fmt / nix fmt / nixfmt paths").add_argument("paths", nargs="*")
    s = add("opt", cmd_opt, "evaluate an option value as JSON", True)
    s.add_argument("path")
    s.add_argument("--hm", metavar="USER", help="evaluate under home-manager.users.USER")
    s = add("drv", cmd_drv, "toplevel drvPath; --save/--compare for refactor proof", True)
    s.add_argument("--save")
    s.add_argument("--compare")
    s = add("build", cmd_build, "build toplevel and diff closure vs running system", True)
    s.add_argument("--out-link", default="result")
    s.add_argument("--no-diff", action="store_true")
    add("why", cmd_why, "why the toplevel depends on a package", True).add_argument("pkg")
    add("doctor", cmd_doctor, "nix config check (falls back to nix doctor)")
    add("recall", cmd_recall, "search .memory/*.md for all keywords").add_argument("keywords", nargs="+")

    args = p.parse_args()
    sys.exit(args.fn(args))


if __name__ == "__main__":
    main()
