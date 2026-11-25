import json
import tempfile
import unittest
from datetime import date
from pathlib import Path

from core.sample_data import build_sample_db
from core.storage import Database, load_db, save_db

TODAY = date(2026, 11, 25)
GOOD = {"name": "Basil", "species": "", "category": "Herb", "location": "",
        "watering_interval_days": 2, "last_watered": date(2026, 11, 20), "notes": ""}


class StorageTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "data" / "plants.json"

    def tearDown(self):
        self.tmp.cleanup()

    def test_missing_file_creates_template(self):
        db, notice = load_db(self.path)
        self.assertEqual((db.plants, db.logs, notice), ([], [], None))
        self.assertTrue(self.path.exists())

    def test_round_trip(self):
        db = Database()
        p = db.add_plant(dict(GOOD), TODAY)
        db.add_log(p.id, {"date": date(2026, 11, 24), "action": "Watered", "notes": "", "water_ml": 250})
        save_db(db, self.path)
        again, notice = load_db(self.path)
        self.assertIsNone(notice)
        self.assertEqual(again.to_dict(), db.to_dict())

    def test_corrupt_json_is_backed_up(self):
        self.path.parent.mkdir(parents=True)
        self.path.write_text("{ not json", encoding="utf-8")
        db, notice = load_db(self.path)
        self.assertEqual(db.plants, [])
        self.assertIn("corrupt", notice.lower())
        self.assertEqual(len(list(self.path.parent.glob("plants.json.corrupt-*"))), 1)
        self.assertEqual(json.loads(self.path.read_text())["plants"], [])

    def test_wrong_structure_and_empty_file(self):
        self.path.parent.mkdir(parents=True)
        for content in ('["a list"]', '{"plants": "nope"}', ""):
            self.path.write_text(content, encoding="utf-8")
            db, notice = load_db(self.path)
            self.assertEqual(db.plants, [])
            self.assertIsNotNone(notice, content)

    def test_bad_records_skipped(self):
        self.path.parent.mkdir(parents=True)
        good = build_sample_db(TODAY).to_dict()
        raw = {"plants": good["plants"][:2] + [{"id": "x"}, {"id": "y", "name": "Bad", "species": "", "category": "Indoor",
               "location": "", "watering_interval_days": 7, "last_watered": "not-a-date", "created_at": "2026-01-01"}],
               "logs": good["logs"][:3] + [{"id": "z", "plant_id": "ghost", "date": "2026-01-01", "action": "Watered"}]}
        self.path.write_text(json.dumps(raw), encoding="utf-8")
        db, notice = load_db(self.path)
        self.assertEqual(len(db.plants), 2)
        self.assertIn("skipped", notice)
        self.assertTrue(all(l.plant_id in {p.id for p in db.plants} for l in db.logs))

    def test_watering_updates_schedule_but_backdating_does_not(self):
        db = Database()
        p = db.add_plant(dict(GOOD), TODAY)
        db.add_log(p.id, {"date": date(2026, 11, 24), "action": "Watered", "notes": "", "water_ml": None})
        self.assertEqual(p.last_watered, "2026-11-24")
        db.add_log(p.id, {"date": date(2026, 11, 1), "action": "Watered", "notes": "", "water_ml": None})
        self.assertEqual(p.last_watered, "2026-11-24")
        db.add_log(p.id, {"date": date(2026, 11, 25), "action": "Pruned", "notes": "", "water_ml": None})
        self.assertEqual(p.last_watered, "2026-11-24")

    def test_delete_plant_removes_logs_and_update(self):
        db = Database()
        p = db.add_plant(dict(GOOD), TODAY)
        db.add_log(p.id, {"date": date(2026, 11, 24), "action": "Note", "notes": "hi", "water_ml": None})
        db.update_plant(p.id, dict(GOOD, name="Sweet Basil"))
        self.assertEqual(db.get_plant(p.id).name, "Sweet Basil")
        db.delete_plant(p.id)
        self.assertEqual((db.plants, db.logs), ([], []))


if __name__ == "__main__":
    unittest.main()
