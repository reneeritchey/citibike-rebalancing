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
    next_hour,
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


def test_next_hour_increments_and_wraps():
    assert next_hour(0) == 1
    assert next_hour(8) == 9
    assert next_hour(22) == 23
    assert next_hour(23) == 0


def test_chronic_stations_filters_and_sorts():
    from src.metrics import chronic_stations

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
