from dataclasses import dataclass
from functools import cached_property
from graphlib import TopologicalSorter
from logging import getLogger
from typing import Callable

from .obj import Obj, ObjSet
from .util import traverse

logger = getLogger(__name__)


@dataclass
class Runner:
    objs: set[Obj]

    @cached_property
    def affected_objs(self) -> set[Obj]:
        "returns objects that actually need rebuilding"
        objs = {o for o in self.objs if o.must_build}
        up_to_date = self.objs - objs
        if up_to_date:
            logger.info("Skipping already up-to-date objects: %s", ObjSet(up_to_date))
        return objs

    @cached_property
    def targets(self) -> set[Obj]:
        return set(d for d in traverse(self.affected_objs, lambda o: o.deps) if d.must_build)

    def run(self, build: Callable[[Obj], bool]) -> int:
        "run action on each object in topological order"

        tot_failures = 0

        ts = TopologicalSorter({o: o.deps for o in Obj.all()})
        ts.prepare()
        while ts.is_active():
            ready_objs = ts.get_ready()
            if not ready_objs:
                break
            for o in sorted(ready_objs):
                if o in self.targets:
                    if build(o):
                        ts.done(o)
                    else:
                        tot_failures += 1
                else:
                    ts.done(o)

        return 1 if tot_failures > 0 else 0
