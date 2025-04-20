# make4db

`make` like tool for databases.

Like the traditional `make` tool, **make4db** builds any modified database scripts, in most cases DDLs, and dependent database scripts in dependency order. For example, when a table DDL is modified, its DDL is evaluated, and then any views that reference the modified table are evaluated, and so on.

One key difference between the traditional `make` tool and `db4make` is, that `db4make` does not rely on file timestamps to detect changes; but instead uses cryptographic hashes.

## Features
- build all changed and their dependent objects in the dependency order (`make`)
- build only specific objects and their references (if changed) in the dependency order (`make <target>`)
- touch mode -- mark objects as built, without running SQLs (`make -t`)
- preview mode -- only show objects that would be executed (`make -n`)
- rebuild unconditionally (`make -B`)
- when supported by the DBMS, help obtain object dependencies
- in case of a failure, keep building scripts that are not dependent on the failing scripts (`make -k`)

## Installation

Use `pip` (`pipx` recommended) for installation. In addition to `make4db` package, a database-provider package for `m4db` must be installed. Available database-provider packages:

1. `make4db-duckdb`
1. `make4db-postgres`
1. `make4db-snowflake`

## Usage

`m4db` is the primary tool. It is used for building changed DDLs and their dependent objects in the correct order.

Use `m4db --help` to list all available options. Some of the important options are listed below:

- `--ddl-dir`: root directory containing all DDLs. It is recommended to use VCS such as git to store DDLs
- `--tracking-dir`: a directory to store DDL execution status. Although execution status is considered persistent information, this directory is not typically version-controlled. There might be different tracking directories that represent different environments, such as `dev`, `prod` etc.
- `--out-dir`: directory to DDL execution logs

### Companion tools

Besides the main tool (`m4db`), the following tools are also available:

- `m4db-refs`: show or manage object dependency hierarchy
- `m4db-gc`: garbage collect outdated, orphaned files
- `m4db-dbclean`: allows cleaning up outdated database objects by generating `DROP` statements. Note: only available for some databases
- `m4db-cache`: allows pre-computing cryptographic hash for large repositories

## Storing DDLs
- DDLs are stored as plain text in single-level deep folders.
- Folder names are used to infer schema name, and file names are used to infer object names. File and folder names are always in lower-case, but converted to upper-case to derive schema and object names
- File names consist of a base name and extension.
  - Base name must match the object name (except filename must be all lower-case).
  - File extension must be either `.sql` or `.py`
  - File names that start with `.` (period) are ignored, and so are any `.py` files that start with `_`.
- Files that have `.sql` extension must contain one or more valid SQL statements.
- Files that have `.py` extension must be a top-level Python script and must contain a function named `sql` returning one or more SQL statements as string. The following are the two valid function signatures.

  ```py
  def sql(name: str, replace: bool) -> str | Iterable[str]:
      """Dynamically build and return SQL statement(s)

     Args:
     name: name of the object being created (or replaced). note: name is qualified with the schema name
     replace: true if m4db is running in replace mode, that is, --replace option was specified at run-time

     Returns:
     A single SQL statement as `str`; or multiple SQL statements as `Iterable[str]`
      """
  ```
  ```py
  def sql(session, name: str, replace: bool) -> str | Iterable[str]:
      """Dynamically build and return SQL statement(s)

     Args:
     session: an active database session (must not be closed)
     name: name of the object being created (or replaced). note: name is qualified with the schema name
     replace: true if m4db is running in replace mode, that is, --replace option was specified at run-time

     Returns:
     A single SQL statement as `str`; or multiple SQL statements as `Iterable[str]`
      """
  ```

## Limitations
- only manages schema-level objects (does not manage databases, schemas, or permissions)
- does not manage cross-database objects (assumes databases are "environments")
- object dependency management, depending on the database support, is semi-automatic
- change detection is based on the file content

## Technical details
- Unlike the traditional `make` utility, *make4db* relies on the cryptographic hash of files to detect changes.
- *make4db* is database agnostic and requires separate *database provider module* to function
- *make4db* relies on object references (for example, references of a view being other tables/views) to determine what objects need to be (re)build
  - object references are stored along with the database scripts in a hidden folder (`.m4db` in the project-level folder)
  - `m4db-refs` is a helper tool that can, for selected databases, automatically generate object references
