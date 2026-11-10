"""Run each import atomically and persist both success and failure status."""
import argparse
import csv
import hashlib
import json
import sqlite3
import uuid
from contextlib import closing
from datetime import datetime,timezone
from pathlib import Path
from .common import ROOT,SCHEMA,load
from .ingest import ingest
from .silver import standardize
from .gold import curate


def checksum(con):
    return hashlib.sha256(json.dumps(con.execute("SELECT * FROM gold ORDER BY day,state").fetchall()).encode()).hexdigest()


def run(config=None, db=None, root=ROOT):
    config = config or load()
    db = Path(db or root / "ledger_april.sqlite")
    run_id = uuid.uuid4().hex
    now = datetime.now(timezone.utc).isoformat()
    with closing(sqlite3.connect(db)) as con:
        con.executescript(SCHEMA)
        con.execute("INSERT INTO runs VALUES (?,?,?,NULL)",(run_id,now,"running"))
        con.commit()
        try:
            con.execute("BEGIN IMMEDIATE")
            added = ingest(con,config,root,run_id,now)
            standardize(con,config)
            curate(con,config,run_id)
            con.execute("UPDATE runs SET status='success' WHERE run_id=?",(run_id,))
            con.commit()
        except Exception as error:
            con.rollback()
            con.execute("UPDATE runs SET status='failed',error=? WHERE run_id=?",(str(error),run_id))
            con.commit()
            raise
        summary = {"new_files":added,"gold_rows":con.execute("SELECT count(*) FROM gold").fetchone()[0],"gold_checksum":checksum(con)}
        manifest = root / "data" / "manifest.csv"
        with manifest.open("w",newline="",encoding="utf-8") as stream:
            writer = csv.writer(stream)
            writer.writerow(["source_name","source_file","file_sha256","report_date","ingested_at","run_id","revision","source_url"])
            writer.writerows(con.execute("SELECT source_name,source_file,file_sha256,report_date,ingested_at,run_id,revision,source_url FROM files ORDER BY id"))
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--config")
    parser.add_argument("--db")
    args = parser.parse_args()
    print(json.dumps(run(load(args.config),args.db),indent=2))
