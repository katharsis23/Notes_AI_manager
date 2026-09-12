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
        pkgs = import nixpkgs {
          inherit system;

          # CUDA packages are unfree. Allow the CUDA/NVIDIA family only —
          # everything nixpkgs names "cuda*", "cudnn*", "libcu*", "libnv*",
          # "nvidia*". Pure free software is unaffected.
          config.allowUnfreePredicate =
            pkg:
            let
              name = pkgs.lib.getName pkg;
              prefixes = [
                "cuda"
                "cudnn"
                "libcu"
                "libnv"
                "nvidia"
              ];
            in
            pkgs.lib.any (p: pkgs.lib.hasPrefix p name) prefixes;
        };
        cuda = pkgs.cudaPackages;

        # Only the CUDA pieces CTranslate2 (faster-whisper backend) actually
        # needs at runtime. Pulling the whole `cudatoolkit` drags in libnpp,
        # cufft, cusparse, ... none of which whisper uses, so we keep it minimal
        # (and the unfree allow-list small).
        cudaRuntimeLibs = [
          cuda.cuda_cudart # libcudart.so.*
          cuda.cudnn # libcudnn.so.*
          cuda.libcublas # libcublas.so.* / libcublasLt.so.*
        ];

        # Python deps installed into a shared environment used both by the
        # wrapper (packages.default) and the dev shell.
        python = pkgs.python3;
        pythonDeps = python.withPackages (
          ps: with ps; [
            httpx
            rich
          ]
        );

        # Native shared libraries that compiled extensions dlopen at runtime:
        #  - libstdc++.so.6 / libz.so.1 / libGL.so.1  -> generic runtime
        #  - ffmpeg                                    -> audio decoding (PyAV)
        #  - CUDA runtime / cuDNN / cuBLAS             -> used by CTranslate2
        nativeLibs = [
          pkgs.stdenv.cc.cc.lib
          pkgs.zlib
          pkgs.libGL
          pkgs.ffmpeg
        ]
        ++ cudaRuntimeLibs;

        # Single directory to put on LD_LIBRARY_PATH.
        nativeLibPath = pkgs.lib.makeLibraryPath nativeLibs;

        # `nix build` -> a runnable `note` wrapper.
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
              --prefix PYTHONPATH : ${pythonDeps}/${pythonDeps.sitePackages} \
              --prefix LD_LIBRARY_PATH : ${nativeLibPath}

            runHook postInstall
          '';
        };
      in
      {
        # `nix build` -> produces a runnable `note` binary wrapper.
        packages.default = app;

        # `nix develop` -> interactive dev environment.
        devShells.default = pkgs.mkShell {
          packages = [ pythonDeps ] ++ nativeLibs;

          shellHook = ''
            # Make native libs discoverable by the venv's compiled extensions
            # (faster-whisper -> av -> libstdc++.so.6 / libz.so.1 / ffmpeg,
            #  CTranslate2 -> cudart / cudnn / cublas).
            export LD_LIBRARY_PATH="${nativeLibPath}:$LD_LIBRARY_PATH"

            echo "Obsidian Master dev shell"
            echo "Python: ${pythonDeps}/${pythonDeps.sitePackages}"
          '';
        };
      }
    );
}
