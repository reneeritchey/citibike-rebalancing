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


def rebalancing_burden(netflow: pd.DataFrame) -> float:
    """Minimum bikes to move to reset: sum of positive per-station net flow."""
    net = station_net(netflow)["net"]
    return float(net[net > 0].sum())


def cumulative_drift(netflow: pd.DataFrame, up_to_hour: int) -> pd.DataFrame:
    """Per-station net accumulated for all hours <= up_to_hour."""
    sliced = netflow[netflow["hour"] <= up_to_hour]
    return station_net(sliced)


def next_hour(h: int) -> int:
    """Advance an hour-of-day by one, wrapping 23 -> 0 (for animation looping)."""
    return (h + 1) % 24


def chronic_stations(classified: pd.DataFrame, category: str) -> pd.DataFrame:
    """Rows of one category, sorted by net flow.

    Drainers are sorted most-negative first; fillers most-positive first.
    Input is the output of `classify_stations` (columns include `net` and
    `category`). Returns the same columns; an empty frame if none match.
    """
    subset = classified[classified["category"] == category]
    ascending = category == "drainer"
    return subset.sort_values("net", ascending=ascending).reset_index(drop=True)
