"load a Db Provider instance"

import importlib.metadata as im
import importlib.util as iu
import logging
import os
from argparse import ArgumentParser
from dataclasses import dataclass
from typing import Any, Callable, Iterable, Self, TextIO

from make4db.provider import DDL, DbAccess, DbProvider, Feature, SchObj

logger = logging.getLogger(__name__)
KNOWN_PROVIDERS = ["make4db-snowflake", "make4db-duckdb", "make4db-postgres"]


@dataclass
class DummyAccess(DbAccess):
    @property
    def conn(self) -> None:
        raise NotImplementedError("Dummy Database Access provider has no implementation")

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *args: Any, **kwargs: Any) -> None:
        pass

    def py2sql(self, fn: Callable[[Any, str, bool], DDL], object: str, replace: bool) -> Iterable[str]:
        ddl = fn(self.conn, object, replace)
        if isinstance(ddl, str):
            yield ddl
        else:
            yield from ddl

    def execsql(self, sql: str, output: TextIO) -> None:
        pass

    def iterdep(self, objs: Iterable[SchObj]) -> Iterable[tuple[SchObj, SchObj]]:
        raise NotImplementedError("Dummy Database Access provider has no implementation")

    def drop_except(self, objs: set[SchObj]) -> Iterable[str]:
        raise NotImplementedError("Dummy Database Access provider has no implementation")


@dataclass
class DummyProvider(DbProvider):
    def dbacc(self, conn_args: dict[str, Any]) -> DummyAccess:
        raise NotImplementedError("Dummy Database Access provider has no implementation")

    def add_db_args(self, parser: ArgumentParser) -> None:
        pass

    def version(self) -> str:
        return "0.1.0"

    def name(self) -> str:
        return "dummy"

    def supports_feature(self, feature: Feature) -> bool:
        return False


def _find_provider() -> str | None:
    logger.debug("searching for a make4db provider from: %s", [m.name for m in im.distributions()])
    providers = [m.name for m in im.distributions() if m.name in KNOWN_PROVIDERS]

    if len(providers) > 1:
        logger.error("More than one providers found: %s", providers)
        return None

    if not providers:
        return None

    return providers[0].replace("-", "_")


def _get_provider() -> DbProvider:
    provider_module = os.environ.get("MAKE4DB_PROVIDER") or _find_provider()

    if provider_module is None:
        logger.warning('Environment variable MAKE4DB_PROVIDER is unset; loading "dummy" provider')
        return DummyProvider()

    spec = iu.find_spec(provider_module)
    if spec is None or spec.loader is None:
        raise SystemExit(f'Database provider "{provider_module}" could not be loaded')

    module = iu.module_from_spec(spec)
    spec.loader.exec_module(module)

    try:
        return getattr(module, "get_provider")()
    except AttributeError:
        raise SystemExit(f'"{provider_module}" does not contain get_provider() function')


dbp = _get_provider()
