"Run DDLs and their dependecies in transitive depedency order"

import logging
import sys
from argparse import ArgumentParser
from enum import StrEnum
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


class Action(StrEnum):
    Build = "build"
    Rebuild = "rebuild"
    Touch = "touch"


class DryRun(StrEnum):
    Name = "name"
    Ddl = "ddl"
    Tree = "tree"
    Quiet = "quiet"


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

    if dry_run is not None:
        return print_plan(dry_run=dry_run, runner=runner, dbp=dbp, replace=replace, do_touch=action is Action.Touch, **conn_args)

    if not runner.affected_objs:
        print("Nothing to make")
        return 0

    if action is Action.Touch:
        return runner.run(with_tracker(print_touched))

    with dbp.dbacc(conn_args) as dba:
        fn = with_obj_runner(dba, replace)
        fn = with_log_writer(out_dir, fn)
        fn = with_tracker(fn)
        return runner.run(fn)


def print_plan(dry_run: DryRun, runner: Runner, dbp: DbProvider, replace: bool, do_touch: bool, **conn_args: Any) -> int:
    def print_obj_name(o: Obj) -> bool:
        print(str(o))
        return True

    match dry_run:
        case DryRun.Quiet:
            return 2 if runner.affected_objs else 0

        case DryRun.Name:
            return runner.run(print_touched if do_touch else print_obj_name)

        case DryRun.Tree:
            for o in only_roots(runner.targets, lambda o: o.deps):
                for trunk, x in treeiter(o, lambda x: x.rdeps, width=1):
                    print(f"{trunk}{x}")
            return 0

        case DryRun.Ddl:
            with dbp.dbacc(conn_args) as dba:

                def print_obj_sqls(obj: Obj) -> bool:
                    try:
                        for sql in itersql(dba, replace, obj):
                            print(sql + "\n;")
                        return True
                    except Exception as err:
                        logger.error(f"SQL generation failed for '{obj}', error: {err}")
                        return False

                return runner.run(print_obj_sqls)


def print_touched(obj: Obj) -> bool:
    print(f"touch '{obj.tracking_path}'")
    return True


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
        try:
            sqls = list(itersql(dba, replace, obj))
        except Exception as err:
            logger.error(f"SQL generation failed for '{obj}', error: {err}")
            return False

        return all(execsql(s, output) for s in sqls)

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
        help="do not run; if 'quiet' and there are objects that need building exit with RC=2; else print affected objects/DDLs/tree",
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
