"iterate over SQL statements of a DdlObj"

import importlib.util as iu
import logging
import re
import sys
from dataclasses import dataclass
from functools import cached_property
from inspect import signature
from pathlib import Path
from typing import Any, Callable, Iterable, Literal, cast

from sqlparse import split as split_sqls  # type: ignore

from make4db.provider import DDL, DbAccess, PySqlFn

from .obj import DdlObj

logger = logging.getLogger(__name__)


def _clean_sql(sql: str) -> str:
    return sql.rstrip().rstrip(";")


@dataclass
class PyScript:
    path: Path
    fn_name: str = "sql"

    @cached_property
    def _fn(self) -> tuple[Callable[..., Any], Literal[2, 3]]:
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

        match len(signature(f).parameters):
            case 2:
                return (f, 2)
            case 3:
                return (f, 3)
            case _:
                raise TypeError(f"'{self.fn_name}' ('{script}') must accept either 2 or 3 parameters exactly")

    @property
    def fn(self) -> PySqlFn:
        return self._fn[0]

    @property
    def needs_dba(self) -> bool:
        return self._fn[1] == 3

    @property
    def obj_name(self) -> str:
        return f"{self.path.parent.name}.{self.path.stem}"


def _load_from_sql(script: Path, replace: bool) -> Iterable[str]:
    def create_or_replace(ddl: str) -> str:
        if re.search("\\bcreate\\s+or\\s+replace\\b", ddl, flags=re.IGNORECASE) is not None:
            return ddl
        new_ddl = re.sub("\\bcreate(\\s+or\\s+alter\\b)?", "create or replace", ddl, count=1, flags=re.IGNORECASE)
        if new_ddl != ddl:
            logger.info("'create' in '%s' overridden with 'create or replace'", Path)
        return new_ddl

    def identity(x: str) -> str:
        return x

    ddl_upd = create_or_replace if replace else identity
    yield from (ddl_upd(_clean_sql(sql)) for sql in split_sqls(script.read_text(), strip_semicolon=True) if sql.strip() != "")


def itersql(dba: DbAccess, replace: bool, obj: DdlObj) -> Iterable[str]:
    if obj.is_python:
        py = PyScript(obj.ddl_path)
        if py.needs_dba:
            yield from dba.py2sql(cast(Callable[[Any, str, bool], DDL], py.fn), py.obj_name, replace)
        else:
            ddl = cast(Callable[[str, bool], DDL], py.fn)(py.obj_name, replace)
            if isinstance(ddl, str):
                yield _clean_sql(ddl)
            else:
                yield from (_clean_sql(sql) for sql in ddl)
    else:
        yield from _load_from_sql(obj.ddl_path, replace)
