# 🌿 Plant Care Log

SmartCommunity Hack - Project #45 (Environment & Sustainability).
Track watering dates and care notes for your plants, with strict input validation,
local JSON persistence, search, summaries, Matplotlib charts and report export.
Web interface built with **Streamlit**.

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

On first launch the app is empty. Open **🗂️ Data & Import → Load sample data** to get
40 realistic plants with care history (every status, plus a few suspicious entries to
trigger the warnings).

Run the tests (standard library only, no extra installs):

```bash
python -m unittest discover -s tests -t .
```

## Features (mapped to the brief)

| Brief requirement | Where |
|---|---|
| Interactive interface | Streamlit app, sidebar navigation (`app.py`) |
| Defensive input validation | `core/validation.py` - every field, enforced server-side; forms are plain text inputs so bad values reach the validator and are explained, not silently blocked |
| Core logic engine | `core/logic.py` - next-due date, status (Overdue / Due today / Due soon / OK), averages, weekly trend |
| Local persistence | `core/storage.py` - JSON, atomic writes, corrupt/missing file recovery (corrupt file is kept as `plants.json.corrupt-<timestamp>`) |
| Query & search | `core/search.py` - multi-keyword AND search, category / status / action / date filters |
| Executive summary | Summary page + Markdown report |
| Matplotlib charts | `core/charts.py` - status, weekly trend, category, interval distribution (PNG download) |
| Multi-format export (stretch) | Markdown, plain-text audit log, CSV (plants + history) |
| Threshold warnings (stretch) | Dashboard banners: overdue (critical when overdue by a full interval), double watering, > 2000 ml |
| Bulk CSV import (stretch) | `core/importer.py` - row-by-row error log, downloadable |
| GUI (stretch) | Streamlit |

## Project layout

```
app.py                  Streamlit UI
generate_samples.py     Rebuilds data/sample_* files (dates relative to today)
core/                   UI-independent logic (reusable from NiceGUI/FastHTML/CLI)
tests/                  42 unit tests
data/sample_plants.json / .csv, sample_import_with_errors.csv
data/plants.json        Live data (auto-created, git-ignored)
```

Set `PLANT_LOG_DATA=/path/to/file.json` to store the data somewhere else.

## Validation rules

- Name: required, 2-50 chars, letters/digits/spaces and `- ' . & ( ) ,`; unique (case-insensitive)
- Category: Indoor, Outdoor, Succulent, Herb, Vegetable, Flower
- Watering interval: whole number 1-60 days
- Dates: `YYYY-MM-DD` (also `DD/MM/YYYY`), not in the future, not before 2000-01-01
- Water amount: 0-5000 ml, only on "Watered" entries
- Notes: up to 500 chars; a "Note" entry needs text

## Demo script (≈ 4 minutes)

1. `streamlit run app.py`, show the branded header and sidebar menu.
2. **Data & Import → Load sample data**; the dashboard shows warnings and overdue plants.
3. **Add Plant** with a blank name, interval `999` and date `2099-01-01`; show the errors, then fix and save.
4. **Data & Import**: upload `data/sample_import_with_errors.csv`; show the row-by-row error log, import the 4 valid rows.
5. **Summary & Charts**: metrics and the four charts.
6. Stop the server (Ctrl+C) and relaunch; the data is still there.
7. **Export Reports**: download the Markdown summary.

## Design notes

- Logging a "Watered" entry moves the plant's schedule forward; back-dated entries never move it backwards.
- Adding a plant records its last-watered date but does not create a log entry, so charts reflect only logged care.
- Exports prefix cells starting with `= + - @` with `'` to prevent spreadsheet formula injection.
- Swapping to NiceGUI or FastHTML only requires rewriting `app.py`; `core/` has no UI dependency.
