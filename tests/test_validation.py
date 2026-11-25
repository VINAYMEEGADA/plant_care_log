import unittest
from datetime import date

from core import validation as v

TODAY = date(2026, 11, 25)


class NameTests(unittest.TestCase):
    def test_valid_and_trimmed(self):
        self.assertEqual(v.validate_name("  Peace   Lily ")[1], "Peace Lily")

    def test_blank_short_long_and_chars(self):
        self.assertFalse(v.validate_name("")[0])
        self.assertFalse(v.validate_name("   ")[0])
        self.assertFalse(v.validate_name("A")[0])
        self.assertTrue(v.validate_name("A" * 50)[0])
        self.assertFalse(v.validate_name("A" * 51)[0])
        self.assertFalse(v.validate_name("Rose<script>")[0])
        self.assertFalse(v.validate_name(None)[0])


class DateTests(unittest.TestCase):
    def test_formats(self):
        self.assertEqual(v.validate_date("2026-11-20", today=TODAY)[1], date(2026, 11, 20))
        self.assertEqual(v.validate_date("20/11/2026", today=TODAY)[1], date(2026, 11, 20))
        self.assertEqual(v.validate_date(date(2026, 1, 1), today=TODAY)[1], date(2026, 1, 1))

    def test_boundaries(self):
        self.assertTrue(v.validate_date("2026-11-25", today=TODAY)[0])      # today is fine
        self.assertFalse(v.validate_date("2026-11-26", today=TODAY)[0])     # future
        self.assertTrue(v.validate_date("2000-01-01", today=TODAY)[0])
        self.assertFalse(v.validate_date("1999-12-31", today=TODAY)[0])

    def test_garbage(self):
        for bad in ("", "tomorrow", "2026-13-01", "31/02/2026", None):
            self.assertFalse(v.validate_date(bad, today=TODAY)[0], bad)


class IntervalTests(unittest.TestCase):
    def test_valid(self):
        for good in ("1", " 7 ", 60, 14.0):
            self.assertTrue(v.validate_interval(good)[0], good)

    def test_invalid(self):
        for bad in ("0", "61", "-3", "abc", "", "7.5", 7.5, True, float("nan"), float("inf"), None):
            self.assertFalse(v.validate_interval(bad)[0], bad)


class WaterTests(unittest.TestCase):
    def test_optional_and_range(self):
        self.assertEqual(v.validate_water_ml(""), (True, None, None))
        self.assertEqual(v.validate_water_ml("250")[1], 250)
        self.assertTrue(v.validate_water_ml("0")[0])
        self.assertTrue(v.validate_water_ml("5000")[0])
        for bad in ("5001", "-1", "lots", "nan", "inf"):
            self.assertFalse(v.validate_water_ml(bad)[0], bad)


class FormTests(unittest.TestCase):
    def good(self, **over):
        raw = {"name": "Basil", "species": "Ocimum", "category": "herb", "location": "Kitchen",
               "watering_interval_days": "2", "last_watered": "2026-11-24", "notes": ""}
        raw.update(over)
        return raw

    def test_valid_plant(self):
        cleaned, errors = v.validate_plant_form(self.good(), today=TODAY)
        self.assertEqual(errors, {})
        self.assertEqual(cleaned["category"], "Herb")   # canonical casing
        self.assertEqual(cleaned["watering_interval_days"], 2)

    def test_collects_all_errors(self):
        _, errors = v.validate_plant_form(
            self.good(name="", category="Cactus", watering_interval_days="999", last_watered="2099-01-01"),
            today=TODAY)
        self.assertEqual(set(errors), {"Name", "Category", "Watering interval", "Last watered"})

    def test_duplicate_name_case_insensitive(self):
        _, errors = v.validate_plant_form(self.good(name="basil"), existing_names=["BASIL"], today=TODAY)
        self.assertIn("Name", errors)

    def test_care_form(self):
        ok, e = v.validate_care_form({"date": "2026-11-25", "action": "watered", "water_ml": "300"}, TODAY)
        self.assertEqual(e, {})
        self.assertEqual(ok["action"], "Watered")
        _, e = v.validate_care_form({"date": "2026-11-25", "action": "Pruned", "water_ml": "300"}, TODAY)
        self.assertIn("Water amount", e)
        _, e = v.validate_care_form({"date": "2026-11-25", "action": "Note", "notes": ""}, TODAY)
        self.assertIn("Notes", e)
        _, e = v.validate_care_form({"date": "", "action": "Dance"}, TODAY)
        self.assertEqual(set(e), {"Date", "Action"})


if __name__ == "__main__":
    unittest.main()
