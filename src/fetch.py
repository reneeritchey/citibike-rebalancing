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
