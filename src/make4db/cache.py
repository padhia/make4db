"update DDL file hash"

import logging
from argparse import ArgumentParser
from pathlib import Path
from typing import Any

from .args import accept_objs, add_args
from .obj import HASH_EXT, DdlObj

logger = logging.getLogger(Path(__file__).stem)


@accept_objs
def main(objs: set[DdlObj]) -> None:
    for o in objs or DdlObj.all():
        digest = o.calc_ddl_hash()
        if digest != o.read_ddl_hash():
            o.path(DdlObj.cache_dir, HASH_EXT).write_text(digest)  # type: ignore
            print(f"{o} hash updated")


def getargs() -> dict[str, Any]:
    parser = ArgumentParser(description=__doc__)
    add_args(parser, "obj*", "ddl_dir", "cache_dir")
    return vars(parser.parse_args())


def cli() -> None:
    "cli entry-point"
    main(**getargs())


if __name__ == "__main__":
    cli()
