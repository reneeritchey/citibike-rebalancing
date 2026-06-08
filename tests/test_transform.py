import numpy as np
import pandas as pd

from src.transform import clean_trips, station_coords


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
