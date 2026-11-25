"""Defensive input validation.

Every validator returns ``(ok, cleaned_value, error_message)`` so the UI can
show the message and the unit tests stay trivial.  Validation is enforced here,
not in the UI widgets, so bad data is rejected no matter where it comes from
(forms, CSV import, tests).
"""
from __future__ import annotations

import math
import re
from datetime import date, datetime

MIN_DATE = date(2000, 1, 1)
CATEGORIES = ["Indoor", "Outdoor", "Succulent", "Herb", "Vegetable", "Flower"]
ACTIONS = ["Watered", "Fertilized", "Pruned", "Repotted", "Note"]

NAME_MIN, NAME_MAX = 2, 50
TEXT_MAX = 50          # species / location
NOTES_MAX = 500
INTERVAL_MIN, INTERVAL_MAX = 1, 60
WATER_MAX_ML = 5000

_NAME_RE = re.compile(r"^[\w\s\-'.&(),]+$", re.UNICODE)
_DATE_FORMATS = ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y")


def _clean(value) -> str:
    """Trim and collapse all whitespace (also strips stray newlines/tabs)."""
    return " ".join(str(value).split()) if value is not None else ""


def validate_name(value):
    s = _clean(value)
    if not s:
        return False, None, "Name is required."
    if len(s) < NAME_MIN:
        return False, None, f"Name must be at least {NAME_MIN} characters."
    if len(s) > NAME_MAX:
        return False, None, f"Name must be at most {NAME_MAX} characters (got {len(s)})."
    if not _NAME_RE.match(s):
        return False, None, "Name may only contain letters, digits, spaces and - ' . & ( ) ,"
    return True, s, None


def validate_optional_text(value, field: str, max_len: int = TEXT_MAX):
    s = _clean(value)
    if len(s) > max_len:
        return False, None, f"{field} must be at most {max_len} characters (got {len(s)})."
    return True, s, None


def validate_notes(value):
    return validate_optional_text(value, "Notes", NOTES_MAX)


def validate_choice(value, choices, field: str):
    s = _clean(value)
    if not s:
        return False, None, f"{field} is required."
    for choice in choices:
        if choice.lower() == s.lower():
            return True, choice, None
    return False, None, f"{field} must be one of: {', '.join(choices)}."


def validate_date(value, field: str = "Date", today: date | None = None):
    today = today or date.today()
    if isinstance(value, datetime):
        d = value.date()
    elif isinstance(value, date):
        d = value
    else:
        s = _clean(value)
        if not s:
            return False, None, f"{field} is required."
        d = None
        for fmt in _DATE_FORMATS:
            try:
                d = datetime.strptime(s, fmt).date()
                break
            except ValueError:
                continue
        if d is None:
            return False, None, f"{field} must look like YYYY-MM-DD (or DD/MM/YYYY)."
    if d > today:
        return False, None, f"{field} cannot be in the future ({d.isoformat()})."
    if d < MIN_DATE:
        return False, None, f"{field} cannot be before {MIN_DATE.isoformat()}."
    return True, d, None


def validate_interval(value):
    msg = f"Watering interval must be a whole number of days ({INTERVAL_MIN}-{INTERVAL_MAX})."
    if isinstance(value, bool):
        return False, None, msg
    if isinstance(value, float):
        if not math.isfinite(value) or not value.is_integer():
            return False, None, msg
        n = int(value)
    elif isinstance(value, int):
        n = value
    else:
        s = _clean(value)
        if not s:
            return False, None, "Watering interval is required."
        try:
            n = int(s)
        except ValueError:
            return False, None, msg
    if not INTERVAL_MIN <= n <= INTERVAL_MAX:
        return False, None, f"Watering interval must be between {INTERVAL_MIN} and {INTERVAL_MAX} days (got {n})."
    return True, n, None


def validate_water_ml(value):
    """Optional. Blank means 'not recorded'."""
    if value is None or (isinstance(value, str) and not value.strip()):
        return True, None, None
    if isinstance(value, bool):
        return False, None, "Water amount must be a number."
    try:
        x = float(value) if isinstance(value, (int, float)) else float(str(value).strip())
    except ValueError:
        return False, None, "Water amount must be a number of millilitres."
    if not math.isfinite(x):
        return False, None, "Water amount must be a finite number."
    if not 0 <= x <= WATER_MAX_ML:
        return False, None, f"Water amount must be between 0 and {WATER_MAX_ML} ml (got {x:g})."
    return True, int(round(x)), None


def _collect(cleaned: dict, errors: dict, key: str, label: str, result) -> None:
    ok, value, err = result
    if ok:
        cleaned[key] = value
    else:
        errors[label] = err


def validate_plant_form(raw: dict, existing_names=(), today: date | None = None):
    """Validate a whole plant record. Returns ``(cleaned, errors)``.

    ``errors`` maps field label -> message; the record is valid iff it is empty.
    For edits, drop the plant's own current name from ``existing_names``.
    """
    errors: dict[str, str] = {}
    cleaned: dict = {}
    _collect(cleaned, errors, "name", "Name", validate_name(raw.get("name")))
    _collect(cleaned, errors, "species", "Species", validate_optional_text(raw.get("species"), "Species"))
    _collect(cleaned, errors, "category", "Category", validate_choice(raw.get("category"), CATEGORIES, "Category"))
    _collect(cleaned, errors, "location", "Location", validate_optional_text(raw.get("location"), "Location"))
    _collect(cleaned, errors, "watering_interval_days", "Watering interval",
             validate_interval(raw.get("watering_interval_days")))
    _collect(cleaned, errors, "last_watered", "Last watered",
             validate_date(raw.get("last_watered"), "Last watered", today))
    _collect(cleaned, errors, "notes", "Notes", validate_notes(raw.get("notes")))

    if "name" in cleaned and cleaned["name"].lower() in {n.lower() for n in existing_names}:
        errors["Name"] = f"A plant named '{cleaned['name']}' already exists."
    return cleaned, errors


def validate_care_form(raw: dict, today: date | None = None):
    """Validate a care-log entry. Returns ``(cleaned, errors)``."""
    errors: dict[str, str] = {}
    cleaned: dict = {}
    _collect(cleaned, errors, "date", "Date", validate_date(raw.get("date"), "Date", today))
    _collect(cleaned, errors, "action", "Action", validate_choice(raw.get("action"), ACTIONS, "Action"))
    _collect(cleaned, errors, "notes", "Notes", validate_notes(raw.get("notes")))
    _collect(cleaned, errors, "water_ml", "Water amount", validate_water_ml(raw.get("water_ml")))

    action = cleaned.get("action")
    if action and action != "Watered" and cleaned.get("water_ml") is not None:
        errors["Water amount"] = "Water amount only applies to 'Watered' entries."
    if action == "Note" and "notes" in cleaned and not cleaned["notes"]:
        errors["Notes"] = "A 'Note' entry needs some text."
    return cleaned, errors
