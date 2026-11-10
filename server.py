"""Read-only API for the versioned southern-state dataset."""
import argparse
import json
import sqlite3
from pathlib import Path
from contextlib import closing
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from urllib.parse import parse_qs,urlsplit
from src.common import ROOT,load
from src.run import run

DB=ROOT/"ledger_april.sqlite"


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        url=urlsplit(self.path)
        if url.path=="/":
            self.reply((ROOT/"index.html").read_bytes(),"text/html; charset=utf-8")
            return
        if url.path not in ("/api/power","/api/evidence","/api/audit","/api/comparison"):
            self.send_error(404)
            return
        params=parse_qs(url.query)
        state=params.get("state",[""])[0]
        day=params.get("day",[""])[0]
        config=load()
        if (state and state not in config["states"]) or (day and day not in config["dates"]):
            self.send_error(400,"Outside configured coverage")
            return
        if url.path not in ("/api/power","/api/comparison") and not (state and day):
            self.send_error(400,"State and day required")
            return
        with closing(sqlite3.connect(DB)) as con:
            con.row_factory=sqlite3.Row
            if url.path=="/api/power":
                query="""SELECT day,state,energy_required required,energy_supplied supplied,shortfall,
                quality_flag status,chosen_source supply_source,chosen_source shortfall_source,version
                FROM gold WHERE (?='' OR state=?) AND (?='' OR day=?) ORDER BY day,state"""
                data=[dict(r) for r in con.execute(query,(state,state,day,day))]
            elif url.path=="/api/evidence":
                query="""SELECT s.day,s.state,f.source_name source,f.source_file,f.file_sha256,
                f.revision,s.line,s.supplied,s.shortfall,s.flags,s.quarantined FROM silver s
                JOIN files f ON s.file_id=f.id WHERE s.state=? AND s.day=? ORDER BY f.id"""
                data=[dict(r) for r in con.execute(query,(state,day))]
            elif url.path=="/api/comparison":
                query="""SELECT a.day,a.state,a.supplied source_a,b.supplied source_b,
                round(a.supplied-b.supplied,6) difference_mu
                FROM silver a JOIN files fa ON fa.id=a.file_id
                LEFT JOIN (silver b JOIN files fb ON fb.id=b.file_id)
                ON a.day=b.day AND a.state=b.state AND fb.source_name='zenodo'
                AND fb.revision=(SELECT max(revision) FROM files WHERE source_name='zenodo')
                WHERE fa.source_name='grid_sentinel'
                AND fa.revision=(SELECT max(revision) FROM files WHERE source_name='grid_sentinel')
                AND (?='' OR a.state=?) AND (?='' OR a.day=?)
                ORDER BY a.day,a.state"""
                data=[dict(r) for r in con.execute(query,(state,state,day,day))]
            else:
                data=[dict(r) for r in con.execute("SELECT * FROM history WHERE state=? AND day=? ORDER BY version",(state,day))]
        self.reply(json.dumps(data).encode(),"application/json")

    def reply(self,body,mime):
        self.send_response(200)
        self.send_header("Content-Type",mime)
        self.send_header("Content-Length",str(len(body)))
        self.send_header("Cache-Control","no-store")
        self.end_headers()
        self.wfile.write(body)


if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--port",type=int,default=8773)
    parser.add_argument("--db", default=str(DB))
    args=parser.parse_args()
    DB = (ROOT / args.db).resolve()
    if not DB.exists():
        run(db=DB)
    print(f"http://127.0.0.1:{args.port}",flush=True)
    ThreadingHTTPServer(("127.0.0.1",args.port),Handler).serve_forever()
