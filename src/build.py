"""Offline pipeline: download a month and write the app's processed parquet.

Usage: python -m src.build [YYYYMM]   (default 202409)
"""
import sys
from pathlib import Path

from src.fetch import load_month
from src.transform import (
    clean_trips,
    station_coords,
    station_hour_totals,
    day_counts,
    normalize_per_day,
)

RAW_DIR = Path("data/raw")
PROCESSED_DIR = Path("data/processed")


def build(yyyymm: str = "202409") -> None:
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    raw = load_month(yyyymm, raw_dir=RAW_DIR)
    print(f"Loaded {len(raw):,} raw trips for {yyyymm}")

    clean = clean_trips(raw)
    print(f"Kept {len(clean):,} trips after cleaning ({len(raw) - len(clean):,} dropped)")

    totals = station_hour_totals(clean)
    netflow = normalize_per_day(totals, day_counts(clean))
    coords = station_coords(clean)

    netflow = netflow.merge(coords, on="station_id", how="left")
    out = PROCESSED_DIR / "station_hour.parquet"
    netflow.to_parquet(out)
    coords.to_parquet(PROCESSED_DIR / "stations.parquet")
    print(f"Wrote {out} with {len(netflow):,} rows across {coords.shape[0]:,} stations")


if __name__ == "__main__":
    build(sys.argv[1] if len(sys.argv) > 1 else "202409")
