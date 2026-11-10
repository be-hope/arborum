"""CSV adapters retain extracted text and source line numbers."""
import csv


def parse(path, kind, config):
    with path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        required = {"Date", *config["states"]} if kind == "wide_csv" else {"date","state","energy_met_mu","energy_shortage_mu"}
        if kind not in ("wide_csv","long_csv") or not required.issubset(reader.fieldnames or []):
            raise ValueError(f"Unsupported parser/header: {path.name}")
        for row in reader:
            day = row["Date" if kind == "wide_csv" else "date"]
            if day not in config["dates"]:
                continue
            if kind == "wide_csv":
                for state in config["states"]:
                    yield reader.line_num,state,day,{"energy_supplied": row[state]}
            else:
                state = config["state_aliases"].get(row["state"], row["state"])
                if state in config["states"]:
                    fields = {"energy_supplied": row["energy_met_mu"], "shortfall": row["energy_shortage_mu"]}
                    if "energy_required_mu" in row:
                        fields["energy_required"] = row["energy_required_mu"]
                    yield reader.line_num,row["state"],day,fields
