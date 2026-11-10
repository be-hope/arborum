"""Reconcile valid observations, tracking every change to the curated result."""
import json

COLUMNS = ["day","state","energy_required","energy_supplied","shortfall","shortfall_pct",
           "chosen_source","quality_flag","version","chosen_file_id","required_derived"]


def curate(con, config, run_id):
    active = {(d,s) for d in config["dates"] for s in config["states"]}
    for day,state in con.execute("SELECT day,state FROM gold").fetchall():
        if (day,state) not in active:
            raise ValueError("Use a fresh database when reducing or replacing the scope")
    for day,state in sorted(active):
        candidates = []
        flags = []
        for source in config["source_priority"]:
            latest = con.execute("SELECT id FROM files WHERE source_name=? ORDER BY revision DESC LIMIT 1",(source,)).fetchone()
            if not latest:
                flags.append("missing_source:"+source)
                continue
            rows = con.execute("SELECT supplied,shortfall,required,required_derived,quarantined FROM silver WHERE file_id=? AND state=? AND day=?",(latest[0],state,day)).fetchall()
            if len(rows)!=1 or rows[0][4]:
                flags.append("unusable_source:"+source)
                continue
            candidates.append((source,latest[0],*rows[0][:4]))
        complete = [r for r in candidates if r[4] is not None]
        winner = (complete or candidates or [None])[0]
        if winner:
            source,file_id,supplied,shortfall,required,derived = winner
            for other in candidates:
                for a,b in zip(winner[2:5],other[2:5]):
                    if a is not None and b is not None and abs(a-b)>config["tolerance_mu"]+1e-9:
                        flags.append("source_disagreement")
            pct = None if required in (None,0) or shortfall is None else round(100*shortfall/required,6)
        else:
            source=file_id=supplied=shortfall=required=pct=None
            derived=0
        if required is None:
            flags.append("missing_state_day_measures")
        status = ",".join(sorted(set(flags))) or "passed"
        old = con.execute("SELECT * FROM gold WHERE day=? AND state=?",(day,state)).fetchone()
        prior = con.execute("SELECT max(version) FROM history WHERE day=? AND state=?",(day,state)).fetchone()[0] or 0
        row = (day,state,required,supplied,shortfall,pct,source,status,prior,file_id,derived)
        if old and old[:8]+old[10:] == row[:8]+row[10:]:
            continue
        row = row[:8]+(prior+1,)+row[9:]
        con.execute("INSERT OR REPLACE INTO gold VALUES (?,?,?,?,?,?,?,?,?,?,?)",row)
        con.execute("INSERT INTO history VALUES (?,?,?,?,?,?)",
            (day,state,prior+1,run_id,json.dumps(dict(zip(COLUMNS,old))) if old else None,json.dumps(dict(zip(COLUMNS,row)))))

