"Generate SQLs to drop schema objects that don't have a DDL"

import logging
from argparse import ArgumentParser
from pathlib import Path
from typing import Any

from make4db.provider import Feature, SchObj

from .args import add_args
from .dbp import dbp
from .obj import DdlObj
from .util import __version__

logger = logging.getLogger(Path(__file__).stem)


def run(ddl_dir: Path, **conn_args: dict[str, Any]) -> None:
    DdlObj.ddl_dir = ddl_dir

    with dbp.dbacc(conn_args) as dba:
        for sql in dba.drop_except(set(SchObj(o.sch, o.name) for o in DdlObj.all())):
            print(sql + ";")


def getargs() -> dict[str, Any]:
    parser = ArgumentParser(description=__doc__)

    add_args(parser, "ddl_dir")
    dbp.add_db_args(parser)
    parser.add_argument("--version", action="version", version=f"{__version__} (plugin: {dbp.name()}, version: {dbp.version()})")

    return vars(parser.parse_args())


def cli() -> Any:
    "cli entry-point"
    if dbp.supports_feature(Feature.DropDatabaseOrphans):
        return run(**getargs())
    else:
        raise SystemExit(f"{dbp.name} does not support detecting orphan database objects")
