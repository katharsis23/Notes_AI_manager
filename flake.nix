{
  description = "Obsidian Master AI CLI - a local CLI tool for generating structured Obsidian notes via Ollama";
  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs =
    {
      self,
      nixpkgs,
      flake-utils,
    }:
    flake-utils.lib.eachDefaultSystem (
      system:
      let
        pkgs = import nixpkgs { inherit system; };

        # Required runtime / build-time Python dependencies
        python = pkgs.python3;

        pythonDeps = python.withPackages (
          ps: with ps; [
            httpx
            rich
          ]
        );

        # Single-file wrapper package that exposes the `note` command.
        app = pkgs.stdenv.mkDerivation {
          pname = "obsidian-master";
          version = "0.1.0";
          src = self;

          nativeBuildInputs = [
            pythonDeps
            pkgs.makeWrapper
          ];

          dontBuild = true;
          dontConfigure = true;

          installPhase = ''
            runHook preInstall

            mkdir -p $out/share/obsidian-master
            cp -r . $out/share/obsidian-master/

            mkdir -p $out/bin
            makeWrapper ${pythonDeps}/bin/python \
              $out/bin/note \
              --add-flags "$out/share/obsidian-master/note.py" \
              --prefix PYTHONPATH : ${pythonDeps}/${pythonDeps.sitePackages}

            runHook postInstall
          '';
        };
      in
      {
        # `nix build` -> produces a runnable `note` binary wrapper.
        packages.default = app;

        # `nix develop` -> interactive dev environment with the app deps.
        devShells.default = pkgs.mkShell {
          packages = [
            pythonDeps
          ];

          shellHook = ''
            echo "Obsidian Master dev shell"
            echo "Python: ${pythonDeps}/${pythonDeps.sitePackages}"
          '';
        };
      }
    );
}
