{
  description = "Library for building GNU Make like tool for database scripts";

  inputs = {
    nixpkgs.url = "github:nixos/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";

    nix-utils.url = "github:padhia/nix-utils";
    nix-utils.inputs.nixpkgs.follows = "nixpkgs";

    yappt.url = "github:padhia/yappt";
    yappt.inputs = {
      nixpkgs.follows = "nixpkgs";
      nix-utils.follows = "nix-utils";
      flake-utils.follows = "flake-utils";
    };

    make4db-api.url = "github:padhia/make4db-api";
    make4db-api.inputs = {
      nixpkgs.follows = "nixpkgs";
      nix-utils.follows = "nix-utils";
      flake-utils.follows = "flake-utils";
    };

    make4db-duckdb.url = "github:padhia/make4db-duckdb";
    make4db-duckdb.inputs = {
      nixpkgs.follows = "nixpkgs";
      nix-utils.follows = "nix-utils";
      flake-utils.follows = "flake-utils";
      make4db-api.follows = "make4db-api";
    };

    make4db-postgres.url = "github:padhia/make4db-postgres";
    make4db-postgres.inputs = {
      nixpkgs.follows = "nixpkgs";
      nix-utils.follows = "nix-utils";
      flake-utils.follows = "flake-utils";
      make4db-api.follows = "make4db-api";
      yappt.follows = "yappt";
    };

    make4db-snowflake.url = "github:padhia/make4db-snowflake";
    make4db-snowflake.inputs = {
      nixpkgs.follows = "nixpkgs";
      nix-utils.follows = "nix-utils";
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
      nix-utils.follows = "nix-utils";
      snowflake.follows = "snowflake";
    };
  };

  outputs = { self, nixpkgs, flake-utils, nix-utils, yappt, make4db-api, make4db-duckdb, make4db-postgres, make4db-snowflake, sfconn, ... }:
  let
    inherit (nix-utils.lib) pyDevShell;
    inherit (nixpkgs.lib) composeManyExtensions;

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

    overlays.default = composeManyExtensions [
      make4db-api.overlays.default
      make4db-duckdb.overlays.default
      make4db-postgres.overlays.default
      make4db-snowflake.overlays.default
      pkgOverlay
    ];

    buildSystem = system:
    let
      pkgs = import nixpkgs {
        inherit system;
        config.allowUnfree = true;
        overlays = [
          make4db-api.overlays.default
          make4db-duckdb.overlays.default
          make4db-postgres.overlays.default
          make4db-snowflake.overlays.default
          sfconn.overlays.default
          yappt.overlays.default
          self.overlays.default
        ];
      };
    in {
      devShells.default = pyDevShell {
        inherit pkgs;
        name = "make4db";
        extra = [
          "sqlparse"
          "make4db-api"
          "yappt"
        ];
      };

      packages = {
        inherit (pkgs) make4db-duckdb make4db-postgres make4db-snowflake;
      };
    };

  in {
    inherit overlays;
    inherit (flake-utils.lib.eachDefaultSystem buildSystem) devShells packages;
  };
}
