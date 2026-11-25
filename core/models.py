"""Data structures for Plant Care Log."""
from __future__ import annotations

from dataclasses import asdict, dataclass, fields


@dataclass
class Plant:
    id: str
    name: str
    species: str
    category: str
    location: str
    watering_interval_days: int
    last_watered: str  # ISO date, YYYY-MM-DD
    created_at: str    # ISO date
    notes: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Plant":
        names = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in data.items() if k in names})


@dataclass
class CareEntry:
    id: str
    plant_id: str
    date: str          # ISO date
    action: str        # one of validation.ACTIONS
    notes: str = ""
    water_ml: int | None = None

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "CareEntry":
        names = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in data.items() if k in names})
