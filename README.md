# Power Ledger

Daily electricity data for Karnataka, Kerala and Tamil Nadu, 22–28 April 2024. Python 3.10+ is required.

## Run

    python -m src.run
    python server.py

Open http://127.0.0.1:8773.

## Correction demo

    python demo_versions.py --keep
    python server.py --port 8774 --db demo/output/demo.sqlite

Open http://127.0.0.1:8774 and inspect Kerala on 27 April. The labelled synthetic revision changes shortfall from 0.95 to 0.45 MU. The script verifies an unchanged rerun, exactly one changed gold row, retained history, failure rollback and retry.

## Tests

    python -m pip install -r requirements-dev.txt
    python -m pytest -q

## Data and decisions

Original downloads are in data/raw/. data/source_downloads.json records download attribution and hashes. data/manifest.csv records ingestion lineage. data/comparable/comparison.csv contains 21 supplied-energy comparisons.

Source A: https://github.com/HalcyonVector/Grid-Sentinel/blob/main/Dataset/README.md
Source B: https://zenodo.org/records/14983362

Both publications derive from Indian grid reporting. Only supplied energy overlaps. Original operator PDFs and regional reports remain unacquired. All 21 comparisons agree within 0.05 MU.

Bronze preserves extracted text and lineage. Silver standardizes values and quarantines invalid or duplicate observations. Gold prefers a complete valid observation, then configured source priority. Grid-Sentinel comes first because it supplies both delivered energy and shortage. Required energy is derived as supplied plus shortage. Missing values remain null. Changed results increment their own gold version. SQLite transactions protect successful results from failed imports.

Weekly supplied energy is 2173.09 MU for Karnataka, 748.32 MU for Kerala and 3017.84 MU for Tamil Nadu. Kerala reports 2.03 MU shortage. The other selected state-days report zero. These figures cannot measure suppressed demand.

config.yaml controls states, dates, aliases and priority. New measures require code/schema changes. Use a fresh --db path when reducing or replacing scope. The measure list is declarative. Acquisition automation would schedule staged downloads, retry transient errors, archive by hash, register explicit publication revisions and alert on missing days. Scheduling and original-report parsing remain unfinished.
"# arborum" 
