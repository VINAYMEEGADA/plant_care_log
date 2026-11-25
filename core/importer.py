"""Bulk CSV import with row-by-row validation and an error log."""
from __future__ import annotations

import csv
import io
from dataclasses import dataclass, field
from datetime import date

from .validation import validate_plant_form

REQUIRED_COLUMNS = ["name", "category", "watering_interval_days", "last_watered"]
OPTIONAL_COLUMNS = ["species", "location", "notes"]
TEMPLATE = "name,species,category,location,watering_interval_days,last_watered,notes\n"

# Map validator field labels to CSV column names for the error log.
_FIELD_TO_COLUMN = {
    "Name": "name", "Species": "species", "Category": "category", "Location": "location",
    "Watering interval": "watering_interval_days", "Last watered": "last_watered", "Notes": "notes",
}


@dataclass
class ImportResult:
    cleaned: list[dict] = field(default_factory=list)   # rows that passed validation
    errors: list[dict] = field(default_factory=list)    # {"Row", "Column", "Problem", "Value"}
    total_rows: int = 0
    fatal: str | None = None                            # file-level problem (no rows processed)


def _decode(data) -> str:
    if isinstance(data, str):
        return data
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError:
        return data.decode("cp1252", errors="replace")


def import_plants_csv(data, existing_names=(), today: date | None = None) -> ImportResult:
    """Validate every row independently so one bad row never blocks the others."""
    result = ImportResult()
    text = _decode(data)
    if not text.strip():
        result.fatal = "The file is empty."
        return result

    try:
        reader = csv.DictReader(io.StringIO(text))
        header = [(h or "").strip().lower() for h in (reader.fieldnames or [])]
        reader.fieldnames = header
    except csv.Error as exc:
        result.fatal = f"Could not read the CSV: {exc}"
        return result

    missing = [c for c in REQUIRED_COLUMNS if c not in header]
    if missing:
        result.fatal = f"Missing required column(s): {', '.join(missing)}. Found: {', '.join(header) or 'none'}."
        return result

    seen = list(existing_names)
    try:
        for row in reader:
            line = reader.line_num
            if all((v is None or str(v).strip() == "") for k, v in row.items() if k is not None) and not row.get(None):
                continue  # blank line
            result.total_rows += 1
            if row.get(None):
                result.errors.append({"Row": line, "Column": "(row)",
                                      "Problem": "Too many columns - check for unquoted commas.",
                                      "Value": ", ".join(row[None])})
                continue
            raw = {k: (v if v is not None else "") for k, v in row.items() if k is not None}
            cleaned, errors = validate_plant_form(raw, existing_names=seen, today=today)
            if errors:
                for label, msg in errors.items():
                    col = _FIELD_TO_COLUMN.get(label, label)
                    result.errors.append({"Row": line, "Column": col, "Problem": msg, "Value": raw.get(col, "")})
                continue
            result.cleaned.append(cleaned)
            seen.append(cleaned["name"])
    except csv.Error as exc:
        result.errors.append({"Row": reader.line_num, "Column": "(file)", "Problem": f"CSV parse error: {exc}", "Value": ""})
    return result


def errors_to_csv(errors: list[dict]) -> str:
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=["Row", "Column", "Problem", "Value"])
    writer.writeheader()
    writer.writerows(errors)
    return buf.getvalue()
