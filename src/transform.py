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
