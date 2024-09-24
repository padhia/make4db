"test dependencies"

from typing import Callable, Iterable

from make4db.export import Obj, Runner


def touch(xs: Iterable[Obj]) -> None:
    for x in xs:
        x.refresh_digest()


def make_builder(done: set[Obj], fails: set[Obj] = set()) -> Callable[[Obj], bool]:
    def accum(o: Obj) -> bool:
        if o in fails:
            return False
        done.add(o)
        return True

    return accum


def test_all_changed(TestObj: type[Obj]) -> None:
    all_objs = set(TestObj.all())
    assert Runner(all_objs).targets == all_objs


def test_none_changed(TestObj: type[Obj]) -> None:
    touch(TestObj.parse_("sch1.tb1"))
    assert Runner(set(TestObj.parse_("sch1.tb1"))).targets == set()


def test_some_changed(TestObj: type[Obj]) -> None:
    touch(TestObj.parse_("sch1.tb2", "sch2.tb3"))
    assert Runner(set(TestObj.parse_("sch2.vw4"))).targets == set(TestObj.parse_("sch1.tb1", "sch1.vw3", "sch2.vw4"))


def test_force_rebuild(TestObj: type[Obj]) -> None:
    touch(TestObj.all())

    Obj.newly_salted = set(TestObj.parse_("sch1.vw3"))
    assert Runner(set(TestObj.all())).targets == set(TestObj.parse_("sch1.vw3", "sch2.vw4"))

    Obj.newly_salted = set()


def test_success(TestObj: type[Obj]) -> None:
    sch1_tb1, sch2_tb3 = TestObj.parse_("sch1.tb1", "sch2.tb3")
    sch1_tb1.refresh_digest()
    result: set[Obj] = set()

    Runner(set([sch1_tb1, sch2_tb3])).run(make_builder(result))

    assert result == set([sch2_tb3])
