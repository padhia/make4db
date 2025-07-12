{
  description = "Library for building GNU Make like tool for database scripts";

  inputs = {
    nixpkgs.url = "github:nixos/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";

    yappt.url = "github:padhia/yappt";
    yappt.inputs = {
      nixpkgs.follows = "nixpkgs";
      flake-utils.follows = "flake-utils";
    };

    make4db-api.url = "github:padhia/make4db-api";
    make4db-api.inputs = {
      nixpkgs.follows = "nixpkgs";
      flake-utils.follows = "flake-utils";
    };

    make4db-duckdb.url = "github:padhia/make4db-duckdb";
    make4db-duckdb.inputs = {
      nixpkgs.follows = "nixpkgs";
      flake-utils.follows = "flake-utils";
      make4db-api.follows = "make4db-api";
    };

    make4db-postgres.url = "github:padhia/make4db-postgres";
    make4db-postgres.inputs = {
      nixpkgs.follows = "nixpkgs";
      flake-utils.follows = "flake-utils";
      make4db-api.follows = "make4db-api";
      yappt.follows = "yappt";
    };

    make4db-snowflake.url = "github:padhia/make4db-snowflake";
    make4db-snowflake.inputs = {
      nixpkgs.follows = "nixpkgs";
      flake-utils.follows = "flake-utils";
      make4db-api.follows = "make4db-api";
      snowflake.follows = "snowflake";
      sfconn.follows = "sfconn";
      yappt.follows = "yappt";
    };

    snowflake.url = "github:padhia/snowflake";
    snowflake.inputs = {
      nixpkgs.follows = "nixpkgs";
      flake-utils.follows = "flake-utils";
    };

    sfconn.url = "github:padhia/sfconn";
    sfconn.inputs = {
      nixpkgs.follows = "nixpkgs";
      flake-utils.follows = "flake-utils";
      snowflake.follows = "snowflake";
    };
  };

  outputs = { self, nixpkgs, flake-utils, yappt, make4db-api, make4db-duckdb, make4db-postgres, make4db-snowflake, sfconn, ... }:
  let
    inherit (nixpkgs.lib) composeManyExtensions;

    overlays.default =
    let
      pkgOverlay = final: prev: {
        pythonPackagesExtensions = prev.pythonPackagesExtensions ++ [
          (py-final: py-prev: {
            make4db = py-final.callPackage ./make4db.nix {};
          })
        ];
        make4db-duckdb = final.python3.withPackages(ps: with ps; [make4db] ++ make4db.optional-dependencies.duckdb);
        make4db-postgres = final.python3.withPackages(ps: with ps; [make4db] ++ make4db.optional-dependencies.postgres);
        make4db-snowflake = final.python312.withPackages(ps: with ps; [make4db] ++ make4db.optional-dependencies.snowflake);
      };
    in composeManyExtensions [
      make4db-api.overlays.default
      make4db-duckdb.overlays.default
      make4db-postgres.overlays.default
      make4db-snowflake.overlays.default
      yappt.overlays.default
      pkgOverlay
    ];

    eachSystem = system:
    let
      pkgs = import nixpkgs {
        inherit system;
        config.allowUnfree = true;
        overlays = [ self.overlays.default ];
      };

      pyPkgs = pkgs.python312Packages;

    in {
      devShells.default = pkgs.mkShell {
        name = "m4db";
        venvDir = "./.venv";
        buildInputs = [
          pkgs.ruff
          pkgs.uv
          pyPkgs.python
          pyPkgs.venvShellHook
          pyPkgs.pytest
          pyPkgs.sqlparse
          pyPkgs.make4db-api
          pyPkgs.yappt
        ];
      };

      packages = {
        inherit (pkgs) make4db-duckdb make4db-postgres make4db-snowflake;
      };
    };

  in {
    inherit overlays;
    inherit (flake-utils.lib.eachDefaultSystem eachSystem) devShells packages;
  };
}
