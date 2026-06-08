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
