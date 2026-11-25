"""JSON persistence with corruption handling, plus the in-memory Database."""
from __future__ import annotations

import json
import os
import uuid
from datetime import date, datetime
from pathlib import Path

from .models import CareEntry, Plant

SCHEMA_VERSION = 1


def make_id() -> str:
    return uuid.uuid4().hex[:8]


class Database:
    """Holds plants and care logs and applies the business rules for changing them."""

    def __init__(self, plants: list[Plant] | None = None, logs: list[CareEntry] | None = None):
        self.plants: list[Plant] = plants or []
        self.logs: list[CareEntry] = logs or []

    # --- lookups -------------------------------------------------------
    def plant_names(self) -> list[str]:
        return [p.name for p in self.plants]

    def get_plant(self, plant_id: str) -> Plant | None:
        return next((p for p in self.plants if p.id == plant_id), None)

    def logs_for(self, plant_id: str) -> list[CareEntry]:
        return sorted((l for l in self.logs if l.plant_id == plant_id), key=lambda l: l.date, reverse=True)

    # --- plants --------------------------------------------------------
    def add_plant(self, cleaned: dict, today: date | None = None) -> Plant:
        today = today or date.today()
        plant = Plant(
            id=make_id(),
            name=cleaned["name"],
            species=cleaned.get("species", ""),
            category=cleaned["category"],
            location=cleaned.get("location", ""),
            watering_interval_days=cleaned["watering_interval_days"],
            last_watered=cleaned["last_watered"].isoformat(),
            created_at=today.isoformat(),
            notes=cleaned.get("notes", ""),
        )
        self.plants.append(plant)
        return plant

    def add_plants_bulk(self, cleaned_rows: list[dict], today: date | None = None) -> int:
        for row in cleaned_rows:
            self.add_plant(row, today)
        return len(cleaned_rows)

    def update_plant(self, plant_id: str, cleaned: dict) -> None:
        plant = self.get_plant(plant_id)
        if plant is None:
            raise KeyError(plant_id)
        plant.name = cleaned["name"]
        plant.species = cleaned.get("species", "")
        plant.category = cleaned["category"]
        plant.location = cleaned.get("location", "")
        plant.watering_interval_days = cleaned["watering_interval_days"]
        plant.last_watered = cleaned["last_watered"].isoformat()
        plant.notes = cleaned.get("notes", "")

    def delete_plant(self, plant_id: str) -> None:
        self.plants = [p for p in self.plants if p.id != plant_id]
        self.logs = [l for l in self.logs if l.plant_id != plant_id]

    # --- care logs -----------------------------------------------------
    def add_log(self, plant_id: str, cleaned: dict) -> CareEntry:
        plant = self.get_plant(plant_id)
        if plant is None:
            raise KeyError(plant_id)
        entry = CareEntry(
            id=make_id(),
            plant_id=plant_id,
            date=cleaned["date"].isoformat(),
            action=cleaned["action"],
            notes=cleaned.get("notes", ""),
            water_ml=cleaned.get("water_ml"),
        )
        self.logs.append(entry)
        # A newer watering moves the schedule forward; back-dated entries never move it back.
        if entry.action == "Watered" and entry.date > plant.last_watered:
            plant.last_watered = entry.date
        return entry

    # --- serialisation -------------------------------------------------
    def to_dict(self) -> dict:
        return {
            "schema_version": SCHEMA_VERSION,
            "plants": [p.to_dict() for p in self.plants],
            "logs": [l.to_dict() for l in self.logs],
        }


def _valid_plant(p: Plant) -> bool:
    try:
        date.fromisoformat(p.last_watered)
        date.fromisoformat(p.created_at)
        return int(p.watering_interval_days) >= 1 and bool(p.name) and bool(p.id)
    except (ValueError, TypeError):
        return False


def _valid_log(l: CareEntry) -> bool:
    try:
        date.fromisoformat(l.date)
        return bool(l.id) and bool(l.plant_id) and bool(l.action)
    except (ValueError, TypeError):
        return False


def save_db(db: Database, path) -> None:
    """Atomic write: write to a temp file, then replace, so a crash can't truncate data."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(db.to_dict(), fh, indent=2, ensure_ascii=False)
    os.replace(tmp, path)


def load_db(path) -> tuple[Database, str | None]:
    """Load the database. Never raises for missing/corrupt files.

    Returns ``(db, notice)``; ``notice`` is a human-readable message when something
    had to be repaired (corrupt file backed up, bad records skipped), else None.
    """
    path = Path(path)
    if not path.exists():
        db = Database()
        try:
            save_db(db, path)
        except OSError:
            pass
        return db, None

    try:
        with open(path, "r", encoding="utf-8") as fh:
            raw = json.load(fh)
        if not isinstance(raw, dict) or not isinstance(raw.get("plants"), list):
            raise ValueError("unexpected structure")
        logs_raw = raw.get("logs", [])
        if not isinstance(logs_raw, list):
            raise ValueError("logs is not a list")
    except (json.JSONDecodeError, ValueError, UnicodeDecodeError, OSError) as exc:
        backup = path.with_name(f"{path.name}.corrupt-{datetime.now():%Y%m%d-%H%M%S}")
        try:
            os.replace(path, backup)
            where = f"The unreadable file was kept as '{backup.name}'."
        except OSError:
            where = "The unreadable file could not be backed up."
        db = Database()
        try:
            save_db(db, path)
        except OSError:
            pass
        return db, f"Data file was corrupted ({exc}). Started with a clean database. {where}"

    plants, logs, skipped = [], [], 0
    for item in raw["plants"]:
        try:
            plant = Plant.from_dict(item)
            if _valid_plant(plant):
                plants.append(plant)
            else:
                skipped += 1
        except (TypeError, AttributeError):
            skipped += 1
    plant_ids = {p.id for p in plants}
    for item in logs_raw:
        try:
            log = CareEntry.from_dict(item)
            if _valid_log(log) and log.plant_id in plant_ids:
                logs.append(log)
            else:
                skipped += 1
        except (TypeError, AttributeError):
            skipped += 1
    notice = f"{skipped} invalid record(s) in the data file were skipped." if skipped else None
    return Database(plants, logs), notice
