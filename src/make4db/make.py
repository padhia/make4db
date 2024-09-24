"Run DDLs and their dependecies in transitive depedency order"

import logging
import sys
from argparse import ArgumentParser
from enum import Enum
from pathlib import Path
from typing import Any, Callable, TextIO

from yappt import treeiter

from make4db.provider import DbAccess, DbProvider

from .args import accept_objs, add_args, existing_dir
from .dbp import dbp
from .itersql import itersql
from .obj import Obj
from .runner import Runner
from .util import __version__, init_logging, only_roots

logger = logging.getLogger(__name__)


class Action(str, Enum):
    Build = "build"
    Rebuild = "rebuild"
    Touch = "touch"


class DryRun(str, Enum):
    Name = "name"
    Ddl = "ddl"
    Tree = "tree"


@accept_objs
def run(
    objs: list[Obj],
    replace: bool,
    out_dir: Path | None,
    dry_run: DryRun | None,
    action: Action,
    loglevel: int = logging.WARNING,
    **conn_args: dict[str, Any],
) -> int:
    init_logging(loglevel)

    _objs = set(objs or Obj.all())

    if action is Action.Rebuild:
        if dry_run is not None:
            Obj.newly_salted = _objs
        else:
            for o in _objs:
                o.refresh_salt()
        runner = Runner(set(Obj.all()))
    else:
        runner = Runner(_objs)

    if not runner.affected_objs:
        print("Nothing to make")
        return 0

    if dry_run is not None:
        return print_plan(dry_run=dry_run, runner=runner, dbp=dbp, replace=replace, is_touch=action is Action.Touch, **conn_args)

    if action is Action.Touch:
        return runner.run(with_tracker(with_true(lambda o: print(f"touch '{o.tracking_path}'"))))

    with dbp.dbacc(conn_args) as dba:
        fn = with_obj_runner(dba, replace)
        fn = with_log_writer(out_dir, fn)
        fn = with_tracker(fn)
        return runner.run(fn)


def print_plan(dry_run: DryRun, runner: Runner, dbp: DbProvider, replace: bool, is_touch: bool, **conn_args: Any) -> int:
    match dry_run:
        case DryRun.Name:
            return runner.run(with_true(lambda o: print(f"touch '{o.tracking_path}'" if is_touch else str(o))))

        case DryRun.Tree:
            for o in only_roots(runner.targets, lambda o: o.rdeps):
                for trunk, x in treeiter(o, lambda x: x.deps, width=1):
                    print(trunk + (f"\033[91m{x}\033[0m" if x in runner.targets else str(x)))
            return 0

        case DryRun.Ddl:
            with dbp.dbacc(conn_args) as dba:

                def print_obj_sqls(o: Obj) -> None:
                    for sql in itersql(dba, replace, o):
                        if sql is not None:
                            print(sql + "\n;")

                return runner.run(with_true(print_obj_sqls))


def with_true(fn: Callable[[Obj], None]) -> Callable[[Obj], bool]:
    def wrapped(obj: Obj) -> bool:
        fn(obj)
        return True

    return wrapped


def with_obj_runner(dba: DbAccess, replace: bool) -> Callable[[Obj, TextIO], bool]:
    def execsql(sql: str, output_file: TextIO) -> bool:
        "execute SQL by forwarding the rquest to Database Provider"

        logger.debug("Running SQL: %s", sql)
        print(sql + "\n;", file=output_file)

        try:
            dba.execsql(sql, output_file)
            return True
        except Exception as err:
            logger.error(err)
            return False

    def fn_(obj: Obj, output: TextIO) -> bool:
        return all(execsql(s, output) if s is not None else False for s in itersql(dba, replace, obj))

    return fn_


def with_log_writer(out_dir: Path | None, fn: Callable[[Obj, TextIO], bool]) -> Callable[[Obj], bool]:
    "transform runner to write to log directory if one is available, otherwise write to stdout"
    if out_dir is None:
        return lambda o: fn(o, sys.stdout)

    def fn_(o: Obj) -> bool:
        with o.path(out_dir, ".log").open("w") as f:
            return fn(o, f)

    return fn_


def with_tracker(fn: Callable[[Obj], bool]) -> Callable[[Obj], bool]:
    "update tracking information after successful execution"

    def fn_(o: Obj) -> bool:
        if fn(o):
            o.refresh_digest()
            return True
        else:
            logger.debug(f"{fn.__name__}({o}) failed, skipped updating tracking info")
            return False

    return fn_


def getargs() -> dict[str, Any]:
    parser = ArgumentParser(description=__doc__)

    g = parser.add_argument_group("locations")
    add_args(g, "ddl_dir", "cache_dir?", "tracking_dir")  # type: ignore
    g.add_argument("-O", "--out-dir", metavar="DIR", type=existing_dir, help="folder to store DDL execution logs")

    add_args(parser, "obj*")
    parser.add_argument("-R", "--replace", action="store_true", help="change 'create' in DDL text with 'create or replace'")

    parser.add_argument(
        "-n",
        "--dry-run",
        nargs="?",
        const=DryRun.Name,
        type=DryRun,
        choices=[x.value for x in DryRun],
        help="Only print, but not run, affected objects/DDLs/tree",
    )

    x = parser.add_mutually_exclusive_group()
    x.add_argument(
        "-B",
        "--rebuild",
        action="store_const",
        dest="action",
        const=Action.Rebuild,
        default=None,
        help="rebuild targets unconditionally",
    )
    x.add_argument(
        "-t", "--touch", action="store_const", dest="action", const=Action.Touch, help="touch targets instead of remaking them"
    )

    dbp.add_db_args(parser)
    parser.add_argument("--version", action="version", version=f"{__version__} (plugin: {dbp.name()}, version: {dbp.version()})")

    return vars(parser.parse_args())


def cli() -> None:
    "cli entry-point"
    return run(**getargs())
