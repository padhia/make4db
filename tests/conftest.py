from pathlib import Path

from pytest import fixture

from make4db.export import Obj


@fixture
def TestObj(tmp_path: Path) -> type[Obj]:
    Obj.ddl_dir = Path(__file__).parent / "ddldir"
    Obj.tracking_dir = tmp_path
    return Obj
