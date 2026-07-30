"test objects"

from os import environ

from make4db.export import Obj


def test_all_obj(TestObj: type[Obj]) -> None:
    assert set(TestObj.all()) == set(TestObj.parse_("sch1.tb1", "sch1.tb2", "sch1.vw3", "sch2.tb3", "sch2.vw4"))


def test_deps(TestObj: type[Obj]) -> None:
    assert set(TestObj.parse("sch2.vw4").deps) == set(TestObj.parse_("sch2.tb3", "sch1.vw3"))
    assert set(TestObj.parse("sch1.vw3").deps) == set(TestObj.parse_("sch1.tb1", "sch1.tb2"))


def test_rdeps(TestObj: type[Obj]) -> None:
    assert set(TestObj.parse("sch1.tb1").rdeps) == set(TestObj.parse_("sch1.vw3"))
    assert set(TestObj.parse("sch1.tb2").rdeps) == set(TestObj.parse_("sch1.vw3"))
    assert set(TestObj.parse("sch2.tb3").rdeps) == set(TestObj.parse_("sch2.vw4"))
    assert set(TestObj.parse("sch1.vw3").rdeps) == set(TestObj.parse_("sch2.vw4"))


def test_ddl_text(TestObj: type[Obj]) -> None:
    environ["DBNAME"] = "db1"
    o = TestObj.parse("sch2.tb3")
    assert o.ddl_text == (
        "create or replace table sch2.tb3 (\n"
        "   obj_database varchar(255) not null default 'db1',\n"
        "   obj_schema   varchar(255) not null default 'sch2',\n"
        "   obj_name     varchar(255) not null default 'tb3',\n"
        "   c4           varchar(20)\n"
        ");"
    )
