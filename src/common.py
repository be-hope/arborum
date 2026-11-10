"""The JSON subset of YAML keeps the application dependency-free."""
import json
import sqlite3
from contextlib import closing
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load(path=None):
    config = json.loads(Path(path or ROOT / "config.yaml").read_text(encoding="utf-8-sig"))
    days = (date.fromisoformat(config["end_date"]) - date.fromisoformat(config["start_date"])).days
    if days < 0 or len(config["states"]) != len(set(config["states"])):
        raise ValueError("Invalid scope")
    config["dates"] = [(date.fromisoformat(config["start_date"]) + timedelta(days=i)).isoformat() for i in range(days + 1)]
    return config


SCHEMA = """
CREATE TABLE IF NOT EXISTS runs(run_id TEXT PRIMARY KEY,started_at TEXT,status TEXT,error TEXT);
CREATE TABLE IF NOT EXISTS files(id INTEGER PRIMARY KEY,source_name TEXT,source_file TEXT,
 file_sha256 TEXT,report_date TEXT,ingested_at TEXT,run_id TEXT,revision INTEGER,source_url TEXT,
 UNIQUE(source_name,file_sha256),UNIQUE(source_name,revision));
CREATE TABLE IF NOT EXISTS bronze(file_id INTEGER,line INTEGER,state_text TEXT,data_date_text TEXT,
 field TEXT,raw_text TEXT,unit TEXT);
CREATE TABLE IF NOT EXISTS silver(file_id INTEGER,line INTEGER,state TEXT,day TEXT,
 supplied REAL,shortfall REAL,required REAL,required_derived INTEGER,flags TEXT,quarantined INTEGER);
CREATE TABLE IF NOT EXISTS gold(day TEXT,state TEXT,energy_required REAL,energy_supplied REAL,
 shortfall REAL,shortfall_pct REAL,chosen_source TEXT,quality_flag TEXT,version INTEGER,
 chosen_file_id INTEGER,required_derived INTEGER,PRIMARY KEY(day,state));
CREATE TABLE IF NOT EXISTS history(day TEXT,state TEXT,version INTEGER,run_id TEXT,
 old_json TEXT,new_json TEXT,PRIMARY KEY(day,state,version));
CREATE VIEW IF NOT EXISTS shortfall_by_state AS SELECT state,sum(shortfall) shortfall_mu,
 sum(energy_required) required_mu,100.0*sum(shortfall)/nullif(sum(energy_required),0) shortfall_pct,
 count(energy_required) complete_days FROM gold GROUP BY state;
CREATE VIEW IF NOT EXISTS daily_trend AS SELECT day,sum(energy_supplied) supplied_mu,
 sum(shortfall) shortfall_mu,count(energy_required) complete_states FROM gold GROUP BY day;
CREATE VIEW IF NOT EXISTS completeness AS SELECT state,count(*) expected_days,
 count(energy_required) complete_days FROM gold GROUP BY state;
CREATE VIEW IF NOT EXISTS bronze_lineage AS SELECT b.*,f.source_name,f.source_file,
 f.file_sha256,f.report_date,f.ingested_at,f.run_id FROM bronze b JOIN files f ON f.id=b.file_id;
"""
