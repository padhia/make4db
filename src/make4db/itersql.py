"iterate over SQL statements of a DdlObj"

import importlib.util as iu
import logging
import re
import sys
from dataclasses import dataclass
from functools import cached_property
from inspect import signature
from pathlib import Path
from typing import Any, Callable, Iterable

from sqlparse import split as split_sqls  # type: ignore

from make4db.provider import DbAccess

from .obj import DdlObj

logger = logging.getLogger(__name__)


@dataclass
class PyScript:
    path: Path
    fn_name: str = "sql"

    @cached_property
    def fn(self) -> Callable[..., Any]:
        "load named Python script and return the function"
        script = self.path.absolute()

        sys.path.insert(0, str(self.path.parent))

        spec = iu.find_spec(self.path.stem)
        if spec is None or spec.loader is None:
            raise TypeError(f'Script "{self.path.stem}" could not be loaded')

        module = iu.module_from_spec(spec)
        spec.loader.exec_module(module)

        try:
            f = getattr(module, self.fn_name)
        except AttributeError:
            raise ValueError(f"{script} does not contain '{self.fn_name}' function")

        if not callable(f):
            raise TypeError(f"'{self.fn_name}' ('{script}') is invalid; must be a function")

        if len(signature(f).parameters) not in [2, 3]:
            raise TypeError(f"'{self.fn_name}' ('{script}') must accept either 2 or 3 parameters exactly")

        return f

    @property
    def obj_name(self) -> str:
        return f"{self.path.parent.name}.{self.path.stem}"

    @property
    def is_dba_fn(self) -> bool:
        "returns True if the function needs to be called by DbAccess (that is, takes 3 arguments)"
        return len(signature(self.fn).parameters) == 3


def _load_from_sql(script: Path, replace: bool) -> Iterable[str]:
    def create_or_replace(ddl: str) -> str:
        new_ddl = re.sub("\\bcreate\\b(?!\\s+or\\s+replace\\b)", "create or replace", ddl, count=1, flags=re.IGNORECASE)
        if new_ddl != ddl:
            logger.info("'create' in '%s' overridden with 'create or replace'", Path)
        return new_ddl

    def identity(x: str) -> str:
        return x

    ddl_upd = create_or_replace if replace else identity
    yield from (ddl_upd(sql) for sql in split_sqls(script.read_text(), strip_semicolon=True) if sql.strip() != "")


def itersql(dba: DbAccess, replace: bool, obj: DdlObj) -> Iterable[str | None]:
    if obj.is_python:
        py = PyScript(obj.ddl_path)
        sqls = dba.py2sql(py.fn, py.obj_name, replace) if py.is_dba_fn else py.fn(py.obj_name, replace)
        yield from (sql.rstrip().rstrip(";") for sql in sqls)
    else:
        yield from _load_from_sql(obj.ddl_path, replace)
