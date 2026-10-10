{
  description = "Consolidated Nix skill for Claude Code, plus the nixops helper";

  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";

  outputs =
    { self, nixpkgs }:
    let
      systems = [
        "x86_64-linux"
        "aarch64-linux"
      ];
      forAll = f: nixpkgs.lib.genAttrs systems (s: f nixpkgs.legacyPackages.${s});
    in
    {
      # `nix` itself is deliberately not pinned: nixops drives whatever Nix/Lix the host runs.
      packages = forAll (pkgs: {
        nixops = pkgs.writeShellApplication {
          name = "nixops";
          runtimeInputs = with pkgs; [
            python3
            git
            gnumake
            nix-diff
            nvd
            nixfmt
            statix
            deadnix
          ];
          text = ''exec python3 ${./nix/scripts/nixops.py} "$@"'';
        };
        default = self.packages.${pkgs.stdenv.hostPlatform.system}.nixops;
      });

      formatter = forAll (pkgs: pkgs.nixfmt-tree);

      # Sandbox-safe gates. The end-to-end suite (tests/test_nixops.sh) needs a Nix
      # daemon, so it runs in CI and via `nix run .#test`.
      checks = forAll (pkgs: {
        formatting = pkgs.runCommand "check-formatting" { nativeBuildInputs = [ pkgs.nixfmt ]; } ''
          nixfmt --check ${./flake.nix}
          touch $out
        '';
        script = pkgs.runCommand "check-script" { nativeBuildInputs = [ pkgs.python3 ]; } ''
          python3 -m py_compile ${./nix/scripts/nixops.py}
          python3 ${./nix/scripts/nixops.py} --help >/dev/null
          touch $out
        '';
        nixops = self.packages.${pkgs.stdenv.hostPlatform.system}.nixops;
      });

      apps = forAll (pkgs: {
        test = {
          type = "app";
          program = "${pkgs.writeShellScript "nixops-test" ''
            PATH=${
              pkgs.lib.makeBinPath [
                pkgs.python3
                pkgs.git
                pkgs.gnused
              ]
            }:$PATH
            NIXOPS=${./nix/scripts/nixops.py} exec ${pkgs.bash}/bin/bash ${./tests/test_nixops.sh}
          ''}";
        };
      });
    };
}
