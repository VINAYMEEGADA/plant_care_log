import csv
import io
import unittest
from datetime import date

from core import logic, reports, search
from core.importer import errors_to_csv, import_plants_csv
from core.sample_data import IMPORT_WITH_ERRORS, build_sample_db

TODAY = date(2026, 11, 25)


class ImporterTests(unittest.TestCase):
    def test_sample_with_errors(self):
        r = import_plants_csv(IMPORT_WITH_ERRORS.encode("utf-8"), existing_names=[], today=TODAY)
        self.assertEqual(r.total_rows, 15)
        self.assertEqual([c["name"] for c in r.cleaned], ["Lavender", "Dill", "Rose Bush", "Jade Baby"])
        self.assertEqual(len({e["Row"] for e in r.errors}), 11)
        self.assertTrue(all(e["Problem"] for e in r.errors))
        dup = [e for e in r.errors if "already exists" in e["Problem"]]
        self.assertEqual(len(dup), 1)

    def test_error_log_csv_round_trip(self):
        r = import_plants_csv(IMPORT_WITH_ERRORS, [], TODAY)
        rows = list(csv.DictReader(io.StringIO(errors_to_csv(r.errors))))
        self.assertEqual(len(rows), len(r.errors))

    def test_existing_names_conflict(self):
        r = import_plants_csv(IMPORT_WITH_ERRORS, ["lavender"], TODAY)
        self.assertNotIn("Lavender", [c["name"] for c in r.cleaned])

    def test_file_level_problems(self):
        self.assertIsNotNone(import_plants_csv(b"", [], TODAY).fatal)
        self.assertIn("Missing", import_plants_csv("a,b\n1,2\n", [], TODAY).fatal)

    def test_bom_header_case_and_latin1(self):
        text = "\ufeffName,Category,Watering_Interval_Days,Last_Watered\nCaf\u00e9 Palm,Indoor,5,2026-11-20\n"
        self.assertEqual(len(import_plants_csv(text.encode("utf-8"), [], TODAY).cleaned), 1)
        self.assertEqual(len(import_plants_csv(text.lstrip("\ufeff").encode("cp1252"), [], TODAY).cleaned), 1)

    def test_too_many_columns(self):
        text = "name,category,watering_interval_days,last_watered\nFern,Indoor,5,2026-11-20,extra\n"
        r = import_plants_csv(text, [], TODAY)
        self.assertEqual((len(r.cleaned), len(r.errors)), (0, 1))


class SearchTests(unittest.TestCase):
    def setUp(self):
        self.db = build_sample_db(TODAY)

    def test_keyword_and_category(self):
        hits = search.filter_plants(self.db.plants, self.db.logs, "basil", today=TODAY)
        self.assertEqual([p.name for p in hits if p.name == "Basil"], ["Basil"])
        herbs = search.filter_plants(self.db.plants, self.db.logs, categories=["Herb"], today=TODAY)
        self.assertEqual(len(herbs), 7)

    def test_all_tokens_must_match(self):
        self.assertEqual(search.filter_plants(self.db.plants, self.db.logs, "basil zzzz", today=TODAY), [])

    def test_status_filter(self):
        over = search.filter_plants(self.db.plants, self.db.logs, statuses=["Overdue"], today=TODAY)
        self.assertTrue(over and all(logic.status(p, TODAY) == "Overdue" for p in over))

    def test_log_search(self):
        rows = search.search_logs(self.db.logs, self.db.plants, actions=["Fertilized"])
        self.assertTrue(rows and all(r["Action"] == "Fertilized" for r in rows))
        self.assertEqual(rows, sorted(rows, key=lambda r: (r["Date"], r["Plant"]), reverse=True))
        none = search.search_logs(self.db.logs, self.db.plants, start=date(2030, 1, 1))
        self.assertEqual(none, [])


class ReportTests(unittest.TestCase):
    def setUp(self):
        self.db = build_sample_db(TODAY)
        self.rows = logic.plant_rows(self.db.plants, TODAY)
        self.summary = logic.summary(self.db.plants, self.db.logs, TODAY)
        self.warnings = logic.anomalies(self.db.plants, self.db.logs, TODAY)

    def test_sample_data_shape(self):
        self.assertEqual(len(self.db.plants), 40)
        statuses = {r["Status"] for r in self.rows}
        self.assertEqual(statuses, set(logic.STATUS_ORDER))   # demo shows every status
        types = {w["type"] for w in self.warnings}
        self.assertTrue({"Overdue", "Over-watering?", "Large volume"} <= types)

    def test_markdown_and_text(self):
        md = reports.build_markdown(self.summary, self.rows, self.warnings, TODAY)
        self.assertIn("# Plant Care Log - Summary Report", md)
        self.assertIn("Total plants: **40**", md)
        txt = reports.build_text_audit(self.db.plants, self.db.logs, self.warnings, TODAY)
        self.assertIn("CARE HISTORY", txt)
        self.assertEqual(txt.count("\n"), len(txt.splitlines()))

    def test_csv_exports_parse_and_neutralise_formulas(self):
        parsed = list(csv.DictReader(io.StringIO(reports.plants_csv(self.rows))))
        self.assertEqual(len(parsed), 40)
        evil = [{**self.rows[0], "Name": "=HYPERLINK(\"x\")"}]
        first = next(csv.DictReader(io.StringIO(reports.plants_csv(evil))))
        self.assertTrue(first["Name"].startswith("'="))
        logs = list(csv.DictReader(io.StringIO(reports.logs_csv(self.db.plants, self.db.logs))))
        self.assertEqual(len(logs), len(self.db.logs))

    def test_charts_render(self):
        from core import charts
        for fn in (charts.fig_status, charts.fig_trend, charts.fig_category, charts.fig_intervals):
            self.assertTrue(charts.fig_to_png(fn(self.summary)).startswith(b"\x89PNG"))
            empty = logic.summary([], [], TODAY)
            self.assertTrue(charts.fig_to_png(fn(empty)).startswith(b"\x89PNG"))


if __name__ == "__main__":
    unittest.main()
