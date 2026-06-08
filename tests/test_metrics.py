import pandas as pd

from src.transform import (
    clean_trips,
    station_hour_totals,
    day_counts,
    normalize_per_day,
)
from src.metrics import (
    station_net,
    classify_stations,
    rebalancing_burden,
    cumulative_drift,
)


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


def test_rebalancing_burden_sums_positive_net(sample_trips):
    netflow = _netflow(sample_trips)

    assert rebalancing_burden(netflow) == 1.0


def test_cumulative_drift_accumulates_through_hour(sample_trips):
    netflow = _netflow(sample_trips)

    drift = cumulative_drift(netflow, up_to_hour=8).set_index("station_id")["net"]

    assert drift.loc["A"] == -2.0
    assert drift.loc["B"] == 2.0
