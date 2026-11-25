"""Plant Care Log - Streamlit interface.

Run with:  streamlit run app.py
"""
from __future__ import annotations

import json
import os
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import streamlit as st

from core import charts, logic, reports, search
from core.importer import TEMPLATE, errors_to_csv, import_plants_csv
from core.sample_data import build_sample_db
from core.storage import Database, load_db, save_db
from core.validation import ACTIONS, CATEGORIES, validate_care_form, validate_plant_form

ROOT = Path(__file__).parent
DATA_PATH = Path(os.environ.get("PLANT_LOG_DATA", ROOT / "data" / "plants.json"))

STATUS_ICON = {"Overdue": "🔴 Overdue", "Due today": "🟠 Due today", "Due soon": "🟡 Due soon", "OK": "🟢 OK"}
PAGES = ["📋 Dashboard", "🌱 My Plants", "➕ Add Plant", "💧 Log Care", "🔎 Search",
         "📊 Summary & Charts", "📤 Export Reports", "🗂️ Data & Import"]


# ----------------------------------------------------------------- helpers
def persist() -> None:
    try:
        save_db(st.session_state.db, DATA_PATH)
    except OSError as exc:
        st.error(f"Could not save data to {DATA_PATH}: {exc}")


def flash(message: str, kind: str = "success") -> None:
    st.session_state.setdefault("flash", []).append((kind, message))


def show_flash() -> None:
    for kind, message in st.session_state.pop("flash", []):
        getattr(st, kind)(message)


def show_errors(errors: dict) -> None:
    st.error("Please fix the following and try again:\n\n" + "\n".join(f"- **{k}:** {v}" for k, v in errors.items()))


def table(rows: list[dict], hide: tuple = ("ID",)) -> None:
    if not rows:
        st.info("Nothing to show.")
        return
    df = pd.DataFrame(rows)
    if "Status" in df:
        df["Status"] = df["Status"].map(lambda s: STATUS_ICON.get(s, s))
    st.dataframe(df.drop(columns=[c for c in hide if c in df]), hide_index=True)


def plant_picker(db: Database, key: str, label: str = "Plant") -> str | None:
    if not db.plants:
        st.info("No plants yet. Add one first (or load the sample data from **Data & Import**).")
        return None
    ordered = sorted(db.plants, key=lambda p: p.name.lower())
    names = {p.id: f"{p.name} ({p.category})" for p in ordered}
    return st.selectbox(label, [p.id for p in ordered], format_func=names.get, key=key)


def chart_with_download(fig, filename: str) -> None:
    st.pyplot(fig)
    st.download_button("⬇️ PNG", charts.fig_to_png(fig), file_name=filename, mime="image/png", key=f"dl_{filename}")


# ------------------------------------------------------------------- pages
def page_dashboard(db: Database, today: date) -> None:
    st.subheader("Dashboard")
    s = logic.summary(db.plants, db.logs, today)
    cols = st.columns(5)
    cols[0].metric("Plants", s["total_plants"])
    for col, status in zip(cols[1:], logic.STATUS_ORDER):
        col.metric(STATUS_ICON[status], s["status_counts"][status])

    if not db.plants:
        st.info("Welcome! Add your first plant, or load 40 realistic sample plants from **🗂️ Data & Import**.")
        return

    warnings = logic.anomalies(db.plants, db.logs, today)
    if warnings:
        st.markdown("#### ⚠️ Warnings")
        for w in warnings[:12]:
            (st.error if w["severity"] == "critical" else st.warning)(w["message"])
        if len(warnings) > 12:
            st.caption(f"…and {len(warnings) - 12} more. See the Export page for the full list.")

    st.markdown("#### Needs attention")
    rows = [r for r in logic.plant_rows(db.plants, today) if r["Status"] != "OK"]
    if not rows:
        st.success("Everything is on schedule. 🌿")
        return
    table(rows)

    st.markdown("**Quick action:** mark as watered today")
    for r in rows[:8]:
        if st.button(f"💧 {r['Name']}", key=f"quick_{r['ID']}"):
            cleaned, errors = validate_care_form({"date": today, "action": "Watered"}, today)
            if errors:
                show_errors(errors)
            else:
                db.add_log(r["ID"], cleaned)
                persist()
                flash(f"Logged watering for {r['Name']}.")
                st.rerun()


def page_plants(db: Database, today: date) -> None:
    st.subheader("My plants")
    table(logic.plant_rows(db.plants, today))
    pid = plant_picker(db, "manage_plant", "Manage a plant")
    if pid is None:
        return
    plant = db.get_plant(pid)
    tab_edit, tab_history, tab_delete = st.tabs(["✏️ Edit", "📜 History", "🗑️ Delete"])

    with tab_edit:
        with st.form(f"edit_{pid}"):
            c1, c2 = st.columns(2)
            name = c1.text_input("Plant name *", value=plant.name)
            species = c2.text_input("Species", value=plant.species)
            category = c1.selectbox("Category *", CATEGORIES, index=CATEGORIES.index(plant.category)
                                    if plant.category in CATEGORIES else 0)
            location = c2.text_input("Location", value=plant.location)
            interval = c1.text_input("Watering interval (days) *", value=str(plant.watering_interval_days))
            last = c2.text_input("Last watered * (YYYY-MM-DD)", value=plant.last_watered)
            notes = st.text_area("Care notes", value=plant.notes)
            submitted = st.form_submit_button("Save changes")
        if submitted:
            others = [n for n in db.plant_names() if n != plant.name]
            cleaned, errors = validate_plant_form(
                {"name": name, "species": species, "category": category, "location": location,
                 "watering_interval_days": interval, "last_watered": last, "notes": notes},
                existing_names=others, today=today)
            if errors:
                show_errors(errors)
            else:
                db.update_plant(pid, cleaned)
                persist()
                flash(f"Updated {cleaned['name']}.")
                st.rerun()

    with tab_history:
        rows = search.search_logs(db.logs_for(pid), db.plants)
        table(rows, hide=())

    with tab_delete:
        st.warning(f"This permanently deletes **{plant.name}** and its {len(db.logs_for(pid))} care entries.")
        confirm = st.checkbox("Yes, delete it", key=f"del_ok_{pid}")
        if st.button("Delete plant", disabled=not confirm, key=f"del_{pid}"):
            db.delete_plant(pid)
            persist()
            flash(f"Deleted {plant.name}.")
            st.rerun()


def page_add_plant(db: Database, today: date) -> None:
    st.subheader("Add a plant")
    st.caption("Fields marked * are required. Everything you enter is validated before it is saved.")
    with st.form("add_plant"):
        c1, c2 = st.columns(2)
        name = c1.text_input("Plant name *")
        species = c2.text_input("Species")
        category = c1.selectbox("Category *", CATEGORIES)
        location = c2.text_input("Location", placeholder="e.g. Balcony")
        interval = c1.text_input("Watering interval (days) *", value="7", help="Whole number from 1 to 60")
        last = c2.text_input("Last watered * (YYYY-MM-DD)", value=today.isoformat())
        notes = st.text_area("Care notes")
        submitted = st.form_submit_button("Save plant")
    if submitted:
        cleaned, errors = validate_plant_form(
            {"name": name, "species": species, "category": category, "location": location,
             "watering_interval_days": interval, "last_watered": last, "notes": notes},
            existing_names=db.plant_names(), today=today)
        if errors:
            show_errors(errors)
        else:
            plant = db.add_plant(cleaned, today)
            persist()
            flash(f"Added {plant.name}. Next watering due {logic.next_due(plant).isoformat()}.")
            st.rerun()


def page_log_care(db: Database, today: date) -> None:
    st.subheader("Log care")
    pid = plant_picker(db, "log_plant")
    if pid is None:
        return
    plant = db.get_plant(pid)
    st.caption(f"Last watered {plant.last_watered} · every {plant.watering_interval_days} days · "
               f"status: {STATUS_ICON[logic.status(plant, today)]}")
    with st.form(f"log_{pid}"):
        c1, c2 = st.columns(2)
        when = c1.text_input("Date * (YYYY-MM-DD)", value=today.isoformat())
        action = c2.selectbox("Action *", ACTIONS)
        water = c1.text_input("Water amount (ml)", help="Only for 'Watered' entries, 0-5000")
        notes = st.text_area("Notes")
        submitted = st.form_submit_button("Save entry")
    if submitted:
        cleaned, errors = validate_care_form({"date": when, "action": action, "water_ml": water, "notes": notes}, today)
        if errors:
            show_errors(errors)
        else:
            db.add_log(pid, cleaned)
            persist()
            flash(f"Logged {cleaned['action'].lower()} for {plant.name}.")
            st.rerun()
    st.markdown("#### Recent entries")
    table(search.search_logs(db.logs_for(pid)[:10], db.plants), hide=())


def page_search(db: Database, today: date) -> None:
    st.subheader("Search")
    keyword = st.text_input("Keyword", placeholder="e.g. balcony, aloe, fertilized")
    scope = st.radio("Search in", ["Plants", "Care logs"], horizontal=True)
    if scope == "Plants":
        c1, c2 = st.columns(2)
        cats = c1.multiselect("Category", CATEGORIES)
        stats = c2.multiselect("Status", logic.STATUS_ORDER)
        found = search.filter_plants(db.plants, db.logs, keyword, cats, stats, today)
        st.caption(f"{len(found)} plant(s) match")
        table(logic.plant_rows(found, today))
    else:
        acts = st.multiselect("Action", ACTIONS)
        c1, c2 = st.columns(2)
        start = c1.date_input("From", value=today - timedelta(days=90))
        end = c2.date_input("To", value=today)
        rows = search.search_logs(db.logs, db.plants, keyword, acts, start, end)
        st.caption(f"{len(rows)} entr{'y' if len(rows) == 1 else 'ies'} match")
        table(rows, hide=())


def page_summary(db: Database, today: date) -> None:
    st.subheader("Summary & charts")
    s = logic.summary(db.plants, db.logs, today)
    c = st.columns(4)
    c[0].metric("Plants", s["total_plants"])
    c[1].metric("Avg interval", f"{s['avg_interval_days']} d" if s["avg_interval_days"] is not None else "n/a")
    c[2].metric("Waterings (7 d)", s["waterings_last_7"])
    c[3].metric("Waterings (30 d)", s["waterings_last_30"])
    c = st.columns(4)
    c[0].metric("Avg gap between waterings", f"{s['avg_gap_days']} d" if s["avg_gap_days"] is not None else "n/a")
    c[1].metric("Avg water / watering", f"{s['avg_water_ml']} ml" if s["avg_water_ml"] else "n/a")
    c[2].metric("Most cared-for", s["most_cared"][0] if s["most_cared"] else "n/a")
    c[3].metric("Least cared-for", s["least_cared"][0] if s["least_cared"] else "n/a")

    left, right = st.columns(2)
    with left:
        chart_with_download(charts.fig_status(s), "status.png")
        chart_with_download(charts.fig_category(s), "categories.png")
    with right:
        chart_with_download(charts.fig_trend(s), "weekly_trend.png")
        chart_with_download(charts.fig_intervals(s), "intervals.png")


def page_export(db: Database, today: date) -> None:
    st.subheader("Export reports")
    rows = logic.plant_rows(db.plants, today)
    s = logic.summary(db.plants, db.logs, today)
    warnings = logic.anomalies(db.plants, db.logs, today)
    stamp = today.isoformat()
    md = reports.build_markdown(s, rows, warnings, today)

    c1, c2 = st.columns(2)
    c1.download_button("⬇️ Markdown summary (.md)", md, f"plant_care_summary_{stamp}.md", "text/markdown")
    c1.download_button("⬇️ Plain-text audit log (.txt)", reports.build_text_audit(db.plants, db.logs, warnings, today),
                       f"plant_care_audit_{stamp}.txt", "text/plain")
    c2.download_button("⬇️ Plants (.csv)", reports.plants_csv(rows), f"plants_{stamp}.csv", "text/csv")
    c2.download_button("⬇️ Care history (.csv)", reports.logs_csv(db.plants, db.logs), f"care_history_{stamp}.csv", "text/csv")
    with st.expander("Preview the Markdown report"):
        st.markdown(md)


def page_data(db: Database, today: date) -> None:
    st.subheader("Data & import")

    st.markdown("#### Bulk import from CSV")
    st.caption("Required columns: name, category, watering_interval_days, last_watered. "
               "Optional: species, location, notes. Each row is validated on its own.")
    st.download_button("⬇️ CSV template", TEMPLATE, "plant_import_template.csv", "text/csv")
    key = f"upload_{st.session_state.get('up_key', 0)}"
    upload = st.file_uploader("Upload a CSV file", type=["csv"], key=key)
    if upload is not None:
        result = import_plants_csv(upload.getvalue(), db.plant_names(), today)
        if result.fatal:
            st.error(result.fatal)
        else:
            c = st.columns(3)
            c[0].metric("Rows read", result.total_rows)
            c[1].metric("Valid", len(result.cleaned))
            c[2].metric("Rejected", result.total_rows - len(result.cleaned))
            if result.errors:
                st.markdown("**Row-by-row error log**")
                st.dataframe(pd.DataFrame(result.errors), hide_index=True)
                st.download_button("⬇️ Error log (.csv)", errors_to_csv(result.errors), "import_errors.csv", "text/csv")
            if result.cleaned and st.button(f"Import {len(result.cleaned)} valid row(s)"):
                count = db.add_plants_bulk(result.cleaned, today)
                persist()
                st.session_state.up_key = st.session_state.get("up_key", 0) + 1
                flash(f"Imported {count} plant(s)." + (f" {len(result.errors)} problem(s) skipped." if result.errors else ""))
                st.rerun()

    st.divider()
    st.markdown("#### Sample data")
    st.caption("Loads 40 realistic plants with care history, including overdue plants and a few suspicious entries.")
    replace_ok = st.checkbox("Replace all current data with the sample data", key="sample_ok")
    if st.button("Load sample data", disabled=not replace_ok):
        st.session_state.db = build_sample_db(today)
        persist()
        flash("Loaded 40 sample plants.")
        st.rerun()

    st.divider()
    st.markdown("#### Backup & reset")
    st.download_button("⬇️ Download JSON backup", json.dumps(db.to_dict(), indent=2),
                       "plants_backup.json", "application/json")
    reset_ok = st.checkbox("I want to delete ALL plants and care history", key="reset_ok")
    if st.button("Reset everything", disabled=not reset_ok):
        st.session_state.db = Database()
        persist()
        flash("All data cleared.", "warning")
        st.rerun()
    st.caption(f"Data file: `{DATA_PATH}`")


PAGE_FUNCS = {
    "📋 Dashboard": page_dashboard, "🌱 My Plants": page_plants, "➕ Add Plant": page_add_plant,
    "💧 Log Care": page_log_care, "🔎 Search": page_search, "📊 Summary & Charts": page_summary,
    "📤 Export Reports": page_export, "🗂️ Data & Import": page_data,
}


# -------------------------------------------------------------------- main
def main() -> None:
    st.set_page_config(page_title="Plant Care Log", page_icon="🌿", layout="wide")

    if "db" not in st.session_state:
        db, notice = load_db(DATA_PATH)
        st.session_state.db = db
        if notice:
            flash(notice, "warning")

    db: Database = st.session_state.db
    today = date.today()

    with st.sidebar:
        st.title("🌿 Plant Care Log")
        st.caption("Track watering dates and care notes for every plant.")
        page = st.radio("Navigate", PAGES, label_visibility="collapsed", key="page")
        st.divider()
        overdue = sum(1 for p in db.plants if logic.status(p, today) == "Overdue")
        st.caption(f"{len(db.plants)} plants · {overdue} overdue · {today:%d %b %Y}")

    st.title("🌿 Plant Care Log")
    show_flash()
    PAGE_FUNCS[page](db, today)


main()
