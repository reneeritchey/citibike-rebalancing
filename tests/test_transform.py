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
