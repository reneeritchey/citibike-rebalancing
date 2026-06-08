# Citi Bike Rebalancing ("Out of Balance") Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an interactive Streamlit + pydeck app that maps which Citi Bike stations chronically drain or overflow in a representative month and quantifies the daily bike-rebalancing burden.

**Architecture:** Pure Python analysis functions (cleaning → per-day net-flow aggregation → classification/metrics) are developed test-first and run once offline to produce a small `station_hour.parquet`. A Streamlit app reads that parquet and renders a 3D pydeck `ColumnLayer` map driven by an hour slider and sidebar filters, plus a searchable station picker that flies the map to a station and shows a drill-down panel.

**Tech Stack:** Python 3.11+, pandas, pyarrow, requests, Streamlit, pydeck (deck.gl), Altair, pytest.

**Domain primer for the implementer (you likely don't know this):**
- Citi Bike publishes one ZIP of trip CSVs per month at `https://s3.amazonaws.com/tripdata/`. Each trip row has a start and an end station, each with an id, name, lat, lng, plus `started_at`/`ended_at` timestamps and `member_casual`.
- **Net flow** of a station = arrivals − departures. A departure happens at the *start* station (someone took a bike); an arrival happens at the *end* station (someone returned one). A station with persistent negative net flow empties out; positive overflows. The bikes that must be trucked back each day to reset the system is the **rebalancing burden**.
- Because a month has more weekdays than weekend days, raw counts across day types aren't comparable. We normalize to **average per day of each type** before analyzing.

---

## File Structure

```
citibike-rebalancing/
├── data/{raw,processed}/        # gitignored (already present from spec commit)
├── src/
│   ├── __init__.py
│   ├── fetch.py        # build_url(), load_month() — download + cache one month
│   ├── transform.py    # clean_trips(), station_coords(), station_hour_totals(),
│   │                   #   day_counts(), normalize_per_day()
│   ├── metrics.py      # station_net(), classify_stations(), rebalancing_burden(),
│   │                   #   cumulative_drift()
│   └── build.py        # orchestration: produces data/processed/station_hour.parquet
├── app/
│   ├── __init__.py
│   ├── layers.py       # net_to_color(), station_view_state(),
│   │                   #   build_column_layer(), build_highlight_layer()
│   └── streamlit_app.py
├── tests/
│   ├── __init__.py
│   ├── conftest.py     # sample_trips fixture
│   ├── test_transform.py
│   ├── test_metrics.py
│   └── test_layers.py
├── requirements.txt
└── README.md
```

Each `src` module has one responsibility and is imported by `build.py` (offline) and/or the app. The app never does heavy computation — it reads the precomputed parquet and filters it.

---

### Task 1: Project scaffolding

**Files:**
- Create: `requirements.txt`
- Create: `src/__init__.py`, `app/__init__.py`, `tests/__init__.py`
- Create: `pytest.ini`
- Create: `tests/conftest.py`

- [ ] **Step 1: Create `requirements.txt`**

```text
pandas>=2.0
pyarrow>=14.0
requests>=2.31
streamlit>=1.31
pydeck>=0.8
altair>=5.0
pytest>=8.0
```

- [ ] **Step 2: Create empty package markers**

Create three empty files: `src/__init__.py`, `app/__init__.py`, `tests/__init__.py` (each with no content).

- [ ] **Step 3: Create `pytest.ini`**

```ini
[pytest]
testpaths = tests
python_files = test_*.py
```

- [ ] **Step 4: Create `tests/conftest.py` with the shared sample fixture**

`2024-09-02` is a Monday (weekday); `2024-09-07` is a Saturday (weekend). These three trips give known, hand-checkable net flows used throughout the tests.

```python
import pandas as pd
import pytest


@pytest.fixture
def sample_trips():
    """Three trips with hand-verifiable net flows.

    Trip 1: A->B, 2024-09-02 08:00 (Mon/weekday), member
    Trip 2: A->B, 2024-09-02 08:30 (Mon/weekday), member
    Trip 3: B->A, 2024-09-07 10:00 (Sat/weekend), casual
    """
    return pd.DataFrame(
        {
            "started_at": [
                "2024-09-02 08:00:00",
                "2024-09-02 08:30:00",
                "2024-09-07 10:00:00",
            ],
            "ended_at": [
                "2024-09-02 08:10:00",
                "2024-09-02 08:45:00",
                "2024-09-07 10:20:00",
            ],
            "start_station_id": ["A", "A", "B"],
            "start_station_name": ["Alpha", "Alpha", "Beta"],
            "start_lat": [40.70, 40.70, 40.80],
            "start_lng": [-74.00, -74.00, -73.90],
            "end_station_id": ["B", "B", "A"],
            "end_station_name": ["Beta", "Beta", "Alpha"],
            "end_lat": [40.80, 40.80, 40.70],
            "end_lng": [-73.90, -73.90, -74.00],
            "member_casual": ["member", "member", "casual"],
        }
    )
```

- [ ] **Step 5: Install dependencies and verify pytest collects nothing yet**

Run: `pip install -r requirements.txt && pytest -q`
Expected: `no tests ran` (exit code 5) — confirms pytest is installed and configured.

- [ ] **Step 6: Commit**

```bash
git add requirements.txt pytest.ini src/__init__.py app/__init__.py tests/__init__.py tests/conftest.py
git commit -m "Scaffold project structure and test fixture"
```

---

### Task 2: `clean_trips` — drop bad rows, parse timestamps

**Files:**
- Create: `src/transform.py`
- Create: `tests/test_transform.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_transform.py
import numpy as np
import pandas as pd

from src.transform import clean_trips


def test_clean_trips_drops_null_coords_and_parses_timestamps(sample_trips):
    dirty = sample_trips.copy()
    # Add a row with a missing end coordinate — must be dropped.
    bad = sample_trips.iloc[[0]].copy()
    bad["end_lat"] = np.nan
    dirty = pd.concat([dirty, bad], ignore_index=True)

    result = clean_trips(dirty)

    assert len(result) == 3  # the bad row is gone
    assert pd.api.types.is_datetime64_any_dtype(result["started_at"])
    assert pd.api.types.is_datetime64_any_dtype(result["ended_at"])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_transform.py::test_clean_trips_drops_null_coords_and_parses_timestamps -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.transform'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/transform.py
import pandas as pd

_COORD_COLS = [
    "start_station_id",
    "start_station_name",
    "start_lat",
    "start_lng",
    "end_station_id",
    "end_station_name",
    "end_lat",
    "end_lng",
]


def clean_trips(df: pd.DataFrame) -> pd.DataFrame:
    """Drop rows missing stations/coords and parse timestamp columns."""
    df = df.dropna(subset=_COORD_COLS).copy()
    df["started_at"] = pd.to_datetime(df["started_at"], errors="coerce")
    df["ended_at"] = pd.to_datetime(df["ended_at"], errors="coerce")
    df = df.dropna(subset=["started_at", "ended_at"])
    return df.reset_index(drop=True)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_transform.py::test_clean_trips_drops_null_coords_and_parses_timestamps -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/transform.py tests/test_transform.py
git commit -m "Add clean_trips: drop invalid rows and parse timestamps"
```

---

### Task 3: `station_coords` — median lat/lng per station

**Files:**
- Modify: `src/transform.py`
- Modify: `tests/test_transform.py`

- [ ] **Step 1: Write the failing test**

```python
# append to tests/test_transform.py
from src.transform import station_coords


def test_station_coords_returns_one_row_per_station(sample_trips):
    clean = clean_trips(sample_trips)

    coords = station_coords(clean)

    assert set(coords["station_id"]) == {"A", "B"}
    assert list(coords.columns) == ["station_id", "station_name", "lat", "lng"]
    a = coords.set_index("station_id").loc["A"]
    assert a["station_name"] == "Alpha"
    assert a["lat"] == 40.70
    assert a["lng"] == -74.00
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_transform.py::test_station_coords_returns_one_row_per_station -v`
Expected: FAIL with `ImportError: cannot import name 'station_coords'`

- [ ] **Step 3: Write minimal implementation**

```python
# append to src/transform.py


def station_coords(df: pd.DataFrame) -> pd.DataFrame:
    """Median lat/lng per station id, combining start and end appearances."""
    starts = df[
        ["start_station_id", "start_station_name", "start_lat", "start_lng"]
    ].rename(
        columns={
            "start_station_id": "station_id",
            "start_station_name": "station_name",
            "start_lat": "lat",
            "start_lng": "lng",
        }
    )
    ends = df[
        ["end_station_id", "end_station_name", "end_lat", "end_lng"]
    ].rename(
        columns={
            "end_station_id": "station_id",
            "end_station_name": "station_name",
            "end_lat": "lat",
            "end_lng": "lng",
        }
    )
    both = pd.concat([starts, ends], ignore_index=True)
    coords = both.groupby("station_id", as_index=False).agg(
        station_name=("station_name", "first"),
        lat=("lat", "median"),
        lng=("lng", "median"),
    )
    return coords
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_transform.py::test_station_coords_returns_one_row_per_station -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/transform.py tests/test_transform.py
git commit -m "Add station_coords: median coordinates per station"
```

---

### Task 4: `station_hour_totals` — arrivals/departures/net per (station, hour, day_type, member_casual)

**Files:**
- Modify: `src/transform.py`
- Modify: `tests/test_transform.py`

- [ ] **Step 1: Write the failing test**

Expected totals from the fixture (verified by hand):
- `A, 8, weekday, member`: arrivals 0, departures 2, net −2
- `B, 8, weekday, member`: arrivals 2, departures 0, net +2
- `B, 10, weekend, casual`: arrivals 0, departures 1, net −1
- `A, 10, weekend, casual`: arrivals 1, departures 0, net +1

```python
# append to tests/test_transform.py
from src.transform import station_hour_totals


def test_station_hour_totals_computes_net_flow(sample_trips):
    clean = clean_trips(sample_trips)

    totals = station_hour_totals(clean)
    keyed = totals.set_index(
        ["station_id", "hour", "day_type", "member_casual"]
    )

    assert keyed.loc[("A", 8, "weekday", "member"), "departures"] == 2
    assert keyed.loc[("A", 8, "weekday", "member"), "arrivals"] == 0
    assert keyed.loc[("A", 8, "weekday", "member"), "net"] == -2
    assert keyed.loc[("B", 8, "weekday", "member"), "net"] == 2
    assert keyed.loc[("B", 10, "weekend", "casual"), "net"] == -1
    assert keyed.loc[("A", 10, "weekend", "casual"), "net"] == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_transform.py::test_station_hour_totals_computes_net_flow -v`
Expected: FAIL with `ImportError: cannot import name 'station_hour_totals'`

- [ ] **Step 3: Write minimal implementation**

```python
# append to src/transform.py


def _day_type(ts: pd.Series) -> pd.Series:
    return ts.dt.dayofweek.map(lambda d: "weekend" if d >= 5 else "weekday")


def station_hour_totals(df: pd.DataFrame) -> pd.DataFrame:
    """Total arrivals/departures/net per station, hour-of-day, day_type, rider type.

    Departures are bucketed at the start station by `started_at` hour;
    arrivals at the end station by `ended_at` hour.
    """
    departures = pd.DataFrame(
        {
            "station_id": df["start_station_id"].values,
            "hour": df["started_at"].dt.hour.values,
            "day_type": _day_type(df["started_at"]).values,
            "member_casual": df["member_casual"].values,
            "arrivals": 0,
            "departures": 1,
        }
    )
    arrivals = pd.DataFrame(
        {
            "station_id": df["end_station_id"].values,
            "hour": df["ended_at"].dt.hour.values,
            "day_type": _day_type(df["ended_at"]).values,
            "member_casual": df["member_casual"].values,
            "arrivals": 1,
            "departures": 0,
        }
    )
    events = pd.concat([departures, arrivals], ignore_index=True)
    totals = events.groupby(
        ["station_id", "hour", "day_type", "member_casual"], as_index=False
    ).agg(arrivals=("arrivals", "sum"), departures=("departures", "sum"))
    totals["net"] = totals["arrivals"] - totals["departures"]
    return totals
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_transform.py::test_station_hour_totals_computes_net_flow -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/transform.py tests/test_transform.py
git commit -m "Add station_hour_totals: net flow by station/hour/day_type/rider"
```

---

### Task 5: `day_counts` — distinct dates per day type

**Files:**
- Modify: `src/transform.py`
- Modify: `tests/test_transform.py`

- [ ] **Step 1: Write the failing test**

```python
# append to tests/test_transform.py
from src.transform import day_counts


def test_day_counts_counts_distinct_dates(sample_trips):
    clean = clean_trips(sample_trips)

    counts = day_counts(clean)

    assert counts == {"weekday": 1, "weekend": 1}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_transform.py::test_day_counts_counts_distinct_dates -v`
Expected: FAIL with `ImportError: cannot import name 'day_counts'`

- [ ] **Step 3: Write minimal implementation**

```python
# append to src/transform.py


def day_counts(df: pd.DataFrame) -> dict:
    """Number of distinct calendar dates of each day type, keyed by started_at."""
    dates = pd.DataFrame(
        {
            "date": df["started_at"].dt.date,
            "day_type": _day_type(df["started_at"]).values,
        }
    ).drop_duplicates()
    counts = dates.groupby("day_type")["date"].nunique().to_dict()
    counts.setdefault("weekday", 0)
    counts.setdefault("weekend", 0)
    return {"weekday": counts["weekday"], "weekend": counts["weekend"]}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_transform.py::test_day_counts_counts_distinct_dates -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/transform.py tests/test_transform.py
git commit -m "Add day_counts: distinct dates per day type"
```

---

### Task 6: `normalize_per_day` — convert totals to average-per-day

**Files:**
- Modify: `src/transform.py`
- Modify: `tests/test_transform.py`

- [ ] **Step 1: Write the failing test**

This test passes a tiny totals table and an explicit `day_counts` dict so the division is unambiguous (4 weekday departures over 2 weekdays → 2.0 per day).

```python
# append to tests/test_transform.py
from src.transform import normalize_per_day


def test_normalize_per_day_divides_by_day_type_count():
    totals = pd.DataFrame(
        {
            "station_id": ["A", "A"],
            "hour": [8, 8],
            "day_type": ["weekday", "weekend"],
            "member_casual": ["member", "member"],
            "arrivals": [0, 0],
            "departures": [4, 2],
            "net": [-4, -2],
        }
    )

    result = normalize_per_day(totals, {"weekday": 2, "weekend": 1})
    keyed = result.set_index(["station_id", "day_type"])

    # 4 departures over 2 weekdays -> 2.0 per day; net -2.0
    assert keyed.loc[("A", "weekday"), "departures"] == 2.0
    assert keyed.loc[("A", "weekday"), "net"] == -2.0
    # 2 departures over 1 weekend day -> 2.0 per day; unchanged
    assert keyed.loc[("A", "weekend"), "departures"] == 2.0
    assert keyed.loc[("A", "weekend"), "net"] == -2.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_transform.py::test_normalize_per_day_divides_by_day_type_count -v`
Expected: FAIL with `ImportError: cannot import name 'normalize_per_day'`

- [ ] **Step 3: Write minimal implementation**

```python
# append to src/transform.py


def normalize_per_day(totals: pd.DataFrame, counts: dict) -> pd.DataFrame:
    """Divide arrivals/departures/net by the number of days of each day type.

    Produces average-per-day values so weekday and weekend rows are comparable.
    """
    result = totals.copy()
    divisor = result["day_type"].map(counts).astype(float)
    for col in ["arrivals", "departures", "net"]:
        result[col] = result[col] / divisor
    return result
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_transform.py::test_normalize_per_day_divides_by_day_type_count -v`
Expected: PASS

- [ ] **Step 5: Run the full transform suite**

Run: `pytest tests/test_transform.py -v`
Expected: all 5 transform tests PASS

- [ ] **Step 6: Commit**

```bash
git add src/transform.py tests/test_transform.py
git commit -m "Add normalize_per_day: average-per-day net flow"
```

---

### Task 7: `station_net` and `classify_stations`

**Files:**
- Create: `src/metrics.py`
- Create: `tests/test_metrics.py`

Net per station over the full fixture (per-day values with both day counts = 1, so equal to totals): A = −2 + 1 = −1; B = +2 − 1 = +1.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_metrics.py
import pandas as pd

from src.transform import (
    clean_trips,
    station_hour_totals,
    day_counts,
    normalize_per_day,
)
from src.metrics import station_net, classify_stations


def _netflow(sample_trips):
    clean = clean_trips(sample_trips)
    totals = station_hour_totals(clean)
    return normalize_per_day(totals, day_counts(clean))


def test_station_net_sums_net_per_station(sample_trips):
    netflow = _netflow(sample_trips)

    net = station_net(netflow).set_index("station_id")["net"]

    assert net.loc["A"] == -1.0
    assert net.loc["B"] == 1.0


def test_classify_stations_labels_drainer_and_filler(sample_trips):
    netflow = _netflow(sample_trips)

    classified = classify_stations(netflow, threshold=1.0).set_index("station_id")

    assert classified.loc["A", "category"] == "drainer"
    assert classified.loc["B", "category"] == "filler"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_metrics.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.metrics'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/metrics.py
import pandas as pd


def station_net(netflow: pd.DataFrame) -> pd.DataFrame:
    """Sum arrivals/departures/net per station over the given (filtered) slice."""
    return netflow.groupby("station_id", as_index=False).agg(
        arrivals=("arrivals", "sum"),
        departures=("departures", "sum"),
        net=("net", "sum"),
    )


def classify_stations(netflow: pd.DataFrame, threshold: float = 10.0) -> pd.DataFrame:
    """Label each station drainer / filler / balanced by total net vs threshold."""
    totals = station_net(netflow)

    def label(n: float) -> str:
        if n <= -threshold:
            return "drainer"
        if n >= threshold:
            return "filler"
        return "balanced"

    totals["category"] = totals["net"].map(label)
    return totals
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_metrics.py -v`
Expected: both tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/metrics.py tests/test_metrics.py
git commit -m "Add station_net and classify_stations"
```

---

### Task 8: `rebalancing_burden` and `cumulative_drift`

**Files:**
- Modify: `src/metrics.py`
- Modify: `tests/test_metrics.py`

Burden = sum of positive station net = B's +1.0 = 1.0. Cumulative drift up to hour 8 (weekday member slice) → A −2, B +2.

- [ ] **Step 1: Write the failing test**

```python
# append to tests/test_metrics.py
from src.metrics import rebalancing_burden, cumulative_drift


def test_rebalancing_burden_sums_positive_net(sample_trips):
    netflow = _netflow(sample_trips)

    assert rebalancing_burden(netflow) == 1.0


def test_cumulative_drift_accumulates_through_hour(sample_trips):
    netflow = _netflow(sample_trips)

    drift = cumulative_drift(netflow, up_to_hour=8).set_index("station_id")["net"]

    assert drift.loc["A"] == -2.0
    assert drift.loc["B"] == 2.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_metrics.py::test_rebalancing_burden_sums_positive_net -v`
Expected: FAIL with `ImportError: cannot import name 'rebalancing_burden'`

- [ ] **Step 3: Write minimal implementation**

```python
# append to src/metrics.py


def rebalancing_burden(netflow: pd.DataFrame) -> float:
    """Minimum bikes to move to reset: sum of positive per-station net flow."""
    net = station_net(netflow)["net"]
    return float(net[net > 0].sum())


def cumulative_drift(netflow: pd.DataFrame, up_to_hour: int) -> pd.DataFrame:
    """Per-station net accumulated for all hours <= up_to_hour."""
    sliced = netflow[netflow["hour"] <= up_to_hour]
    return station_net(sliced)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_metrics.py -v`
Expected: all 4 metrics tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/metrics.py tests/test_metrics.py
git commit -m "Add rebalancing_burden and cumulative_drift"
```

---

### Task 9: `fetch.py` — build URL and load/cache a month

**Files:**
- Create: `src/fetch.py`
- Create: `tests/test_fetch.py`

We TDD the pure `build_url` and the cache-hit branch of `load_month` (no network). The download branch is exercised manually in Task 10.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_fetch.py
import pandas as pd

from src.fetch import build_url, load_month


def test_build_url_formats_month():
    assert (
        build_url("202409")
        == "https://s3.amazonaws.com/tripdata/202409-citibike-tripdata.zip"
    )


def test_load_month_reads_cached_parquet(tmp_path):
    raw_dir = tmp_path
    cached = pd.DataFrame({"start_station_id": ["A"], "member_casual": ["member"]})
    cached.to_parquet(raw_dir / "202409.parquet")

    result = load_month("202409", raw_dir=raw_dir)

    assert list(result["start_station_id"]) == ["A"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_fetch.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.fetch'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/fetch.py
import io
import zipfile
from pathlib import Path

import pandas as pd
import requests

BASE_URL = "https://s3.amazonaws.com/tripdata"


def build_url(yyyymm: str) -> str:
    """URL of the monthly Citi Bike trip ZIP, e.g. '202409'."""
    return f"{BASE_URL}/{yyyymm}-citibike-tripdata.zip"


def load_month(yyyymm: str, raw_dir: Path) -> pd.DataFrame:
    """Return all trips for a month as a DataFrame, caching a parquet in raw_dir.

    On cache miss, downloads the ZIP, concatenates every CSV inside it
    (months are sometimes split into multiple CSVs), caches, and returns.
    """
    raw_dir = Path(raw_dir)
    raw_dir.mkdir(parents=True, exist_ok=True)
    cache = raw_dir / f"{yyyymm}.parquet"
    if cache.exists():
        return pd.read_parquet(cache)

    resp = requests.get(build_url(yyyymm), timeout=120)
    resp.raise_for_status()
    if len(resp.content) < 1000:
        raise ValueError(f"Downloaded file for {yyyymm} is suspiciously small")

    frames = []
    with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
        csv_names = [
            n
            for n in zf.namelist()
            if n.endswith(".csv") and not n.startswith("__MACOSX")
        ]
        for name in csv_names:
            with zf.open(name) as fh:
                frames.append(pd.read_csv(fh, low_memory=False))

    df = pd.concat(frames, ignore_index=True)
    df.to_parquet(cache)
    return df
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_fetch.py -v`
Expected: both tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/fetch.py tests/test_fetch.py
git commit -m "Add fetch: build_url and cached load_month"
```

---

### Task 10: `build.py` — produce `data/processed/station_hour.parquet`

**Files:**
- Create: `src/build.py`

This is an offline orchestration script (no unit test — it wires tested functions and does I/O). It is verified by running it once and inspecting output.

- [ ] **Step 1: Write the build script**

```python
# src/build.py
"""Offline pipeline: download a month and write the app's processed parquet.

Usage: python -m src.build [YYYYMM]   (default 202409)
"""
import sys
from pathlib import Path

from src.fetch import load_month
from src.transform import (
    clean_trips,
    station_coords,
    station_hour_totals,
    day_counts,
    normalize_per_day,
)

RAW_DIR = Path("data/raw")
PROCESSED_DIR = Path("data/processed")


def build(yyyymm: str = "202409") -> None:
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    raw = load_month(yyyymm, raw_dir=RAW_DIR)
    print(f"Loaded {len(raw):,} raw trips for {yyyymm}")

    clean = clean_trips(raw)
    print(f"Kept {len(clean):,} trips after cleaning ({len(raw) - len(clean):,} dropped)")

    totals = station_hour_totals(clean)
    netflow = normalize_per_day(totals, day_counts(clean))
    coords = station_coords(clean)

    netflow = netflow.merge(coords, on="station_id", how="left")
    out = PROCESSED_DIR / "station_hour.parquet"
    netflow.to_parquet(out)
    coords.to_parquet(PROCESSED_DIR / "stations.parquet")
    print(f"Wrote {out} with {len(netflow):,} rows across {coords.shape[0]:,} stations")


if __name__ == "__main__":
    build(sys.argv[1] if len(sys.argv) > 1 else "202409")
```

- [ ] **Step 2: Run the build (downloads ~real data; needs free disk)**

> **Disk note:** this downloads/extracts a few hundred MB. Ensure `data/` lives on a filesystem with room and that `CLAUDE_CODE_TMPDIR`/the temp filesystem is not full before running.

Run: `python -m src.build 202409`
Expected: prints "Loaded N raw trips", "Kept M trips", and "Wrote data/processed/station_hour.parquet ...". Files `data/processed/station_hour.parquet` and `stations.parquet` exist.

- [ ] **Step 3: Sanity-check the output**

Run: `python -c "import pandas as pd; df=pd.read_parquet('data/processed/station_hour.parquet'); print(df.columns.tolist()); print(df.head()); print('stations:', df.station_id.nunique())"`
Expected: columns include `station_id, hour, day_type, member_casual, arrivals, departures, net, station_name, lat, lng`; thousands of stations.

- [ ] **Step 4: Commit (code only — data/ is gitignored)**

```bash
git add src/build.py
git commit -m "Add build pipeline producing processed station_hour parquet"
```

---

### Task 11: `app/layers.py` — pydeck helpers

**Files:**
- Create: `app/layers.py`
- Create: `tests/test_layers.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_layers.py
from app.layers import net_to_color, station_view_state


def test_net_to_color_endpoints_and_midpoint():
    assert net_to_color(0, 10) == [200, 200, 200, 200]
    assert net_to_color(10, 10) == [0, 0, 255, 200]      # max positive -> blue
    assert net_to_color(-10, 10) == [255, 0, 0, 200]     # max negative -> red


def test_net_to_color_handles_zero_max():
    assert net_to_color(5, 0) == [200, 200, 200, 180]


def test_station_view_state_centers_on_station():
    vs = station_view_state(40.75, -73.99)
    assert vs.latitude == 40.75
    assert vs.longitude == -73.99
    assert vs.zoom == 15
    assert vs.pitch == 45
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_layers.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.layers'`

- [ ] **Step 3: Write minimal implementation**

```python
# app/layers.py
import pydeck as pdk


def net_to_color(net: float, max_abs: float) -> list:
    """Diverging color: red (drains) -> pale grey (balanced) -> blue (overflows)."""
    if max_abs <= 0:
        return [200, 200, 200, 180]
    t = max(-1.0, min(1.0, net / max_abs))
    if t >= 0:
        return [int(200 * (1 - t)), int(200 * (1 - t)), int(200 + 55 * t), 200]
    t = -t
    return [int(200 + 55 * t), int(200 * (1 - t)), int(200 * (1 - t)), 200]


def station_view_state(lat: float, lng: float) -> pdk.ViewState:
    """Camera focused on a single station (zoomed, tilted for the 3D columns)."""
    return pdk.ViewState(
        latitude=lat, longitude=lng, zoom=15, pitch=45, bearing=0
    )


def build_column_layer(df) -> pdk.Layer:
    """3D column per station; height = |net|, color = signed net via net_to_color."""
    return pdk.Layer(
        "ColumnLayer",
        data=df,
        get_position=["lng", "lat"],
        get_elevation="elevation",
        elevation_scale=4,
        radius=30,
        get_fill_color="color",
        pickable=True,
        auto_highlight=True,
    )


def build_highlight_layer(row) -> pdk.Layer:
    """Bright ring marking the selected station. `row` is a 1-row DataFrame."""
    return pdk.Layer(
        "ScatterplotLayer",
        data=row,
        get_position=["lng", "lat"],
        get_radius=60,
        get_fill_color=[255, 255, 0, 120],
        get_line_color=[255, 255, 0, 255],
        stroked=True,
        line_width_min_pixels=3,
        pickable=False,
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_layers.py -v`
Expected: all 3 tests PASS

- [ ] **Step 5: Run the full suite**

Run: `pytest -q`
Expected: all tests PASS (transform 5, metrics 4, fetch 2, layers 3).

- [ ] **Step 6: Commit**

```bash
git add app/layers.py tests/test_layers.py
git commit -m "Add pydeck layer helpers with tested color/view-state logic"
```

---

### Task 12: `app/streamlit_app.py` — assemble the interactive app

**Files:**
- Create: `app/streamlit_app.py`

No unit test (UI). Verified by running Streamlit and interacting.

- [ ] **Step 1: Write the app**

```python
# app/streamlit_app.py
from pathlib import Path

import altair as alt
import pandas as pd
import pydeck as pdk
import streamlit as st

from src.metrics import (
    station_net,
    classify_stations,
    rebalancing_burden,
    cumulative_drift,
)
from app.layers import (
    net_to_color,
    station_view_state,
    build_column_layer,
    build_highlight_layer,
)

PROCESSED = Path("data/processed/station_hour.parquet")

st.set_page_config(page_title="Out of Balance — Citi Bike", layout="wide")


@st.cache_data
def load_netflow() -> pd.DataFrame:
    return pd.read_parquet(PROCESSED)


if not PROCESSED.exists():
    st.error("Processed data not found. Run `python -m src.build 202409` first.")
    st.stop()

netflow = load_netflow()

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
hour = st.sidebar.slider("Cumulative drift through hour", 0, 23, 9)

picker_options = ["(none)"] + sorted(netflow["station_name"].dropna().unique().tolist())
selected_name = st.sidebar.selectbox("Zoom to station", picker_options, index=0)

# --- Apply filters ---
view = netflow[netflow["day_type"] == day_type]
if rider != "all":
    view = view[view["member_casual"] == rider]

# Cumulative drift through the chosen hour, per station.
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
    st.warning("No stations match these filters. Try lowering the minimum trips.")
    st.stop()

# --- Map encodings ---
max_abs = float(drift["net"].abs().max()) or 1.0
drift["elevation"] = drift["net"].abs()
drift["color"] = drift["net"].apply(lambda n: net_to_color(n, max_abs))

# --- KPI row (over the full day for the current filters) ---
classified = classify_stations(
    view.merge(coords[["station_id"]], on="station_id", how="inner"), threshold=10.0
)
k1, k2, k3, k4 = st.columns(4)
k1.metric("Trips (avg/day)", f"{int(view['departures'].sum()):,}")
k2.metric("Rebalancing burden (bikes/day)", f"{int(rebalancing_burden(view)):,}")
k3.metric("Chronic drainers", int((classified["category"] == "drainer").sum()))
k4.metric("Chronic fillers", int((classified["category"] == "filler").sum()))

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
        map_style="mapbox://styles/mapbox/dark-v10",
        tooltip={
            "html": "<b>{station_name}</b><br/>net: {net}",
            "style": {"color": "white"},
        },
    )
)

# --- Supporting charts ---
left, right = st.columns(2)

pulse = (
    view.groupby("hour", as_index=False)["net"]
    .sum()
    .rename(columns={"net": "citywide_net"})
)
left.subheader("Citywide net flow by hour (the tidal pulse)")
left.altair_chart(
    alt.Chart(pulse)
    .mark_area(opacity=0.6)
    .encode(x="hour:O", y="citywide_net:Q")
    .properties(height=260),
    use_container_width=True,
)

ranked = drift.merge(coords[["station_id", "station_name"]], on="station_id")
top_drain = ranked.nsmallest(10, "net")
top_fill = ranked.nlargest(10, "net")
right.subheader("Top drainers (red) and fillers (blue)")
right.altair_chart(
    alt.Chart(pd.concat([top_drain, top_fill]))
    .mark_bar()
    .encode(
        x="net:Q",
        y=alt.Y("station_name_x:N", sort="-x", title="station"),
        color=alt.condition("datum.net < 0", alt.value("#d6604d"), alt.value("#4393c3")),
    )
    .properties(height=260),
    use_container_width=True,
)

# --- Station drill-down ---
if selected_name != "(none)":
    st.subheader(f"Station detail: {selected_name}")
    sel_id = coords[coords["station_name"] == selected_name]["station_id"].iloc[0]
    sel_rows = view[view["station_id"] == sel_id]
    s_net = station_net(sel_rows)["net"].iloc[0] if not sel_rows.empty else 0.0
    category = "drainer" if s_net <= -10 else "filler" if s_net >= 10 else "balanced"
    c1, c2, c3 = st.columns(3)
    c1.metric("Net (avg/day)", f"{s_net:.1f}")
    c2.metric("Category", category)
    c3.metric("Trips (avg/day)", f"{int(sel_rows['departures'].sum() + sel_rows['arrivals'].sum())}")
    hourly = sel_rows.groupby("hour", as_index=False)["net"].sum()
    st.altair_chart(
        alt.Chart(hourly).mark_bar().encode(
            x="hour:O",
            y="net:Q",
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
        "- Data: Citi Bike public trip data, September 2024."
    )
```

- [ ] **Step 2: Run the app and verify interactively**

Run: `streamlit run app/streamlit_app.py`
Expected and to verify manually:
- App loads without error; KPI row shows non-zero trips and a rebalancing burden.
- Dragging the **hour** slider changes column heights/colors (drift grows toward rush hours).
- Switching **weekday/weekend** and **member/casual** changes the map and charts.
- Selecting a station in **Zoom to station** flies/zooms the map to it, shows a yellow highlight ring, and renders the station detail panel with its hourly net-flow bars.
- Setting filters that match nothing shows the friendly "No stations match" warning.

- [ ] **Step 3: Commit**

```bash
git add app/streamlit_app.py
git commit -m "Add Streamlit app: 3D imbalance map, filters, station drill-down"
```

---

### Task 13: README and deployment notes

**Files:**
- Create: `README.md`

- [ ] **Step 1: Write the README**

````markdown
# Out of Balance: NYC's Citi Bike Rebalancing Problem

An interactive map of which Citi Bike stations chronically run empty or overflow,
and how many bikes must be trucked around each day to reset the system.

**Live demo:** _<add Streamlit Community Cloud URL after deploy>_

![screenshot](docs/screenshot.png)

## The question
Every trip moves exactly one bike, so each station accrues a net flow
(arrivals − departures). Persistent imbalance forces Citi Bike to physically
rebalance bikes — a real operational cost. This project maps and quantifies it
for September 2024.

## Highlights
- 3D pydeck map: column height = imbalance magnitude, color = drains (red) vs overflows (blue)
- Hour slider animates cumulative daily drift toward rush hours
- Weekday/weekend and member/casual filters
- Searchable station picker that zooms to any station with a per-station drill-down
- Headline metric: **daily rebalancing burden** (bikes that must be moved)

## Run locally
```bash
pip install -r requirements.txt
python -m src.build 202409        # downloads + processes one month (~hundreds of MB)
streamlit run app/streamlit_app.py
```

## Tests
```bash
pytest -q
```

## How it works
`src/fetch.py` downloads/caches a month → `src/transform.py` cleans and aggregates to
average-per-day net flow per station/hour → `src/metrics.py` classifies stations and
computes the rebalancing burden → `src/build.py` writes `data/processed/station_hour.parquet`
→ `app/streamlit_app.py` reads that parquet and renders the map.

## Deploy
Push to GitHub and deploy on [Streamlit Community Cloud](https://streamlit.io/cloud)
with `app/streamlit_app.py` as the entrypoint. Commit `data/processed/station_hour.parquet`
(or regenerate it in the cloud) since `data/` is gitignored by default. A Mapbox token in
Streamlit secrets enables the dark basemap; without one, pydeck's default basemap is used.

## Data
[Citi Bike System Data](https://citibikenyc.com/system-data) — September 2024.
````

- [ ] **Step 2: Capture a screenshot**

With the app running, take a screenshot of the map and save it to `docs/screenshot.png` (referenced by the README).

- [ ] **Step 3: Commit**

```bash
git add README.md docs/screenshot.png
git commit -m "Add README with narrative, usage, and deployment notes"
```

---

## Self-Review

**Spec coverage:**
- Rebalancing-burden metric → Task 8 + KPI in Task 12. ✓
- Cumulative-drift lead visual → Task 8 (`cumulative_drift`) + hour slider in Task 12. ✓
- Station × hour net flow, weekday/weekend, member/casual → Tasks 4–6, filters in Task 12. ✓
- Drainer/filler classification → Task 7. ✓
- Median station coords / cleaning rules → Tasks 2–3. ✓
- September 2024 data, multi-CSV concat, caching → Tasks 9–10. ✓
- 3D ColumnLayer, diverging color, tooltip, supporting charts, KPI row → Tasks 11–12. ✓
- Searchable picker + zoom-to-station + highlight + drill-down → Task 12 (with `station_view_state`/`build_highlight_layer` from Task 11). ✓
- Friendly empty-filter handling → Task 12 (`st.warning` + `st.stop`). ✓
- Repo structure, README, deployment → file structure + Task 13. ✓
- Click-to-select stretch goal → intentionally not implemented (spec marks it stretch); dropdown is the robust path. ✓

**Placeholder scan:** No TBD/TODO in code. The only `_<add URL>_` is a runtime artifact (live demo link filled in after deploy), and the screenshot is produced in Task 13 Step 2 — both are expected human outputs, not code placeholders.

**Type consistency:** Column names are consistent across tasks (`station_id`, `hour`, `day_type`, `member_casual`, `arrivals`, `departures`, `net`, `station_name`, `lat`, `lng`). `station_net`/`classify_stations`/`rebalancing_burden`/`cumulative_drift` signatures match their call sites in `build.py` and the app. `net_to_color(net, max_abs)`, `station_view_state(lat, lng)`, `build_column_layer(df)`, `build_highlight_layer(row)` match their uses in Task 12.

Note: the top-drainers/fillers chart references `station_name_x` because `drift` already carries `station_name` and the merge adds a second one (`station_name_x`); verify the suffix during Task 12 Step 2 and adjust if pandas names it differently in your version.
