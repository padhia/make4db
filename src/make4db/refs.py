"List object references, or update object references using snowflake.account_usage.object_dependecies"

import logging
from argparse import ArgumentParser
from enum import StrEnum, auto
from pathlib import Path
from typing import Any, TypeAlias

from yappt import treeiter

from make4db.provider import Feature, SchObj

from .args import accept_objs, add_args
from .dbp import dbp
from .obj import DdlObj
from .util import __version__, only_roots

logger = logging.getLogger(Path(__file__).stem)
Refs: TypeAlias = dict[DdlObj, set[DdlObj]]


class Cmd(StrEnum):
    SHOW = auto()
    INVERT = auto()
    ADD = auto()
    DEL = auto()
    REFRESH = auto()
    DIFF = auto()


@accept_objs
def run(objs: list[DdlObj], all_ddls: bool, cmd: Cmd, **conn_args: dict[str, Any]) -> None:
    if bool(objs) and all_ddls:
        raise SystemExit("--all not valid when object(s) also specified")

    match cmd:
        case Cmd.SHOW | Cmd.INVERT:
            _objs = set(objs or DdlObj.all())
            if cmd == Cmd.INVERT:
                nodes = (x for r in only_roots(_objs, lambda o: o.deps) for x in treeiter(r, lambda o: o.rdeps))
            else:
                nodes = (x for r in only_roots(_objs, lambda o: o.rdeps) for x in treeiter(r, lambda o: o.deps))

            for pfx, o in nodes:
                print(f"{pfx}{o}")

        case Cmd.ADD | Cmd.DEL:
            if len(objs) < 2:
                raise SystemExit("must specify a <target> and at least one <ref>")
            tgt = objs[0]
            refs = set(objs[1:])

            curr_deps = set(tgt.deps)
            new_deps = (curr_deps | refs) if cmd == Cmd.ADD else (curr_deps - refs)
            if dep_changes(tgt, new_deps):
                tgt.update_deps(new_deps)

        case Cmd.REFRESH:
            if not objs:
                if all_ddls:
                    objs = DdlObj.all()
                else:
                    raise SystemExit("no objects specified; must specify --all to refresh all objects")
            for o, rs in build_refs(objs, **conn_args).items():
                if dep_changes(o, rs):
                    o.update_deps(rs)

        case Cmd.DIFF:
            for o, rs in build_refs(objs or DdlObj.all(), **conn_args).items():
                dep_changes(o, rs)


def build_refs(objs: list[DdlObj], **conn_args: dict[str, Any]) -> Refs:
    def mk_obj(o: SchObj) -> DdlObj:
        return DdlObj(o.sch.lower(), o.obj.lower())

    refs: dict[DdlObj, set[DdlObj]] = {o: set() for o in objs}
    with dbp.dbacc(conn_args) as dba:
        for obj_g, obj_d in dba.iterdep(SchObj(o.sch, o.name) for o in objs):
            refs[mk_obj(obj_g)].add(mk_obj(obj_d))

    return refs


def dep_changes(o: DdlObj, new_deps: set[DdlObj]) -> bool:
    curr_deps = set(o.deps)
    if curr_deps == new_deps:
        return False

    print(f"Dependencies changes for {o}:")
    for x in new_deps - curr_deps:
        print(f"  +{x}")
    for x in curr_deps - new_deps:
        print(f"  -{x}")

    return True


def getargs() -> dict[str, Any]:
    parser = ArgumentParser(description=__doc__)

    add_args(parser, "obj*", "ddl_dir")

    g = parser.add_argument_group("command")
    x = g.add_mutually_exclusive_group()
    x.add_argument(
        "--show", action="store_const", dest="cmd", const=Cmd.SHOW, default=Cmd.SHOW, help="show dependencies as a tree"
    )
    x.add_argument(
        "-T",
        "--invert",
        action="store_const",
        dest="cmd",
        const=Cmd.INVERT,
        help="show dependencies as an inverted tree (downstream objects shown as child nodes)",
    )
    x.add_argument(
        "-a", "--add", action="store_const", dest="cmd", const=Cmd.ADD, help="add dependencies (usage: <target> <dep>...)"
    )
    x.add_argument("--rm", action="store_const", dest="cmd", const=Cmd.DEL, help="remove dependencies (usage: <target> <dep>...)")
    if dbp.supports_feature(Feature.AutoRefresh):
        x.add_argument("--refresh", action="store_const", dest="cmd", const=Cmd.REFRESH, help="refresh references (dependencies)")
        x.add_argument("--diff", action="store_const", dest="cmd", const=Cmd.DIFF, help="do not refresh dependencies, but show only the changes")

    parser.add_argument(
        "--all",
        dest="all_ddls",
        action="store_true",
        help="when no objects are specified, use all objects from the DDL repository",
    )

    dbp.add_db_args(parser)
    parser.add_argument("--version", action="version", version=f"{__version__} (plugin: {dbp.name()}, version: {dbp.version()})")

    return vars(parser.parse_args())


def cli() -> Any:
    "cli entry-point"
    return run(**getargs())
