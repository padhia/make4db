"utility functions"

import logging
from typing import Callable, Iterable, TypeVar

T = TypeVar("T")
__version__ = "0.1.3"


def only_roots(objs: set[T], parents: Callable[[T], Iterable[T]]) -> Iterable[T]:
    "return only root elements, that is, only those elements which don't have any ancestor as one of the roots"

    def has_root_ancestor(os: Iterable[T]) -> bool:
        return any(o in objs or has_root_ancestor(parents(o)) for o in os)

    yield from (o for o in objs if not has_root_ancestor(parents(o)))


def uniq(xs: Iterable[T]) -> Iterable[T]:
    "iterate over an existing iterable after removing any element that might occur more than once"
    seen: set[T] = set()

    for x in xs:
        if x not in seen:
            seen.add(x)
            yield x


def traverse(objs: Iterable[T], children: Callable[[T], list[T]]) -> Iterable[T]:
    "traverse tree for each objs, eliminating any duplicate occurrences"

    def recurse(o: T) -> Iterable[T]:
        for x in children(o):
            yield from recurse(x)
        yield o

    yield from uniq(d for o in objs for d in recurse(o))


def init_logging(level: int = logging.WARNING, module_name: str | None = None) -> logging.Logger:
    h = logging.StreamHandler()
    h.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))

    if module_name is None:
        module_name = ".".join(__name__.split(".")[:-1])  # parent module of this module

    logger = logging.getLogger(module_name)
    logger.addHandler(h)
    logger.setLevel(level)

    return logger


init_logging()
