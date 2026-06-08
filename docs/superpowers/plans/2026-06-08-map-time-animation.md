# Map Time Animation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a Play/Pause + loop animation that advances the map's hour-of-day 0→23 so the user watches cumulative Citi Bike imbalance build and shift across the city.

**Architecture:** A server-driven Streamlit rerun loop. Animation state (`playing`, `hour`) lives in `st.session_state`. While playing, the script advances the hour before the slider widget is created, renders the frame, then sleeps and calls `st.rerun()` at the bottom. The map's existing `cumulative_drift()` logic and deck `key` (which excludes the hour) are reused, so the camera stays fixed and only the columns morph. No analysis-pipeline changes.

**Tech Stack:** Python 3.11 (conda env `citibike`), Streamlit 1.58, pydeck, pytest. Run all commands via `conda run -n citibike --no-capture-output ...`.

**Important environment note:** This project uses the conda env `citibike`. Prefix every python/pytest/streamlit command with `conda run -n citibike --no-capture-output`. The Anaconda base Python (3.8) will NOT work.

---

## File Structure

- **Modify `src/metrics.py`** — add one tiny pure helper `next_hour(h)`.
- **Modify `tests/test_metrics.py`** — add the `next_hour` unit test.
- **Modify `app/streamlit_app.py`** — add animation state, the playback row (Play/Pause + readout + scrubber) directly above the map, and the bottom-of-script rerun loop. This reorders the script so the KPI row renders before the playback row, and the hour-dependent `drift` computation moves below the playback row.

No new files. No changes to `src/fetch.py`, `src/transform.py`, `src/build.py`, or `app/layers.py`.

---

### Task 1: `next_hour` helper (TDD)

**Files:**
- Modify: `src/metrics.py`
- Modify: `tests/test_metrics.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_metrics.py`:

```python
from src.metrics import next_hour


def test_next_hour_increments_and_wraps():
    assert next_hour(0) == 1
    assert next_hour(8) == 9
    assert next_hour(22) == 23
    assert next_hour(23) == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `conda run -n citibike --no-capture-output python -m pytest tests/test_metrics.py::test_next_hour_increments_and_wraps -v`
Expected: FAIL with `ImportError: cannot import name 'next_hour' from 'src.metrics'`

- [ ] **Step 3: Write minimal implementation**

Append to `src/metrics.py`:

```python
def next_hour(h: int) -> int:
    """Advance an hour-of-day by one, wrapping 23 -> 0 (for animation looping)."""
    return (h + 1) % 24
```

- [ ] **Step 4: Run test to verify it passes**

Run: `conda run -n citibike --no-capture-output python -m pytest tests/test_metrics.py::test_next_hour_increments_and_wraps -v`
Expected: PASS

- [ ] **Step 5: Run the full suite (no regressions)**

Run: `conda run -n citibike --no-capture-output python -m pytest -q`
Expected: 15 passed (the prior 14 plus this one).

- [ ] **Step 6: Commit**

```bash
git add src/metrics.py tests/test_metrics.py
git commit -m "Add next_hour helper for animation hour advance"
```

---

### Task 2: Wire animation into the Streamlit app

**Files:**
- Modify: `app/streamlit_app.py` (full replacement below)

This task has no unit test (it's Streamlit UI assembly); it is verified by running the app and driving it with Playwright.

- [ ] **Step 1: Replace `app/streamlit_app.py` with this exact content**

```python
import sys
import time
from pathlib import Path

# Streamlit puts the script's own folder (app/) on sys.path, not the repo root,
# so make the repo root importable for the `src` and `app` packages regardless
# of the working directory (local or Streamlit Community Cloud).
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import altair as alt
import pandas as pd
import pydeck as pdk
import streamlit as st

from src.metrics import (
    station_net,
    classify_stations,
    rebalancing_burden,
    cumulative_drift,
    next_hour,
)
from app.layers import (
    net_to_color,
    station_view_state,
    build_column_layer,
    build_highlight_layer,
)

PROCESSED = ROOT / "data" / "processed" / "station_hour.parquet"
ANIM_SPEED = 0.6  # seconds between animation frames

st.set_page_config(page_title="Out of Balance — Citi Bike", layout="wide")


@st.cache_data
def load_netflow() -> pd.DataFrame:
    return pd.read_parquet(PROCESSED)


if not PROCESSED.exists():
    st.error("Processed data not found. Run `python -m src.build 202409` first.")
    st.stop()

netflow = load_netflow()

# --- Animation state ---
st.session_state.setdefault("playing", False)
st.session_state.setdefault("hour", 9)
st.session_state.setdefault("_advance", False)


def _toggle_play():
    st.session_state.playing = not st.session_state.playing
    if not st.session_state.playing:
        st.session_state._advance = False


def _pause_on_scrub():
    # Manually dragging the scrubber pauses playback.
    st.session_state.playing = False
    st.session_state._advance = False


# Advance the hour BEFORE the slider widget is created this run; Streamlit forbids
# mutating a widget-keyed value after instantiation. `_advance` is set at the end
# of the previous frame, so playback steps exactly one hour per rerun.
if st.session_state._advance:
    st.session_state.hour = next_hour(st.session_state.hour)
    st.session_state._advance = False

st.title("Out of Balance: NYC's Citi Bike Rebalancing Problem")
st.caption(
    "Every trip moves one bike. Stations that chronically drain or overflow force "
    "Citi Bike to truck bikes around. This maps that imbalance for September 2024."
)

# --- Sidebar filters ---
st.sidebar.header("Filters")
day_type = st.sidebar.radio("Day type", ["weekday", "weekend"], index=0)
rider = st.sidebar.radio("Rider", ["all", "member", "casual"], index=0)
min_trips = st.sidebar.slider("Minimum trips at station (per day)", 0, 50, 5)

picker_options = ["(none)"] + sorted(netflow["station_name"].dropna().unique().tolist())
selected_name = st.sidebar.selectbox("Zoom to station", picker_options, index=0)

# --- Apply filters ---
view = netflow[netflow["day_type"] == day_type]
if rider != "all":
    view = view[view["member_casual"] == rider]

# --- KPI row (over the full day for the current filters) ---
classified = classify_stations(view, threshold=10.0)
k1, k2, k3, k4 = st.columns(4)
k1.metric("Trips (avg/day)", f"{int(view['departures'].sum()):,}")
k2.metric("Rebalancing burden (bikes/day)", f"{int(rebalancing_burden(view)):,}")
k3.metric("Chronic drainers", int((classified["category"] == "drainer").sum()))
k4.metric("Chronic fillers", int((classified["category"] == "filler").sum()))

# --- Time playback row (directly above the map) ---
st.markdown("#### Time of Day")
pc1, pc2, pc3 = st.columns([1, 2, 6])
pc1.button(
    "⏸ Pause" if st.session_state.playing else "▶ Play",
    use_container_width=True,
    on_click=_toggle_play,
)
pc2.markdown(f"### {st.session_state.hour:02d}:00")
pc3.slider(
    "Cumulative drift through hour",
    min_value=0,
    max_value=23,
    key="hour",
    on_change=_pause_on_scrub,
    label_visibility="collapsed",
)
hour = st.session_state.hour

# --- Cumulative drift through the chosen hour, per station ---
drift = cumulative_drift(view, up_to_hour=hour)
activity = station_net(view)
activity["volume"] = activity["arrivals"] + activity["departures"]
drift = drift.merge(activity[["station_id", "volume"]], on="station_id", how="left")

coords = netflow[["station_id", "station_name", "lat", "lng"]].drop_duplicates(
    "station_id"
)
drift = drift.merge(coords, on="station_id", how="left")
drift = drift[drift["volume"] >= min_trips]

if drift.empty:
    st.session_state.playing = False
    st.warning("No stations match these filters. Try lowering the minimum trips.")
    st.stop()

# --- Map encodings ---
max_abs = float(drift["net"].abs().max()) or 1.0
drift["elevation"] = drift["net"].abs()
drift["color"] = drift["net"].apply(lambda n: net_to_color(n, max_abs))

# --- Map ---
layers = [build_column_layer(drift)]
initial_view = pdk.ViewState(latitude=40.74, longitude=-73.98, zoom=11, pitch=45)

if selected_name != "(none)":
    sel = drift[drift["station_name"] == selected_name]
    if not sel.empty:
        row = sel.iloc[0]
        layers.append(build_highlight_layer(sel))
        initial_view = station_view_state(row["lat"], row["lng"])

st.pydeck_chart(
    pdk.Deck(
        layers=layers,
        initial_view_state=initial_view,
        map_style="dark_no_labels",
        tooltip={
            "html": "<b>{station_name}</b><br/>net: {net}",
            "style": {"color": "white"},
        },
    ),
    # Keying on the selected station forces the deck.gl component to remount when
    # the selection changes, so it re-applies `initial_view_state` and actually
    # flies to the station. Without this, deck.gl keeps its current camera across
    # reruns and the "zoom to station" never moves the map. The key intentionally
    # excludes the hour so the camera stays fixed while the animation plays.
    key=f"deck-{selected_name}",
)

# --- Supporting charts ---
left, right = st.columns(2)

pulse = (
    view.groupby("hour", as_index=False)["net"]
    .sum()
    .rename(columns={"net": "citywide_net"})
)
left.subheader("Citywide Net Flow by Hour (the Tidal Pulse)")
left.altair_chart(
    alt.Chart(pulse)
    .mark_area(opacity=0.6)
    .encode(
        x=alt.X("hour:O", title="Hour of Day", axis=alt.Axis(labelAngle=0)),
        y=alt.Y("citywide_net:Q", title="Net Flow (bikes/day)"),
    )
    .properties(height=260),
    use_container_width=True,
)

top_drain = drift.nsmallest(10, "net")
top_fill = drift.nlargest(10, "net")
right.subheader("Top Drainers (Red) and Fillers (Blue)")
right.altair_chart(
    alt.Chart(pd.concat([top_drain, top_fill]))
    .mark_bar()
    .encode(
        x=alt.X("net:Q", title="Net Flow (bikes/day)"),
        y=alt.Y("station_name:N", sort="-x", title="Station"),
        color=alt.condition("datum.net < 0", alt.value("#d6604d"), alt.value("#4393c3")),
    )
    .properties(height=260),
    use_container_width=True,
)

# --- Station drill-down ---
if selected_name != "(none)":
    st.subheader(f"Station Detail: {selected_name}")
    sel_id = coords[coords["station_name"] == selected_name]["station_id"].iloc[0]
    sel_rows = view[view["station_id"] == sel_id]
    s_net = station_net(sel_rows)["net"].iloc[0] if not sel_rows.empty else 0.0
    category = "drainer" if s_net <= -10 else "filler" if s_net >= 10 else "balanced"
    c1, c2, c3 = st.columns(3)
    c1.metric("Net (avg/day)", f"{s_net:.1f}")
    c2.metric("Category", category)
    c3.metric(
        "Trips (avg/day)",
        f"{int(sel_rows['departures'].sum() + sel_rows['arrivals'].sum())}",
    )
    hourly = sel_rows.groupby("hour", as_index=False)["net"].sum()
    st.altair_chart(
        alt.Chart(hourly).mark_bar().encode(
            x=alt.X("hour:O", title="Hour of Day", axis=alt.Axis(labelAngle=0)),
            y=alt.Y("net:Q", title="Net Flow (bikes/day)"),
            color=alt.condition("datum.net < 0", alt.value("#d6604d"), alt.value("#4393c3")),
        ).properties(height=240),
        use_container_width=True,
    )

with st.expander("How this works / methodology"):
    st.markdown(
        "- **Net flow** = arrivals − departures, per station. Negative = drains empty; "
        "positive = overflows.\n"
        "- Counts are normalized to **average per day** of the selected day type, so "
        "weekday and weekend are comparable.\n"
        "- **Cumulative drift through hour H** sums each station's net flow for hours 0–H.\n"
        "- **Rebalancing burden** = sum of positive per-station net flow = the minimum "
        "bikes that must be moved to reset the system each day.\n"
        "- Press ▶ Play to animate the map through the day; drag the hour scrubber to "
        "pause and inspect any hour.\n"
        "- Data: Citi Bike public trip data, September 2024."
    )

# --- Drive the animation: schedule the next frame ---
if st.session_state.playing:
    st.session_state._advance = True
    time.sleep(ANIM_SPEED)
    st.rerun()
```

- [ ] **Step 2: Launch the app locally**

```bash
cd /Users/reneeritchey/Development/citibike-rebalancing
conda run -n citibike --no-capture-output streamlit run app/streamlit_app.py --server.headless true --server.port 8780 > /tmp/st_anim.log 2>&1 &
sleep 10
curl -s -o /dev/null -w "health HTTP %{http_code}\n" http://localhost:8780/_stcore/health
```
Expected: `health HTTP 200`, and no traceback in `/tmp/st_anim.log`.

- [ ] **Step 3: Drive it with Playwright to verify Play advances the hour and the map changes**

Write `/tmp/verify_anim.py`:

```python
import time, os, re
from PIL import Image, ImageChops
import numpy as np
from playwright.sync_api import sync_playwright

URL = "http://localhost:8780/"
OUT = "/tmp/anim_shots"
os.makedirs(OUT, exist_ok=True)


def app_frame(page):
    for f in page.frames:
        try:
            if f.get_by_text("Time of Day", exact=False).count() > 0:
                return f
        except Exception:
            pass
    return page.main_frame


def read_hour(fr):
    # The readout is an h3 rendered from "### HH:00".
    for t in fr.locator("h3").all_inner_texts():
        m = re.search(r"\b(\d{2}):00\b", t)
        if m:
            return int(m.group(1))
    return None


with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width": 1600, "height": 1300})
    pg.goto(URL, wait_until="domcontentloaded", timeout=60000)
    fr = None
    for _ in range(40):
        fr = app_frame(pg)
        if fr.get_by_role("button", name=re.compile("Play|Pause")).count() > 0:
            break
        time.sleep(1)
    time.sleep(3)

    pg.screenshot(path=f"{OUT}/before.png", full_page=True)
    h0 = read_hour(fr)

    # Click Play and let it animate a few frames.
    fr.get_by_role("button", name=re.compile("Play")).first.click()
    time.sleep(4)
    h1 = read_hour(fr)
    pg.screenshot(path=f"{OUT}/playing.png", full_page=True)

    # Click Pause and confirm the hour stops advancing.
    fr.get_by_role("button", name=re.compile("Pause")).first.click()
    time.sleep(1)
    h2 = read_hour(fr)
    time.sleep(3)
    h3 = read_hour(fr)

    a = Image.open(f"{OUT}/before.png").convert("RGB")
    c = Image.open(f"{OUT}/playing.png").convert("RGB")
    w, h = a.size
    box = (int(w*0.18), int(h*0.20), int(w*0.99), int(h*0.45))
    diff = np.asarray(ImageChops.difference(a.crop(box), c.crop(box)))
    print({
        "hour_before_play": h0,
        "hour_while_playing": h1,
        "advanced": h1 is not None and h0 is not None and h1 != h0,
        "hour_at_pause": h2,
        "hour_after_pause_wait": h3,
        "stayed_paused": h2 == h3,
        "map_mean_diff": round(float(diff.mean()), 2),
        "map_changed": bool(diff.mean() > 1.0),
    })
    b.close()
print("DONE")
```

Run: `cd /tmp && conda run -n citibike --no-capture-output python verify_anim.py`
Expected output: `advanced: True`, `map_changed: True`, `stayed_paused: True`.

- [ ] **Step 4: Inspect the screenshots**

Open `/tmp/anim_shots/playing.png` and confirm the playback row shows `▶ Play`/`⏸ Pause`, a `HH:00` readout, and the hour scrubber directly above the 3D map, with the map columns reflecting the advanced hour.

- [ ] **Step 5: Stop the server and clean up**

```bash
pkill -f "streamlit run app/streamlit_app.py"
rm -f /tmp/verify_anim.py /tmp/st_anim.log
```

- [ ] **Step 6: Run the full test suite (no regressions)**

Run: `cd /Users/reneeritchey/Development/citibike-rebalancing && conda run -n citibike --no-capture-output python -m pytest -q`
Expected: 15 passed.

- [ ] **Step 7: Commit**

```bash
git add app/streamlit_app.py
git commit -m "Add Play/Pause time animation to the map"
```

---

## Self-Review

**Spec coverage:**
- Cumulative-imbalance frames → reuses `cumulative_drift(view, up_to_hour=hour)` (Task 2). ✓
- Full-day Play/Pause + loop → `next_hour` wraps 23→0 (Task 1) + bottom-of-script rerun loop (Task 2). ✓
- Playback row above the map with Play/Pause, `HH:00` readout, scrubber → Task 2 (`st.columns([1, 2, 6])` placed after KPIs, before the map). ✓
- Hour control moved out of the sidebar → removed from sidebar; now in the playback row (Task 2). ✓
- `{playing, hour}` session-state model, no-mutation-after-widget via advance-at-top → Task 2 (`_advance` flag, keyed slider). ✓
- Scrub pauses playback → `on_change=_pause_on_scrub` (Task 2). ✓
- Camera fixed during playback → deck `key=f"deck-{selected_name}"` excludes the hour (Task 2). ✓
- Empty-data pauses cleanly → `st.session_state.playing = False` before `st.warning`/`st.stop` (Task 2). ✓
- `next_hour` TDD; existing 14 tests stay green; Playwright verification → Tasks 1 and 2. ✓
- YAGNI (no speed control, range, per-hour mode, export) → none added. ✓

**Placeholder scan:** No TBD/TODO. All code blocks are complete and runnable. The verification script is full, not sketched.

**Type consistency:** `next_hour(h: int) -> int` defined in Task 1 and imported/called in Task 2 match. Session-state keys (`playing`, `hour`, `_advance`) are used consistently. The slider's `key="hour"` matches the `st.session_state.hour` reads. The deck `key` string is unchanged from the existing app. Column names (`net`, `station_id`, `station_name`, `lat`, `lng`, `volume`) match the existing pipeline.

**Note on Pause responsiveness:** the `on_click=_toggle_play` callback runs before the script body, and it clears `_advance`, so Pause stops immediately at the current hour with no extra frame. Verified by Step 3's `stayed_paused` check.
