# make4db

make like tool for databases. **make4db** uses cryptographic-hash, instead of last-modified timestamp, to detect file changes

## Features
- build all changed and their dependent objects in the dependency order (`make`)
- build only specific objects and their references (if changed) in the dependency order (`make <target>`)
- touch mode -- mark objects as built, without running SQLs (`make -t`)
- preview mode -- only show objects that would be executed (`make -n`)
- rebuild unconditionally (`make -B`)
- when supported by the DBMS, help obtain object dependencies
- in case of a failure, keep building scripts that are not dependent on the failing scripts (`make -k`)

## Limitations
- only manages schema level objects (does not manage databases, schemas or permissions)
- strict naming conventions: schema names must be used as folder names, object names as file names
- does not manage cross database objects (assumes databases are "environments")
- object dependency management, depending on the database support, is semi-automatic
- change detection is based on the file content

## Commands
- `m4db`: Evaluates and builds changed DDLs and their dependent objects
- `m4db-refs`: list and/or update (when supported by the DBMS) object references (dependencies)
- `m4db-cache`: if set up to use cache, update cryptographic hash values of DDLs
- `m4db-gc`: garbage collect meta items that are no longer in use

Use `--help` option to print detailed usage information of each of the above command.

## Technical details
- Unlike the traditional `make` utility, *make4db* relies on cryptographic hash of files to detect changes.
  - When managing a large number of files, the hash can be pre-computed to avoid computing hash during each run.
- *make4db* is database agnostic and requires separate *database provider module* to function
- *make4db* relies on object references (for example, references of a view being other tables/views) to determine what objects need to be (re)build
  - object references are stored along with the database scripts in a hidden folder
  - `m4db-refs` is a helper tools that can, for selected databases, automatically generate object references
