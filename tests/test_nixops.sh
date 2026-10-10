#!/usr/bin/env bash
# End-to-end tests for nix/scripts/nixops.py against a stub flake (no inputs, no network).
# The stub mimics nixosSystem: extendModules, pkgs.lib.mkForce, and a revision taken
# from self.rev/dirtyRev, which is what makes naive drvPath comparison flap.
set -euo pipefail
[ -n "${DEBUG:-}" ] && set -x

S=${NIXOPS:-$(realpath "$(dirname "$0")/../nix/scripts/nixops.py")}
W=$(mktemp -d)
trap 'rm -rf "$W"' EXIT
cd "$W"
export NIX_CONFIG="experimental-features = nix-command flakes"
pass=0
fail() { echo "FAIL: $*" >&2; exit 1; }
ok() { pass=$((pass + 1)); echo "ok - $*"; }

git init -q && git config user.email t@t && git config user.name t
cat >flake.nix <<'EOF'
{
  outputs = { self }: let
    mk = name: deps: derivation {
      inherit name;
      system = "x86_64-linux"; # builders: x86_64 only
      builder = "/bin/sh";
      args = [ "-c" "echo ${toString deps} > $out" ];
    };
    dep = mk "dep-hello" [ ];
    host = rev: {
      config = {
        networking.hostName = "box";
        system.build.toplevel = mk "toplevel-${builtins.substring 0 7 rev}-v1" [ dep ];
        home-manager.users.u.home.stateVersion = "24.11";
      };
      extendModules = _: host "pinned0";
      pkgs = { hello = dep; lib.mkForce = x: x; };
    };
  in {
    nixosConfigurations.box = host (self.rev or self.dirtyRev or "unknown");
  };
}
EOF
cat >statix.toml <<'EOF'
ignore = ["scratch/**"]
EOF
git add -A && git commit -qm init

# host autodetect + opt
[ "$("$S" opt networking.hostName 2>/dev/null)" = '"box"' ] || fail opt; ok "opt autodetects host"
[ "$("$S" opt home.stateVersion --hm u 2>/dev/null)" = '"24.11"' ] || fail "opt --hm"; ok "opt --hm"

# drv: revision pinned, so commit/dirty changes don't flap
"$S" drv --save before >/dev/null 2>&1
echo "# touch" >>statix.toml   # dirty tree, revision changes
"$S" drv --compare before >/dev/null 2>&1 || fail "pinned drv flapped on dirty tree"
ok "drv pinned: identical across clean->dirty"
"$S" drv --with-rev --save raw1 >/dev/null 2>&1
git commit -qam bump
"$S" drv --with-rev --compare raw1 >/dev/null 2>&1 && fail "--with-rev should differ across commits"
ok "drv --with-rev exposes the revision"
sed -i 's/-v1"/-v2"/' flake.nix
"$S" drv --compare before >/dev/null 2>&1 && fail "real change not detected"
ok "drv detects a real change"
git checkout -q flake.nix

# untracked: relevant fails, lint-ignored is skipped
mkdir -p scratch && echo '{ }' >scratch/x.nix
"$S" untracked >/dev/null 2>&1 || fail "ignored untracked counted"
ok "untracked skips statix ignore globs"
echo '{ }' >new.nix
"$S" untracked >/dev/null 2>&1 && fail "relevant untracked missed"
"$S" untracked --allow-untracked >/dev/null 2>&1 || fail "--allow-untracked"
ok "untracked flags relevant files"

# parse
printf '{ a = 1\n' >new.nix
"$S" parse >/dev/null 2>&1 && fail "parse missed syntax error"
ok "parse catches syntax errors"
rm new.nix

# build + diff against HEAD in a worktree
sed -i 's/-v1"/-v3"/' flake.nix
"$S" build --against HEAD >/dev/null 2>&1 || fail "build"
[ -e result ] && [ -e result-base ] || fail "build out-links"
[ "$(git worktree list | wc -l)" -eq 1 ] || fail "worktree leaked"
ok "build diffs against HEAD and cleans its worktree"

# cache lists would-build drvs; --fail-on trips
"$S" cache --fail-on 'nomatch' >/dev/null 2>&1 || fail "cache"
sed -i -E 's/-v[0-9]"/-v9"/' flake.nix
"$S" cache 2>/dev/null | grep -q 'toplevel-.*-v9.drv' || fail "cache did not list unbuilt drv"
"$S" cache --fail-on 'toplevel' >/dev/null 2>&1 && fail "cache --fail-on did not trip"
ok "cache lists would-build drvs and --fail-on trips"

# evaltime emits JSON
"$S" evaltime 2>/dev/null | python3 -c 'import json,sys; d=json.load(sys.stdin); assert "wallSeconds" in d and "cpuTime" in d, d' || fail evaltime
ok "evaltime emits json"

echo "all $pass passed"
