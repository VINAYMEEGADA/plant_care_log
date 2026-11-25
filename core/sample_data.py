"""Deterministic, realistic sample data (40 plants + care history) for demos and tests."""
from __future__ import annotations

import csv
import random
from datetime import date, timedelta
from pathlib import Path

from .models import CareEntry, Plant
from .storage import Database, save_db

# name, species, category, interval (days)
PLANTS = [
    ("Monstera", "Monstera deliciosa", "Indoor", 7), ("Peace Lily", "Spathiphyllum", "Indoor", 5),
    ("Snake Plant", "Dracaena trifasciata", "Indoor", 14), ("Pothos", "Epipremnum aureum", "Indoor", 7),
    ("Fiddle Leaf Fig", "Ficus lyrata", "Indoor", 8), ("Rubber Plant", "Ficus elastica", "Indoor", 10),
    ("ZZ Plant", "Zamioculcas zamiifolia", "Indoor", 21), ("Spider Plant", "Chlorophytum comosum", "Indoor", 6),
    ("Boston Fern", "Nephrolepis exaltata", "Indoor", 3), ("Calathea", "Calathea orbifolia", "Indoor", 4),
    ("Heartleaf Philodendron", "Philodendron hederaceum", "Indoor", 7),
    ("Aloe Vera", "Aloe barbadensis", "Succulent", 14), ("Jade Plant", "Crassula ovata", "Succulent", 14),
    ("Echeveria", "Echeveria elegans", "Succulent", 12), ("Haworthia", "Haworthiopsis attenuata", "Succulent", 15),
    ("String of Pearls", "Senecio rowleyanus", "Succulent", 10), ("Christmas Cactus", "Schlumbergera", "Succulent", 9),
    ("Barrel Cactus", "Echinocactus grusonii", "Succulent", 60), ("Burro's Tail", "Sedum morganianum", "Succulent", 12),
    ("Basil", "Ocimum basilicum", "Herb", 2), ("Mint", "Mentha spicata", "Herb", 2),
    ("Coriander", "Coriandrum sativum", "Herb", 3), ("Curry Leaf", "Murraya koenigii", "Herb", 4),
    ("Tulsi", "Ocimum tenuiflorum", "Herb", 2), ("Rosemary", "Salvia rosmarinus", "Herb", 6),
    ("Thyme", "Thymus vulgaris", "Herb", 5),
    ("Tomato", "Solanum lycopersicum", "Vegetable", 2), ("Chilli Pepper", "Capsicum annuum", "Vegetable", 3),
    ("Brinjal", "Solanum melongena", "Vegetable", 3), ("Okra", "Abelmoschus esculentus", "Vegetable", 2),
    ("Spinach", "Spinacia oleracea", "Vegetable", 1),
    ("Hibiscus", "Hibiscus rosa-sinensis", "Flower", 2), ("Jasmine", "Jasminum sambac", "Flower", 3),
    ("Rose", "Rosa", "Flower", 3), ("Marigold", "Tagetes", "Flower", 2),
    ("Orchid", "Phalaenopsis", "Flower", 7), ("Bougainvillea", "Bougainvillea glabra", "Flower", 5),
    ("Banana Plant", "Musa", "Outdoor", 3), ("Lemon Tree", "Citrus limon", "Outdoor", 4),
    ("Areca Palm", "Dypsis lutescens", "Outdoor", 5),
]
assert len(PLANTS) == 40

LOCATIONS = ["Living room", "Balcony", "Bedroom", "Kitchen", "Terrace", "Garden", "Office desk", "Study"]
PLANT_NOTES = ["Bright indirect light", "Prefers morning sun", "Let top soil dry between waterings",
               "Mist leaves weekly", "Keep away from AC vent", "Needs well-draining soil", "", "", ""]
LOG_NOTES = {
    "Fertilized": ["Liquid feed, half strength", "Organic compost top-up", "Slow-release pellets"],
    "Pruned": ["Removed yellow leaves", "Trimmed leggy growth", "Pinched tips for bushier growth"],
    "Repotted": ["Moved to a larger pot", "Fresh potting mix"],
    "Note": ["New leaf spotted", "Slight leaf curl - watching", "Moved closer to window", "Looks healthy"],
}
WATER_RANGE = {"Indoor": (200, 400), "Succulent": (80, 150), "Herb": (150, 250),
               "Vegetable": (500, 900), "Flower": (300, 600), "Outdoor": (800, 1500)}
DAYS_AGO_OVERRIDE = {"Spinach": 0, "Barrel Cactus": 75, "Boston Fern": 12, "Monstera": 7, "Tomato": 0, "Orchid": 3}
NO_LOGS = {"Orchid"}  # edge case: a plant with no care history

# Deliberately imperfect rows to demo the importer's row-by-row error log.
IMPORT_WITH_ERRORS = """name,species,category,location,watering_interval_days,last_watered,notes
Lavender,Lavandula,Flower,Terrace,6,2026-11-20,Full sun
Dill,Anethum graveolens,Herb,Kitchen,3,2026-11-22,
,Ficus,Indoor,Hall,7,2026-11-20,Blank name
Cherry Tomato,Solanum,Vegetable,Garden,abc,2026-11-21,Non-numeric interval
Bonsai Juniper,Juniperus,Outdoor,Balcony,0,2026-11-18,Interval too small
Fern Deluxe,Nephrolepis,Indoor,Hall,500,2026-11-18,Interval too large
Time Traveller,Unknown,Indoor,Lab,5,2099-01-01,Future date
Ancient Aloe,Aloe,Succulent,Shelf,14,1999-12-31,Before 2000
Sunflower,Helianthus,Flower,Garden,4,15-13-2026,Impossible date
Cactus Joe,Opuntia,Cactus,Desk,20,2026-11-10,Unknown category
Lavender,Lavandula,Flower,Terrace,6,2026-11-20,Duplicate inside the file
Rose Bush,Rosa,Flower,Garden,3,2026-11-23,"Valid, with a comma in the notes"
Mint Extra,Mentha,Herb,Kitchen,2
Peace Lily!!!@@,Spathiphyllum,Indoor,Hall,5,2026-11-19,Bad characters in name
Jade Baby,Crassula,Succulent,Window,14,24/11/2026,Valid DD/MM/YYYY date
"""


def build_sample_db(today: date | None = None, seed: int = 45) -> Database:
    today = today or date.today()
    rng = random.Random(seed)
    plants: list[Plant] = []
    logs: list[CareEntry] = []
    log_no = 0

    def add_log(plant_id, d, action, notes="", ml=None):
        nonlocal log_no
        log_no += 1
        logs.append(CareEntry(id=f"l{log_no:04d}", plant_id=plant_id, date=d.isoformat(),
                              action=action, notes=notes, water_ml=ml))

    for idx, (name, species, cat, interval) in enumerate(PLANTS, start=1):
        pid = f"p{idx:03d}"
        days_ago = DAYS_AGO_OVERRIDE.get(name, rng.randint(0, int(interval * 1.4)))
        last = today - timedelta(days=days_ago)
        plants.append(Plant(
            id=pid, name=name, species=species, category=cat, location=rng.choice(LOCATIONS),
            watering_interval_days=interval, last_watered=last.isoformat(),
            created_at=(today - timedelta(days=120)).isoformat(), notes=rng.choice(PLANT_NOTES),
        ))
        if name in NO_LOGS:
            continue

        lo, hi = WATER_RANGE[cat]
        d = last
        for _ in range(rng.randint(2, 6)):
            if d < today - timedelta(days=100):
                break
            add_log(pid, d, "Watered", ml=rng.randrange(lo, hi + 1, 10))
            d -= timedelta(days=max(1, interval + rng.randint(-1, 1)) if interval > 1 else 1)

        for action, chance in (("Fertilized", 0.25), ("Pruned", 0.15), ("Repotted", 0.08), ("Note", 0.3)):
            if rng.random() < chance:
                add_log(pid, today - timedelta(days=rng.randint(1, 40)), action, rng.choice(LOG_NOTES[action]))

        # Planted anomalies so the warning indicators have something to show.
        if name == "Peace Lily":
            add_log(pid, last, "Watered", "Accidentally watered twice", 250)
        elif name == "Fiddle Leaf Fig":
            add_log(pid, last - timedelta(days=1), "Watered", "Extra drink after repotting", 300)
        elif name == "Rubber Plant":
            add_log(pid, last, "Watered", "Left the hose running", 3500)

    return Database(plants, logs)


def write_sample_files(out_dir, today: date | None = None) -> list[Path]:
    """Write sample_plants.json / sample_plants.csv / sample_import_with_errors.csv."""
    today = today or date.today()
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    db = build_sample_db(today)

    json_path = out / "sample_plants.json"
    save_db(db, json_path)

    csv_path = out / "sample_plants.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["name", "species", "category", "location", "watering_interval_days", "last_watered", "notes"])
        for p in db.plants:
            writer.writerow([p.name, p.species, p.category, p.location,
                             p.watering_interval_days, p.last_watered, p.notes])

    bad_path = out / "sample_import_with_errors.csv"
    bad_path.write_text(IMPORT_WITH_ERRORS, encoding="utf-8")
    return [json_path, csv_path, bad_path]
