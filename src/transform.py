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
