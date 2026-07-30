# make4db

`make`-like tool for databases.

Like the traditional `make` tool, **make4db** builds only outdated database scripts (typically DDLs), and any dependent database scripts in the dependency order. For example, when a table DDL is modified, its DDL is rerun first, then the DDLs of referencing views are rerun, and then any views that reference those views are rerun, and so on until all dependencies have been updated.

One key difference between the traditional `make` tool and `make4db` is that `make4db` relies on cryptographic hashes to detect changes instead of file timestamps.

## Features

- Build all changed objects and their dependents in dependency order
- Build only specific objects and their dependents (if changed) in dependency order
- **Touch mode** — mark objects as built without running SQL (`-t`)
- **Preview mode** — show what would be executed without running anything (`-n`)
    - `name` (default): print object names
    - `ddl`: print the SQL that would be executed
    - `tree`: print dependency tree
    - `quiet`: exit with code 2 if any objects need building, 0 otherwise (useful in CI pipelines)
- **Replace mode** — rewrite `CREATE` as `CREATE OR REPLACE` in `.sql` files (`-R`)
- Rebuild unconditionally (`-B`)
- Automatically determine object dependencies for supported databases
- Keep building unaffected objects when a dependency fails (`-k`)

## Installation

Use `pip` (`uv` or `pix` recommended) for installation. In addition to `make4db`, install a database-provider package:

| Package             | Database   |
| ------------------- | ---------- |
| `make4db-duckdb`    | DuckDB     |
| `make4db-postgres`  | PostgreSQL |
| `make4db-snowflake` | Snowflake  |

## Usage

The main executable is `m4db`. It builds any changed DDLs and their dependent objects in dependency order.

```
m4db [options] [<FILE>|<OBJ> ...]
```

When one or more object references are given, only those objects (and their dependents, if changed) are built. Without arguments, all changed objects are processed.

Run `m4db --help` for a full option listing. Key options:

| Option                     | Description                                                             |
| -------------------------- | ----------------------------------------------------------------------- |
| `-S`, `--ddl-dir DIR`      | Root directory containing all DDL files                                 |
| `-T`, `--tracking-dir DIR` | Directory to store build-status tracking files                          |
| `-O`, `--out-dir DIR`      | Directory to write per-object execution logs                            |
| `-n`, `--dry-run [MODE]`   | Preview mode; `MODE` is one of `name` (default), `ddl`, `tree`, `quiet` |
| `-t`, `--touch`            | Mark objects as built without executing SQL                             |
| `-B`, `--rebuild`          | Rebuild targets unconditionally                                         |
| `-R`, `--replace`          | Rewrite `CREATE` as `CREATE OR REPLACE` in SQL files                    |

### Environment variables

The three directory options can be set via environment variables to avoid repeating them on every invocation:

| Variable               | Corresponding option |
| ---------------------- | -------------------- |
| `MAKE4DB_DDL_DIR`      | `--ddl-dir`          |
| `MAKE4DB_TRACKING_DIR` | `--tracking-dir`     |
| `MAKE4DB_CACHE_DIR`    | `--cache-dir`        |

### Companion tools

| Tool           | Description                                                                                     |
| -------------- | ----------------------------------------------------------------------------------------------- |
| `m4db-refs`    | Show or manage the object dependency hierarchy                                                  |
| `m4db-gc`      | Remove orphaned tracking, cache, and log files                                                  |
| `m4db-dbclean` | Generate `DROP` statements for objects no longer in the DDL directory (selected databases only) |
| `m4db-cache`   | Pre-compute cryptographic hashes for large repositories                                         |

## Storing DDLs

- DDLs live in a single-level folder hierarchy: `<ddl-dir>/<schema>/<object>.<ext>`
- Folder names map to schema names; file stems map to object names. Both are stored in lower-case and converted to upper-case at runtime.
- Valid extensions are `.sql` and `.py`. Files starting with `.` are ignored; `.py` files starting with `_` are also ignored.

### SQL files (`.sql`)

Each `.sql` file contains one or more SQL statements for a single database object. `.sql` files are processed as **Jinja2 templates** before execution, which allows dynamic content without switching to a full Python script.

Available template variables:

| Variable          | Type     | Description                                             |
| ----------------- | -------- | ------------------------------------------------------- |
| `this`            | object   | The current object; renders as `<schema>.<name>`        |
| `this.sch`        | string   | Schema name                                             |
| `this.name`       | string   | Object name                                             |
| `ref("sch.name")` | function | Renders `sch.name` **and** registers it as a dependency |
| `env_var`         | mapping  | OS environment variables (e.g. `env_var.MY_VAR`)        |

Example — `sch2/some_table.sql`:

```sql
create or replace table {{ this }} (
    db_name  varchar(255) not null default '{{ env_var.TARGET_DB }}',
    sch_name varchar(255) not null default '{{ this.sch }}',
    obj_name varchar(255) not null default '{{ this.name }}'
);
```

Example — `sch2/some_view.sql`:

```sql
create or replace view {{ this }} as
select *
from {{ ref("sch2.some_table") }}
join {{ ref("sch1.other_view") }} using (id);
```

The `ref()` call both renders the object name and automatically records `sch2.some_table` as a dependency of `sch2.some_view`, so the view is rebuilt whenever the table changes.

### Python files (`.py`)

A `.py` file must be a top-level Python module containing a function named `sql`. Two signatures are supported:

```py
# without database access
def sql(name: str, replace: bool) -> str | Iterable[str]: ...

# with an active database session
def sql(session, name: str, replace: bool) -> str | Iterable[str]: ...
```

Parameters:

- `name` — fully-qualified object name (`schema.object`)
- `replace` — `True` when `m4db` is run with `--replace`
- `session` — an active database session provided by the database-provider plugin

The function must return either a single SQL string or an iterable of SQL strings.

When both `.py` and `.sql` files exist for the same object, the `.py` file takes precedence.

### Dependency files

Dependencies are stored in `.m4db/<schema>/<object>.deps` inside the DDL directory. Each line is a `schema.object` reference. These files are managed automatically when using Jinja2 `ref()` calls or `m4db-refs --refresh`; you can also edit them manually.

## Limitations

- Manages schema-level objects only; does not manage databases, schemas, or permissions
- Does not manage cross-database objects
- Dependency detection is semi-automatic depending on database support
- Change detection is based on file content (not runtime schema state)

## Technical notes

- Change detection uses the [BLAKE2b](https://www.blake2.net/) cryptographic hash of the DDL file content plus a salt derived from the tracking state of dependencies. This means an object is rebuilt whenever either its own DDL or any upstream DDL changes.
- `make4db` is database-agnostic and requires a separate database-provider plugin to run.
- Object references (dependencies) are stored in `.m4db/` inside the DDL directory and are intended to be version-controlled alongside the DDL files.
