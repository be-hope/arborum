"""Preserve downloaded bytes and append extracted fields with file lineage."""
import hashlib
from .parse_csv import parse


def ingest(con, config, root, run_id, timestamp):
    added = 0
    con.execute("CREATE UNIQUE INDEX IF NOT EXISTS bronze_field ON bronze(file_id,line,state_text,field)")
    for item in config["inputs"]:
        path = root / item["path"]
        contents = path.read_bytes()
        sha = hashlib.sha256(contents).hexdigest()
        archived = root / "data" / "raw" / "archive" / (sha + path.suffix)
        archived.parent.mkdir(parents=True, exist_ok=True)
        if archived.exists() and hashlib.sha256(archived.read_bytes()).hexdigest() != sha:
            raise ValueError("Archived file checksum mismatch")
        if not archived.exists():
            archived.write_bytes(contents)
        existing_file = con.execute(
            "SELECT id FROM files WHERE source_name=? AND file_sha256=?",
            (item["source"], sha)).fetchone()
        if existing_file:
            file_id = existing_file[0]
        else:
            latest = con.execute("SELECT max(revision) FROM files WHERE source_name=?",
                                 (item["source"],)).fetchone()[0]
            if latest is not None and item["revision"] <= latest:
                raise ValueError("Changed bytes require a higher explicit publication revision")
            cursor = con.execute(
                """INSERT INTO files(source_name,source_file,file_sha256,report_date,
                ingested_at,run_id,revision,source_url) VALUES (?,?,?,?,?,?,?,?)""",
                (item["source"], item["path"], sha, item.get("report_date"),
                 timestamp, run_id, item["revision"], item["url"]))
            file_id = cursor.lastrowid
            added += 1
        # Re-reading an existing hash supports expanded scope without duplicating fields.
        for line, state, day, fields in parse(archived, item["parser"], config):
            con.executemany("INSERT OR IGNORE INTO bronze VALUES (?,?,?,?,?,?,?)",
                [(file_id, line, state, day, field, text, "MU") for field, text in fields.items()])
    return added
