"Class that represents a SQL object"

from dataclasses import dataclass
from datetime import datetime
from functools import cached_property
from hashlib import blake2b, file_digest
from logging import getLogger
from pathlib import Path
from typing import Any, ClassVar, Iterable, Self

from .util import uniq

TRK_EXT = ".trk"
SQL_DDL_EXT = ".sql"
PY_DDL_EXT = ".py"
DEPS_EXT = ".deps"
HASH_EXT = ".hash"
SALT_EXT = ".salt"
META_SUBDIR = ".m4db"

logger = getLogger(__name__)
_salt = int(datetime.today().timestamp()).to_bytes(16)


def _sane_path(p: Path) -> Path:
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


@dataclass(frozen=True)
class DdlObj:
    ddl_dir: ClassVar[Path]
    cache_dir: ClassVar[Path | None] = None
    _all: ClassVar[list[Self] | None] = None

    sch: str
    name: str
    pinned_ext: str | None = None

    def path(self, dir_name: Path, ext: str) -> Path:
        return dir_name / self.sch / f"{self.name}{ext}"

    @property
    def deps_path(self) -> Path:
        return self.path(self.ddl_dir / META_SUBDIR, DEPS_EXT)

    @cached_property
    def _ddl_path(self) -> Path | None:
        "returns validated DDL path"
        if self.pinned_ext is not None:
            return p if (p := self.path(self.ddl_dir, self.pinned_ext)).is_file() else None

        if (p := self.path(self.ddl_dir, PY_DDL_EXT)).is_file():
            if self.path(self.ddl_dir, SQL_DDL_EXT).is_file():
                logger.warning(f"{self} has both, .py and .sql, DDLs available; only .py DDL will be considered")
            return p

        return p if (p := self.path(self.ddl_dir, SQL_DDL_EXT)).is_file() else None

    @property
    def ddl_path(self) -> Path:
        "returns validated DDL path"
        if self._ddl_path is None:
            raise FileNotFoundError(f"No DDL was found for {self}")
        return self._ddl_path

    @property
    def has_ddl(self) -> bool:
        "return True if object has a DDL file that exists"
        return self._ddl_path is not None

    @property
    def is_python(self) -> bool:
        return self.ddl_path.suffix == PY_DDL_EXT

    def write(self, path: Path, data: str | Iterable[str]) -> None:
        text = data if isinstance(data, str) else "\n".join(data)
        _sane_path(path).write_text(text + "\n")

    @cached_property
    def ddl_hash(self) -> str:
        digest = self.read_ddl_hash()
        if digest is None:
            digest = self.calc_ddl_hash()
            if self.cache_dir is not None:
                self.path(self.cache_dir, HASH_EXT).write_text(digest)

        return digest

    def calc_ddl_hash(self) -> str:
        with self.ddl_path.open("rb") as f:
            return file_digest(f, "blake2b").hexdigest()

    def read_ddl_hash(self) -> str | None:
        if self.cache_dir is not None and (p := self.path(self.cache_dir, HASH_EXT)).is_file():
            return p.read_text().strip()
        return None

    @cached_property
    def deps(self) -> list[Self]:
        "return dependencies (upstream objects)"

        def dep_obj(name: str) -> Self | None:
            try:
                dep = self.parse(name)
            except ValueError:
                logger.error(f"'{self}' has an invalid dependency specification '{name}'; must be in <sch>.<obj> format")
                return None

            if not dep.has_ddl:
                logger.info("Ignoring non-existing dependency '%s' of '%s'", name, self)
                return None

            return dep

        try:
            deps_text = self.deps_path.read_text()
            return sorted(uniq(d for x in deps_text.splitlines() if (d := dep_obj(x)) is not None))
        except FileNotFoundError:
            return list()

    @property
    def rdeps(self) -> list[Self]:
        "reverse dependencies (downstream objects)"
        return sorted(uniq(x for x in self.all() if self in x.deps))

    def update_deps(self, deps: set[Self]) -> None:
        if deps:
            self.write(self.deps_path, (str(x) for x in sorted(deps)))
        else:
            self.deps_path.unlink(missing_ok=True)

    def __hash__(self) -> int:
        return hash((self.sch, self.name))

    def __str__(self):
        return f"{self.sch}.{self.name}"

    def __eq__(self, other: Any) -> bool:
        return isinstance(other, type(self)) and (self.sch, self.name) == (other.sch, other.name)

    def __lt__(self, other: Self) -> bool:
        return (self.sch, self.name) < (other.sch, other.name)

    @classmethod
    def from_path(cls: type[Self], p: Path) -> Self:
        if p.suffix not in [PY_DDL_EXT, SQL_DDL_EXT]:
            raise ValueError("DDL Path must have an extension of either .py or .sql")
        return cls(p.parent.name, p.stem, p.suffix)

    @classmethod
    def parse(cls: type[Self], name: str) -> Self:
        sch, name = name.lower().strip().split(".")
        return cls(sch, name)

    @classmethod
    def parse_(cls: type[Self], *name: str) -> Iterable[Self]:
        yield from (cls.parse(n) for n in name)

    @classmethod
    def roots(cls: type[Self], of: set[Self] | None = None) -> Iterable[Self]:
        all_roots = (x for x in cls.all() if len(x.rdeps) == 0)

        if of is None:
            yield from all_roots
            return

        def has_dep(o: Self, nodes: list[Self]) -> bool:
            return o in nodes or any(has_dep(o, n.deps) for n in nodes)

        yield from (r for r in all_roots if any(has_dep(o, r.deps) for o in of))

    @classmethod
    def all(cls: type[Self]) -> list[Self]:
        """
        iterate through all objects by scanning all valid DDL files

        A valid DDL file is:
        - a file (regular or symlink)
        - at a depth of 1 directory level (which corresponds to schema)
        - doesn't start with ".", and for Python DDLs, it doesn't start with "_"
        """

        if cls._all is None:

            def is_ddl(f: Path) -> bool:
                return (
                    f.is_file()
                    and f.suffix in [PY_DDL_EXT, SQL_DDL_EXT]
                    and not (f.name.startswith(".") or f.name.startswith("_") and f.suffix == PY_DDL_EXT)
                )

            ddl_dirs = (d for d in cls.ddl_dir.iterdir() if d.is_dir() and not d.name.startswith("."))
            cls._all = list(uniq(cls.from_path(f) for d in ddl_dirs for f in d.iterdir() if is_ddl(f)))

        return cls._all


@dataclass(frozen=True, eq=False)
class TrackedObj(DdlObj):
    tracking_dir: ClassVar[Path]
    newly_salted: ClassVar[set[Self]] = set()

    @property
    def tracking_path(self) -> Path:
        return self.path(self.tracking_dir, TRK_EXT)

    @property
    def salt(self) -> bytes:
        if self in self.newly_salted:
            return _salt
        if (p := self.path(self.tracking_dir, SALT_EXT)).is_file():
            return p.read_bytes()
        return bytes()

    def refresh_salt(self) -> None:
        _sane_path(self.path(self.tracking_dir, SALT_EXT)).write_bytes(_salt)

    @property
    def digest(self) -> bytes:
        "returns digest of DDL+salt and recursively all dependencies"
        h = blake2b(self.ddl_hash.encode(), salt=self.salt)
        for d in self.deps:
            h.update(d.digest)
        return h.digest()

    def refresh_digest(self):
        if self.must_build:
            _sane_path(self.tracking_path).write_bytes(self.digest)
            del self.__dict__["cached_digest"]

    @cached_property
    def cached_digest(self) -> bytes:
        return self.tracking_path.read_bytes() if self.tracking_path.is_file() else bytes()

    @property
    def must_build(self) -> bool:
        "returns True if the DDLs of either the object or any of its dependencies have been modified"
        return self.digest != self.cached_digest


Obj = TrackedObj


@dataclass
class ObjSet:
    objs: set[Obj]

    def __str__(self):
        return "[" + ",".join(str(o) for o in self.objs) + "]"
