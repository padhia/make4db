import logging
import os
import re
from argparse import ArgumentParser, ArgumentTypeError
from functools import partial
from pathlib import Path
from typing import Any, Callable, Iterable

from .obj import PY_DDL_EXT, SQL_DDL_EXT, DdlObj, Obj
from .util import uniq

logger = logging.getLogger(Path(__file__).stem)


SQL_IDENT_PAT = r"[a-zA-Z_][a-zA-Z_$0-9]*"
OBJ_PAT = re.compile(f"({SQL_IDENT_PAT})\\.({SQL_IDENT_PAT})")


def valid_path(of_type: str, validate: Callable[[Path], bool], v: str) -> Path:
    if validate((p := Path(v).absolute())):
        return p
    raise ArgumentTypeError(f"'{v}' is not an valid {of_type}")


existing_dir = partial(valid_path, "directory", Path.is_dir)
existing_file = partial(valid_path, "file", Path.is_file)


def add_args(parser: ArgumentParser, *args: str) -> None:
    def add_dirarg(*args: Any, **kwargs: Any):
        parser.add_argument(*args, **(dict(metavar="DIR", type=existing_dir) | kwargs))  # type: ignore

    def obj_ref(s: str) -> tuple[str, str] | Path:
        if s.endswith(SQL_DDL_EXT) or s.endswith(PY_DDL_EXT):
            return existing_file(s)

        m = OBJ_PAT.fullmatch(s)
        if m is not None:
            sch, name = m.groups()
            return (sch.lower(), name.lower())

        raise ArgumentTypeError(f"'{s}' is not a valid DDL file or an object name")

    def default_dir(envvar: str) -> Path | None:
        dir_name = os.environ.get(envvar)
        if dir_name is not None:
            if (p := Path(dir_name)).is_dir():
                return p
            else:
                logger.warning(f"Environment variable ${envvar} does not refer to an existing directory; ignored")

        return None

    for arg in args:
        match arg:
            case "ddl_dir":
                ddl_dir = default_dir("MAKE4DB_DDL_DIR")
                add_dirarg(
                    "-S",
                    "--ddl-dir",
                    type=existing_dir,
                    required=ddl_dir is None,
                    default=ddl_dir,
                    help="DDL directory containing <ddl-dir>/<schema>/<obj>.<sql/py> hierarchy (default: $MAKE4DB_DDL_DIR)",
                )
            case "obj+" | "obj*":
                parser.add_argument(
                    "obj_refs",
                    metavar="<FILE>|<OBJ>",
                    type=obj_ref,
                    nargs=arg[-1],
                    help="Object reference, either <sch>.<name> or <path> of the DDL",
                )
            case "cache_dir?" | "cache_dir":
                cache_dir = default_dir("MAKE4DB_CACHE_DIR")
                add_dirarg(
                    "--cache-dir",
                    type=existing_dir,
                    required=cache_dir is None and arg == "cache_dir",
                    default=cache_dir,
                    help="directory that caches DDL hashes (default: $MAKE4DB_CACHE_DIR)",
                )
            case "tracking_dir":
                tracking_dir = default_dir("MAKE4DB_TRACKING_DIR")
                add_dirarg(
                    "-T",
                    "--tracking-dir",
                    type=existing_dir,
                    required=tracking_dir is None,
                    default=tracking_dir,
                    help="folder to track DDL executions (default: $MAKE4DB_TRACKING_DIR)",
                )
            case _:
                raise ValueError(f"Invalid argument name '{arg}' for add_args()")


def validate_objrefs(obj_refs: list[tuple[str, str] | Path], T: type[DdlObj]) -> Iterable[DdlObj]:
    """
    Return iterable of validated object references.
    - An object reference be object name <sch>.<obj> or Path to it's DDL.
    - An object reference is valid if a DDL file (Python or SQL) exists for the object
    """

    def as_obj(ref: tuple[str, str] | Path) -> DdlObj:
        if isinstance(ref, Path):
            if not ref.absolute().is_relative_to(T.ddl_dir):
                raise ValueError(f"Object path: '{ref}' must be relative to '{T.ddl_dir}'")
            obj = T.from_path(ref.absolute())
        else:
            obj = T(ref[0], ref[1])
        if not obj.has_ddl:
            raise ValueError(f"Invalid object '{obj}'; it is missing a DDL")

        return obj

    return uniq(as_obj(x) for x in obj_refs)


def accept_objs(fn: Callable[..., Any]) -> Callable[..., Any]:
    def wrapped(
        obj_refs: list[tuple[str, str] | Path],
        ddl_dir: Path,
        tracking_dir: Path | None = None,
        cache_dir: Path | None = None,
        **kwargs: Any,
    ) -> Any:
        if tracking_dir is None:
            t = DdlObj
            DdlObj.ddl_dir = ddl_dir
            DdlObj.cache_dir = cache_dir
        else:
            t = Obj
            Obj.ddl_dir = ddl_dir
            Obj.cache_dir = cache_dir
            Obj.tracking_dir = tracking_dir

        try:
            return fn(list(validate_objrefs(obj_refs, t)), **kwargs)
        except ValueError as msg:
            raise SystemExit(msg)

    return wrapped
