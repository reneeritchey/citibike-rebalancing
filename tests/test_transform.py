import numpy as np
import pandas as pd

from src.transform import (
    clean_trips,
    station_coords,
    station_hour_totals,
    day_counts,
    normalize_per_day,
)


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


def test_station_coords_returns_one_row_per_station(sample_trips):
    clean = clean_trips(sample_trips)

    coords = station_coords(clean)

    assert set(coords["station_id"]) == {"A", "B"}
    assert list(coords.columns) == ["station_id", "station_name", "lat", "lng"]
    a = coords.set_index("station_id").loc["A"]
    assert a["station_name"] == "Alpha"
    assert a["lat"] == 40.70
    assert a["lng"] == -74.00


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


def test_day_counts_counts_distinct_dates(sample_trips):
    clean = clean_trips(sample_trips)

    counts = day_counts(clean)

    assert counts == {"weekday": 1, "weekend": 1}


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
