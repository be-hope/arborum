import copy
import sqlite3
from contextlib import closing
import pytest
from src.common import ROOT,load
from src.parse_csv import parse
from src.silver import clean
from src.run import run
from demo_versions import demo


@pytest.mark.parametrize("fields,expected", [
    ({"energy_supplied":"-1","shortfall":"0"},"negative"),
    ({"energy_supplied":"10","shortfall":"1","energy_required":"9"},"required_below_supplied"),
    ({"energy_supplied":"10","shortfall":"1","energy_required":"15"},"balance_mismatch"),
    ({"energy_supplied":"nan"},"invalid_numeric"),
])
def test_quality(fields,expected):
    assert expected in clean(fields,.05)[4]


def test_parser():
    config=load()
    rows=list(parse(ROOT/config["inputs"][0]["path"],"long_csv",config))
    assert len(rows)==21
    assert any(s=="Kerala" and d=="2024-04-27" and f["shortfall"]=="0.95" for _,s,d,f in rows)


def test_demo():
    demo()


def test_priority_missing_duplicate_and_conflict(tmp_path):
    (tmp_path/"data").mkdir()
    config=load()
    config.update(states=["Kerala"],start_date="2026-09-22",end_date="2026-09-23",dates=["2026-09-22","2026-09-23"])
    config["inputs"]=[]
    for source,met in [("grid_sentinel",10),("zenodo",12)]:
        path=tmp_path/(source+".csv")
        path.write_text(f"date,state,energy_met_mu,energy_shortage_mu\n2026-09-22,Kerala,{met},1\n")
        config["inputs"].append(dict(source=source,path=str(path),parser="long_csv",revision=1,url="test"))
    db=tmp_path/"test.sqlite"
    run(config,db,tmp_path)
    with closing(sqlite3.connect(db)) as con:
        row=con.execute("SELECT energy_supplied,quality_flag FROM gold WHERE day='2026-09-22'").fetchone()
        assert row==(10,"source_disagreement")
        assert con.execute("SELECT energy_required FROM gold WHERE day='2026-09-23'").fetchone()[0] is None
    config["source_priority"].reverse()
    run(config,db,tmp_path)
    with closing(sqlite3.connect(db)) as con:
        assert con.execute("SELECT energy_supplied FROM gold WHERE day='2026-09-22'").fetchone()[0]==12
    path=tmp_path/"duplicate.csv"
    path.write_text("date,state,energy_met_mu,energy_shortage_mu\n2026-09-22,Kerala,12,1\n2026-09-22,Kerala,13,1\n")
    config["inputs"][1].update(path=str(path),revision=2)
    run(config,db,tmp_path)
    with closing(sqlite3.connect(db)) as con:
        assert con.execute("SELECT count(*) FROM silver WHERE flags LIKE '%duplicate_state_day%'").fetchone()[0]==2
        assert con.execute("SELECT energy_supplied FROM gold WHERE day='2026-09-22'").fetchone()[0]==10

def test_late_primary_and_expanded_scope(tmp_path):
    (tmp_path / "data").mkdir()
    config = load()
    for item in config["inputs"]:
        item["path"] = str(ROOT / item["path"])
    primary = config["inputs"].pop(0)
    db = tmp_path / "late.sqlite"
    run(config, db, tmp_path)
    with closing(sqlite3.connect(db)) as con:
        assert con.execute("SELECT count(*) FROM gold WHERE energy_required IS NULL").fetchone()[0] == 21
    config["inputs"].insert(0, primary)
    run(config, db, tmp_path)
    with closing(sqlite3.connect(db)) as con:
        assert con.execute("SELECT count(*) FROM gold WHERE energy_required IS NOT NULL").fetchone()[0] == 21
    config["states"].append("Andhra Pradesh")
    run(config, db, tmp_path)
    with closing(sqlite3.connect(db)) as con:
        assert con.execute("SELECT count(*) FROM gold WHERE state='Andhra Pradesh' AND energy_required IS NOT NULL").fetchone()[0] == 7
        assert con.execute("SELECT count(*) FROM files").fetchone()[0] == 2
