"""Normalize each source observation and retain rejected values as flags."""
import json
import math


def clean(fields, tolerance):
    flags = []
    result = {}
    for field,text in fields.items():
        try:
            number = None if not text.strip() else float(text)
            if number is not None and not math.isfinite(number):
                raise ValueError()
            result[field] = number
        except ValueError:
            flags.append("invalid_numeric")
            result[field] = None
    supplied = result.get("energy_supplied")
    shortage = result.get("shortfall")
    required = result.get("energy_required")
    derived = required is None and supplied is not None and shortage is not None
    if derived:
        required = round(supplied + shortage,6)
    if any(x is not None and x < 0 for x in (supplied,shortage,required)):
        flags.append("negative")
    if required is not None and supplied is not None and required < supplied - tolerance:
        flags.append("required_below_supplied")
    if all(x is not None for x in (required,supplied,shortage)) and abs(required-supplied-shortage)>tolerance:
        flags.append("balance_mismatch")
    return supplied,shortage,required,int(derived),flags


def standardize(con, config):
    # Re-evaluate all immutable bronze observations for the active configuration.
    con.execute("DELETE FROM silver")
    groups = {}
    for file_id,line,state,day,field,text in con.execute("SELECT file_id,line,state_text,data_date_text,field,raw_text FROM bronze"):
        canonical = config["state_aliases"].get(state,state)
        if canonical in config["states"] and day in config["dates"]:
            groups.setdefault((file_id,line,canonical,day),{})[field] = text
    counts = {}
    for file_id,line,state,day in groups:
        key = (file_id,state,day)
        counts[key] = counts.get(key,0)+1
    for (file_id,line,state,day),fields in groups.items():
        supplied,shortage,required,derived,flags = clean(fields,config["tolerance_mu"])
        if counts[file_id,state,day]>1:
            flags.append("duplicate_state_day")
        con.execute("INSERT INTO silver VALUES (?,?,?,?,?,?,?,?,?,?)",
            (file_id,line,state,day,supplied,shortage,required,derived,json.dumps(flags),int(bool(flags))))
