"""Offline demonstration in a separate temporary database."""
import argparse
import shutil
import copy
import csv
import json
import sqlite3
import tempfile
from contextlib import closing
from pathlib import Path
from src.common import ROOT,load
from src.run import run,checksum


def demo(keep=False):
    config = load()
    with tempfile.TemporaryDirectory(dir=ROOT) as folder:
        root = Path(folder)
        (root / "data").mkdir()
        # Absolute inputs allow using original samples without copying them.
        for item in config["inputs"]:
            item["path"] = str(ROOT / item["path"])
        db = root / "demo.sqlite"
        first = run(config,db,root)
        again = run(config,db,root)
        assert first["gold_checksum"] == again["gold_checksum"] and again["new_files"] == 0
        print("Baseline and unchanged rerun:",first,again)
        revision = root / "revised.csv"
        # This partial revision fixture must include the complete current scoped snapshot.
        original = Path(config["inputs"][0]["path"])
        selected = []
        with original.open(newline="") as stream:
            reader = csv.DictReader(stream)
            fields = reader.fieldnames
            for row in reader:
                if row["date"] in config["dates"] and row["state"] in config["states"]:
                    if row["date"]=="2024-04-27" and row["state"]=="Kerala":
                        row["energy_shortage_mu"]="0.45"
                    selected.append(row)
        with revision.open("w",newline="") as stream:
            writer=csv.DictWriter(stream,fieldnames=fields)
            writer.writeheader()
            writer.writerows(selected)
        changed=copy.deepcopy(config)
        changed["inputs"][0].update(path=str(revision),revision=2,url="synthetic demonstration fixture")
        before = None
        with closing(sqlite3.connect(db)) as con:
            before=con.execute("SELECT * FROM gold ORDER BY day,state").fetchall()
        revised=run(changed,db,root)
        with closing(sqlite3.connect(db)) as con:
            after=con.execute("SELECT * FROM gold ORDER BY day,state").fetchall()
            # Equivalent values retain their original selected evidence and version.
            measure_changes=[(a,b) for a,b in zip(before,after) if a[:8]!=b[:8]]
            assert len(measure_changes)==1
            assert sum(a != b for a,b in zip(before,after))==1
            assert measure_changes[0][1][4]==0.45
            print("Corrected measure:",measure_changes[0])
            print("Retained silver observations:",con.execute("SELECT count(*) FROM silver").fetchone()[0])
        corrupt=root / "corrupt.csv"
        corrupt.write_text("invalid header\n")
        failed=copy.deepcopy(changed)
        failed["inputs"][0].update(path=str(corrupt),revision=3)
        try:
            run(failed,db,root)
            raise AssertionError("Expected failed import")
        except ValueError:
            pass
        with closing(sqlite3.connect(db)) as con:
            assert checksum(con)==revised["gold_checksum"]
            assert con.execute("SELECT count(*) FROM runs WHERE status='failed'").fetchone()[0]==1
        retry=run(changed,db,root)
        assert retry["gold_checksum"]==revised["gold_checksum"]
        print("Failed import rolled back; failure recorded; retry succeeded.")
        if keep:
            output = ROOT / "demo" / "output"
            output.mkdir(exist_ok=True)
            shutil.copyfile(db, output / "demo.sqlite")
            shutil.copyfile(revision, output / "synthetic_revision.csv")
            shutil.copytree(root / "data" / "raw", output / "data" / "raw", dirs_exist_ok=True)
            with closing(sqlite3.connect(output / "demo.sqlite")) as saved, saved:
                for original in load()["inputs"]:
                    saved.execute("UPDATE files SET source_file=? WHERE source_name=? AND revision=1",
                                  (original["path"], original["source"]))
                saved.execute("UPDATE files SET source_file=? WHERE source_name=? AND revision=2",
                              ("demo/output/synthetic_revision.csv", "grid_sentinel"))
            with closing(sqlite3.connect(db)) as con:
                con.row_factory = sqlite3.Row
                report = {
                    "synthetic": True,
                    "baseline": first,
                    "rerun": again,
                    "revised": revised,
                    "audit": [dict(r) for r in con.execute("SELECT * FROM history WHERE version>1")],
                    "runs": [dict(r) for r in con.execute("SELECT * FROM runs ORDER BY started_at")]
                }
            (output / "replay.json").write_text(json.dumps(report, indent=2))
            print("Saved demo/output/demo.sqlite and replay.json for review.")


if __name__=="__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--keep", action="store_true")
    demo(parser.parse_args().keep)

