"garbage collect unneeded files from meta, tracking and cache directories"

import logging
from argparse import ArgumentParser
from itertools import chain
from pathlib import Path
from typing import Any, Iterable

from .args import add_args, existing_dir
from .obj import DEPS_EXT, HASH_EXT, META_SUBDIR, SALT_EXT, TRK_EXT, Obj

logger = logging.getLogger(Path(__file__).stem)
_dummy_obj = Obj("", "")


def main(dry_run: bool, ddl_dir: Path, tracking_dir: Path, cache_dir: Path | None, out_dir: Path | None) -> None:
    Obj.ddl_dir = ddl_dir
    Obj.cache_dir = cache_dir

    objs = set((o.sch, o.name) for o in Obj.all())

    rm_iters = [removable_files(objs, tracking_dir, [TRK_EXT, SALT_EXT])]
    if (ddl_dir / META_SUBDIR).is_dir():
        rm_iters.append(removable_files(objs, ddl_dir / META_SUBDIR, [DEPS_EXT]))
    if cache_dir is not None:
        rm_iters.append(removable_files(objs, cache_dir, [HASH_EXT]))
    if out_dir is not None:
        rm_iters.append(removable_files(objs, out_dir, [".log"]))

    removables = sorted(chain(*rm_iters), key=lambda x: x.stem)  # sort files to be deleted by object name
    files = (p for p in removables if p.is_file())
    dirs = (p for p in removables if p.is_dir())
    rm_all(chain(files, dirs), dry_run=dry_run)


def removable_files(sch_obj: set[tuple[str, str]], dir_path: Path, valid_exts: list[str]) -> Iterable[Path]:
    "returns an Iterable of files to be cleaned"

    valid_sch = set(s for s, _ in sch_obj)

    for sch_dir in dir_path.iterdir():
        if sch_dir.is_file():
            yield sch_dir
        elif sch_dir.name not in valid_sch:
            yield from sch_dir.iterdir()
            yield sch_dir
        else:
            for f in sch_dir.iterdir():
                if (sch_dir.name, f.stem) not in sch_obj or f.suffix not in valid_exts:
                    yield f


def rm_all(ps: Iterable[Path], dry_run: bool):
    for p in ps:
        if dry_run:
            print(f"{p} will be removed")
        else:
            if p.is_dir():
                p.rmdir()
            else:
                p.unlink()
            print(f"{p} removed")


def getargs() -> dict[str, Any]:
    parser = ArgumentParser(description=__doc__)

    g = parser.add_argument_group("locations")
    add_args(g, "ddl_dir", "cache_dir?", "tracking_dir")  # type: ignore
    g.add_argument("-O", "--out-dir", metavar="DIR", type=existing_dir, help="folder to store DDL execution logs")

    parser.add_argument("-n", "--dry-run", action="store_true", help="Only print, but not remove, files")

    return vars(parser.parse_args())


def cli() -> None:
    "cli entry-point"
    main(**getargs())


if __name__ == "__main__":
    cli()
