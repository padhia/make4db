{
  description = "Library for building GNU Make like tool for database scripts";

  inputs = {
    nixpkgs.url = "github:nixos/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";

    nix-utils.url = "github:padhia/nix-utils";
    nix-utils.inputs.nixpkgs.follows = "nixpkgs";

    make4db-api.url = "github:padhia/make4db-api";
    make4db-api.inputs = {
      nixpkgs.follows = "nixpkgs";
      nix-utils.follows = "nix-utils";
      flake-utils.follows = "flake-utils";
    };

    yappt.url = "github:padhia/yappt";
    yappt.inputs = {
      nixpkgs.follows = "nixpkgs";
      nix-utils.follows = "nix-utils";
      flake-utils.follows = "flake-utils";
    };
  };

  outputs = { self, nixpkgs, flake-utils, nix-utils, yappt, make4db-api }:
  let
    inherit (nix-utils.lib) pyDevShell mkApps;

    overlays.default = final: prev: {
      pythonPackagesExtensions = prev.pythonPackagesExtensions ++ [
        (py-final: py-prev: {
          make4db = py-final.callPackage ./make4db.nix {};
        })
      ];
    } // { inherit (final.python311Packages) make4db mak4db-sf; };

    buildSystem = system:
    let
      pkgs = import nixpkgs {
        inherit system;
        config.allowUnfree = true;
        overlays = [
          make4db-api.overlays.default
          yappt.overlays.default
          self.overlays.default
        ];
      };

      devShells.default = pyDevShell {
        inherit pkgs;
        pyVer = "311";
        name = "make4db";
        extra = [
          "make4db-api"
          "yappt"
          "sqlparse"
        ];
      };

      packages.default = pkgs.make4db;

      apps = mkApps {
        pkg = packages.default;
        cmds = [ "m4db" "m4db-refs" "m4db-gc" "m4db-cache" ];
      };
    in {
      inherit devShells packages apps;
    };

  in {
    inherit overlays;
    inherit (flake-utils.lib.eachDefaultSystem buildSystem) devShells packages apps;
  };
}
