# Chronic Stations Tables Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Show two sortable tables naming every chronic drainer and chronic filler station, so the user sees exactly which stations are behind the KPI counts.

**Architecture:** Reuse the `classify_stations(view, threshold=10.0)` result already computed for the KPI row. A new pure helper `chronic_stations(classified, category)` filters/sorts by category (TDD). The app merges station names, formats display columns, and renders two `st.dataframe` tables (built-in sort/search/CSV download).

**Tech Stack:** Python 3.11 (conda env `citibike`), Streamlit 1.58, pandas, pytest. Run all commands via `conda run -n citibike --no-capture-output ...`.

**Important environment note:** Prefix every python/pytest/streamlit command with `conda run -n citibike --no-capture-output`. The Anaconda base Python (3.8) will NOT work.

---

## File Structure

- **Modify `src/metrics.py`** — add pure helper `chronic_stations(classified, category)`.
- **Modify `tests/test_metrics.py`** — add the helper's unit test.
- **Modify `app/streamlit_app.py`** — insert a "Chronic Stations" section (two `st.dataframe` tables) between the supporting charts and the station drill-down. Reuses the existing `classified` and `coords` variables; no other changes.

No new files.

---

### Task 1: `chronic_stations` helper (TDD)

**Files:**
- Modify: `src/metrics.py`
- Modify: `tests/test_metrics.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_metrics.py`:

```python
from src.metrics import chronic_stations


def test_chronic_stations_filters_and_sorts():
    classified = pd.DataFrame(
        {
            "station_id": ["A", "B", "C", "D"],
            "arrivals": [1.0, 5.0, 2.0, 3.0],
            "departures": [20.0, 1.0, 2.5, 30.0],
            "net": [-19.0, 12.0, -0.5, -27.0],
            "category": ["drainer", "filler", "balanced", "drainer"],
        }
    )

    drainers = chronic_stations(classified, "drainer")
    # only drainers, most-negative net first
    assert list(drainers["station_id"]) == ["D", "A"]

    fillers = chronic_stations(classified, "filler")
    # only fillers, most-positive net first
    assert list(fillers["station_id"]) == ["B"]

    # a category with no matching rows -> empty frame
    only_balanced = classified[classified["category"] == "balanced"]
    assert chronic_stations(only_balanced, "drainer").empty
```

- [ ] **Step 2: Run test to verify it fails**

Run: `conda run -n citibike --no-capture-output python -m pytest tests/test_metrics.py::test_chronic_stations_filters_and_sorts -v`
Expected: FAIL with `ImportError: cannot import name 'chronic_stations' from 'src.metrics'`

- [ ] **Step 3: Write minimal implementation**

Append to `src/metrics.py`:

```python
def chronic_stations(classified: pd.DataFrame, category: str) -> pd.DataFrame:
    """Rows of one category, sorted by net flow.

    Drainers are sorted most-negative first; fillers most-positive first.
    Input is the output of `classify_stations` (columns include `net` and
    `category`). Returns the same columns; an empty frame if none match.
    """
    subset = classified[classified["category"] == category]
    ascending = category == "drainer"
    return subset.sort_values("net", ascending=ascending).reset_index(drop=True)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `conda run -n citibike --no-capture-output python -m pytest tests/test_metrics.py::test_chronic_stations_filters_and_sorts -v`
Expected: PASS

- [ ] **Step 5: Run the full suite (no regressions)**

Run: `conda run -n citibike --no-capture-output python -m pytest -q`
Expected: 16 passed (the prior 15 plus this one).

- [ ] **Step 6: Commit**

```bash
git add src/metrics.py tests/test_metrics.py
git commit -m "Add chronic_stations helper to filter and sort by category"
```

---

### Task 2: Render the Chronic Stations tables in the app

**Files:**
- Modify: `app/streamlit_app.py`

This task has no unit test (Streamlit UI); it is verified by running the app and driving it with Playwright.

**Where this goes:** Between the supporting-charts block and the `# --- Station drill-down ---` comment. The `classified` variable (`classify_stations(view, threshold=10.0)`) is already computed earlier for the KPI row, and `coords` (station_id → station_name/lat/lng) is already computed in the drift section — both are in scope here and are reused.

- [ ] **Step 1: Add the import**

In `app/streamlit_app.py`, the existing import block is:

```python
from src.metrics import (
    station_net,
    classify_stations,
    rebalancing_burden,
    cumulative_drift,
    next_hour,
)
```

Change it to add `chronic_stations`:

```python
from src.metrics import (
    station_net,
    classify_stations,
    rebalancing_burden,
    cumulative_drift,
    next_hour,
    chronic_stations,
)
```

- [ ] **Step 2: Insert the Chronic Stations section**

Find this exact text in `app/streamlit_app.py` (end of the top-drainers/fillers chart block, immediately followed by the station drill-down comment):

```python
    .properties(height=260),
    use_container_width=True,
)

# --- Station drill-down ---
```

Replace it with (inserts the new section before the drill-down comment):

```python
    .properties(height=260),
    use_container_width=True,
)

# --- Chronic stations tables ---
st.markdown("## Chronic Stations")
_named = classified.merge(
    coords[["station_id", "station_name"]], on="station_id", how="left"
)
_DISPLAY_COLS = {
    "station_name": "Station",
    "net": "Net (avg/day)",
    "arrivals": "Arrivals (avg/day)",
    "departures": "Departures (avg/day)",
}


def _chronic_table(category):
    table = chronic_stations(_named, category)[list(_DISPLAY_COLS)].rename(
        columns=_DISPLAY_COLS
    )
    return table.round(
        {
            "Net (avg/day)": 1,
            "Arrivals (avg/day)": 1,
            "Departures (avg/day)": 1,
        }
    )


drainers_table = _chronic_table("drainer")
fillers_table = _chronic_table("filler")

dcol, fcol = st.columns(2)
dcol.markdown(f"#### Drainers ({len(drainers_table)})")
if drainers_table.empty:
    dcol.info("No chronic drainers at the current filters.")
else:
    dcol.dataframe(
        drainers_table, hide_index=True, use_container_width=True, height=360
    )
fcol.markdown(f"#### Fillers ({len(fillers_table)})")
if fillers_table.empty:
    fcol.info("No chronic fillers at the current filters.")
else:
    fcol.dataframe(
        fillers_table, hide_index=True, use_container_width=True, height=360
    )

# --- Station drill-down ---
```

- [ ] **Step 3: Launch the app locally**

```bash
cd /Users/reneeritchey/Development/citibike-rebalancing
conda run -n citibike --no-capture-output streamlit run app/streamlit_app.py --server.headless true --server.port 8784 > /tmp/st_chronic.log 2>&1 &
sleep 10
curl -s -o /dev/null -w "health HTTP %{http_code}\n" http://localhost:8784/_stcore/health
```
Expected: `health HTTP 200`, no traceback in `/tmp/st_chronic.log`.

- [ ] **Step 4: Verify with Playwright that table counts match the KPI counts**

Write `/tmp/verify_chronic.py`:

```python
import time, re
from playwright.sync_api import sync_playwright

URL = "http://localhost:8784/"


def app_frame(page):
    for f in page.frames:
        try:
            if f.get_by_text("Chronic Stations", exact=False).count() > 0:
                return f
        except Exception:
            pass
    return page.main_frame


def metric_value(fr, label):
    # st.metric renders the label and value within a [data-testid="stMetric"] block.
    blocks = fr.locator('[data-testid="stMetric"]')
    for i in range(blocks.count()):
        txt = blocks.nth(i).inner_text()
        if label in txt:
            m = re.search(r"(\d[\d,]*)", txt.split(label)[-1])
            if m:
                return int(m.group(1).replace(",", ""))
    return None


def header_count(fr, word):
    for t in fr.locator("h4").all_inner_texts():
        m = re.search(rf"{word} \((\d+)\)", t)
        if m:
            return int(m.group(1))
    return None


with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width": 1600, "height": 1600})
    pg.goto(URL, wait_until="domcontentloaded", timeout=60000)
    fr = None
    for _ in range(40):
        fr = app_frame(pg)
        if fr.get_by_text("Chronic Stations", exact=False).count() > 0:
            break
        time.sleep(1)
    time.sleep(4)

    kpi_drainers = metric_value(fr, "Chronic drainers")
    kpi_fillers = metric_value(fr, "Chronic fillers")
    tbl_drainers = header_count(fr, "Drainers")
    tbl_fillers = header_count(fr, "Fillers")
    n_tables = fr.locator('[data-testid="stDataFrame"]').count()
    pg.screenshot(path="/tmp/chronic.png", full_page=True)
    print({
        "kpi_drainers": kpi_drainers,
        "table_drainers": tbl_drainers,
        "drainers_match": kpi_drainers == tbl_drainers,
        "kpi_fillers": kpi_fillers,
        "table_fillers": tbl_fillers,
        "fillers_match": kpi_fillers == tbl_fillers,
        "dataframe_count": n_tables,
    })
    b.close()
print("DONE")
```

Run: `cd /tmp && conda run -n citibike --no-capture-output python verify_chronic.py`
Expected: `drainers_match: True`, `fillers_match: True`, `dataframe_count: 2`.

- [ ] **Step 5: Inspect the screenshot**

Open `/tmp/chronic.png` and confirm a "Chronic Stations" section with two side-by-side tables (Drainers / Fillers) showing Station / Net (avg/day) / Arrivals (avg/day) / Departures (avg/day) columns.

- [ ] **Step 6: Stop server and clean up**

```bash
pkill -f "streamlit run app/streamlit_app.py"
rm -f /tmp/verify_chronic.py /tmp/st_chronic.log
```

- [ ] **Step 7: Run the full test suite (no regressions)**

Run: `cd /Users/reneeritchey/Development/citibike-rebalancing && conda run -n citibike --no-capture-output python -m pytest -q`
Expected: 16 passed.

- [ ] **Step 8: Commit**

```bash
git add app/streamlit_app.py
git commit -m "Add Chronic Stations tables listing exact drainer/filler stations"
```

---

## Self-Review

**Spec coverage:**
- Two sortable tables (drainers, fillers) listing every qualifying station → Task 2 (`st.dataframe` per category). ✓
- Reuse `classify_stations` so tables match KPI counts → Task 2 reuses the existing `classified`; verification asserts header counts equal KPI counts. ✓
- Respond to day-type/rider filters but not min-trips → `classified` is computed on `view` (filtered by day_type/rider, not min_trips), reused unchanged. ✓
- Columns Station / Net / Arrivals / Departures (avg/day), rounded to 1 decimal → `_DISPLAY_COLS` + `.round(...)` in Task 2. ✓
- Default sort (drainers most-negative, fillers most-positive) → `chronic_stations` in Task 1, unit-tested. ✓
- Built-in sort/search/CSV download, scroll → `st.dataframe(..., height=360)` toolbar in Task 2. ✓
- Empty state messages → `st.info(...)` branches in Task 2. ✓
- Keep the existing top-10 bar chart → untouched (the section is inserted after it). ✓
- TDD helper; existing tests green; Playwright verification → Tasks 1 and 2. ✓
- YAGNI (no adjustable threshold, no map labels, no custom download button) → none added. ✓

**Placeholder scan:** No TBD/TODO. All code blocks complete; the verification script is full and runnable.

**Type consistency:** `chronic_stations(classified, category)` defined in Task 1 and imported/called in Task 2 match. It consumes the `classify_stations` output columns (`station_id`, `arrivals`, `departures`, `net`, `category`) — consistent with the existing function. `_DISPLAY_COLS` keys (`station_name`, `net`, `arrivals`, `departures`) exist after merging `coords` (which supplies `station_name`). The reused variables `classified` and `coords` are confirmed in scope at the insertion point.
