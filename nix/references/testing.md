# Testing

Escalate only as far as the change needs. Each level catches what the previous can't.

| Level | Command | Catches | Cost |
|---|---|---|---|
| 0 Parse | `nixops.py parse <files>` | syntax | ms |
| 1 Gate | `nixops.py gate` (`make check`) | format, statix, deadnix, flake eval, `checks.*` | s |
| 2 Eval host | `nixops.py drv` | full system evaluates; assertions | s |
| 2b Cache | `nixops.py cache` | what would compile locally; unreachable substituters | s |
| 3 Build | `nixops.py build` (`make build`) | derivations build; closure diff vs HEAD (dirty tree) or running system | min |
| 4 Dry-activate | `make dry-activate` | which units restart/stop; activation script errors | s |
| 5 VM | `nix build .#nixosConfigurations.<host>.config.system.build.vm` → `./result/bin/run-*-vm` | boots, services start, no host risk | min |
| 6 NixOS test | `nix build .#checks.x86_64-linux.<test> -L` | scripted behavior (ports, units, network, Tor egress) | min |
| 7 Live | `nixos-rebuild test` (no boot entry) → then `make switch` | real hardware | — |

Minimum before reporting done: levels 1–3 for host changes; 1 + build of the affected output otherwise. Level 4 whenever networking, display manager, greetd, or systemd-networkd changed. Level 6 for MicroVM/firewall/Tor changes when a test exists — propose one when it doesn't.

## Closure diff (what actually changed)
`nixops.py build` prints it — against HEAD when the tree is dirty, so the diff is *this change only*. Manually: `nix store diff-closures /run/current-system ./result` or `nvd diff /run/current-system ./result`. An "unrelated" version bump or a removed package in the diff is a finding — explain it before switching.

## Refactor proof
Pure restructure ⇒ identical drvPath (nixops pins `system.configurationRevision`, which otherwise changes with every commit/dirty tree): `nixops.py drv --save /tmp/before` → edit → `nixops.py drv --compare /tmp/before`. Differs → `nix-diff` output explains every difference, or the refactor isn't pure.

## Eval cost
`nixops.py evaltime --save /tmp/e0` before, `--compare /tmp/e0` after a structural change. Each extra NixOS evaluation (MicroVM guests, `import nixpkgs` in modules, IFD) adds seconds; treat a >20% jump as a finding.

## Writing NixOS tests
Put them in `checks.<system>` so `nix flake check` runs them.
```nix
checks.x86_64-linux.netgate = pkgs.testers.runNixOSTest {
  name = "netgate";
  nodes.gate = { imports = [ ./vms/net-gate.nix ]; };
  nodes.client = { … };
  testScript = ''
    start_all()
    gate.wait_for_unit("tor.service")
    gate.wait_for_open_port(9040)
    client.succeed("…")
    client.fail("curl --max-time 5 https://example.com")  # no non-Tor egress
  '';
};
```
- Test real behavior (ports open, unit active, traffic blocked), not that an option is set.
- Debug interactively: `nix build .#checks.x86_64-linux.netgate.driverInteractive && ./result/bin/nixos-test-driver` → `start_all()`, `gate.shell_interact()`.
- `wait_for_*` over `sleep`.

## Testing library code
Pure functions in `lib/`: `lib.debug.runTests { testX = { expr = …; expected = …; }; }` returns failures (`[]` = pass); wrap in a `checks` derivation that fails when non-empty. Use `nix-unit` if the repo already has it.

## Packages
`nix build .#<pkg> -L`, then run its binary from `./result`; `passthru.tests` for package tests; `nixpkgs-review` when upstreaming.
