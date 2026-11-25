import unittest
from datetime import date

from core import logic
from core.models import CareEntry, Plant

TODAY = date(2026, 11, 25)


def plant(pid="p1", name="Fern", interval=7, last="2026-11-20", cat="Indoor"):
    return Plant(id=pid, name=name, species="", category=cat, location="",
                 watering_interval_days=interval, last_watered=last, created_at="2026-01-01")


def log(i, pid, d, action="Watered", ml=None, notes=""):
    return CareEntry(id=f"l{i}", plant_id=pid, date=d, action=action, notes=notes, water_ml=ml)


class StatusTests(unittest.TestCase):
    def test_next_due(self):
        self.assertEqual(logic.next_due(plant()).isoformat(), "2026-11-27")

    def test_status_boundaries(self):
        # interval 7: last 11-17 -> due 11-24 (yesterday) overdue; 11-18 -> today; 11-19/11-20 soon; 11-21 ok
        expected = {"2026-11-17": "Overdue", "2026-11-18": "Due today", "2026-11-19": "Due soon",
                    "2026-11-20": "Due soon", "2026-11-21": "OK"}
        for last, want in expected.items():
            self.assertEqual(logic.status(plant(last=last), TODAY), want, last)

    def test_rows_sorted_most_urgent_first(self):
        rows = logic.plant_rows([plant("a", "A", last="2026-11-24"), plant("b", "B", last="2026-11-01")], TODAY)
        self.assertEqual([r["Name"] for r in rows], ["B", "A"])


class SummaryTests(unittest.TestCase):
    def test_empty(self):
        s = logic.summary([], [], TODAY)
        self.assertEqual(s["total_plants"], 0)
        self.assertIsNone(s["avg_interval_days"])
        self.assertIsNone(s["most_cared"])
        self.assertEqual(len(s["weekly_trend"]), logic.TREND_WEEKS)

    def test_metrics(self):
        plants = [plant("a", "A", 7, "2026-11-24"), plant("b", "B", 3, "2026-11-10", "Herb")]
        logs = [log(1, "a", "2026-11-17", ml=200), log(2, "a", "2026-11-24", ml=400),
                log(3, "a", "2026-11-24", "Note", notes="hi")]
        s = logic.summary(plants, logs, TODAY)
        self.assertEqual(s["avg_interval_days"], 5.0)
        self.assertEqual(s["avg_gap_days"], 7.0)
        self.assertEqual(s["waterings_last_7"], 1)
        self.assertEqual(s["waterings_last_30"], 2)
        self.assertEqual(s["avg_water_ml"], 300)
        self.assertEqual(s["most_cared"], ("A", 3))
        self.assertEqual(s["least_cared"], ("B", 0))
        self.assertEqual(s["status_counts"]["Overdue"], 1)
        self.assertEqual(s["category_counts"], {"Herb": 1, "Indoor": 1})
        self.assertEqual(sum(c for _, c in s["weekly_trend"]), 2)


class AnomalyTests(unittest.TestCase):
    def test_overdue_severity(self):
        warn = logic.anomalies([plant("a", "Mild", 7, "2026-11-15"), plant("b", "Bad", 7, "2026-11-01")], [], TODAY)
        sev = {w["plant"]: w["severity"] for w in warn}
        self.assertEqual(sev, {"Bad": "critical", "Mild": "warning"})
        self.assertEqual(warn[0]["plant"], "Bad")   # critical first

    def test_double_watering_and_large_volume(self):
        p = plant("a", "Fig", 8, "2026-11-24")
        logs = [log(1, "a", "2026-11-23"), log(2, "a", "2026-11-24", ml=3500)]
        types = {w["type"] for w in logic.anomalies([p], logs, TODAY)}
        self.assertEqual(types, {"Over-watering?", "Large volume"})

    def test_old_entries_ignored(self):
        p = plant("a", "Fig", 8, "2026-11-24")
        logs = [log(1, "a", "2026-08-01"), log(2, "a", "2026-08-01", ml=4000)]
        self.assertEqual(logic.anomalies([p], logs, TODAY), [])

    def test_healthy_plant_has_no_warnings(self):
        self.assertEqual(logic.anomalies([plant(last="2026-11-24")], [log(1, "p1", "2026-11-24", ml=250)], TODAY), [])


if __name__ == "__main__":
    unittest.main()
