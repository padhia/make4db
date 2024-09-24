"test utility functions"

from make4db.export import Obj
from make4db.util import only_roots, traverse


def test_roots(TestObj: type[Obj]) -> None:
    assert set(only_roots(set(TestObj.parse_("sch1.vw3", "sch2.vw4")), lambda o: o.rdeps)) == set(TestObj.parse_("sch2.vw4"))


def test_roots_upstream(TestObj: type[Obj]) -> None:
    assert set(only_roots(set(TestObj.all()), lambda o: o.rdeps)) == set(TestObj.parse_("sch2.vw4"))


def test_roots_downstream(TestObj: type[Obj]) -> None:
    assert set(only_roots(set(TestObj.all()), lambda o: o.deps)) == set(TestObj.parse_("sch1.tb1", "sch1.tb2", "sch2.tb3"))


def test_traverse(TestObj: type[Obj]) -> None:
    assert set(traverse(TestObj.parse_("sch1.vw3"), lambda o: o.deps)) == set(TestObj.parse_("sch1.vw3", "sch1.tb1", "sch1.tb2"))
    assert set(traverse(TestObj.parse_("sch2.vw4"), lambda o: o.deps)) == set(
        TestObj.parse_("sch2.vw4", "sch1.vw3", "sch1.tb1", "sch1.tb2", "sch2.tb3")
    )
