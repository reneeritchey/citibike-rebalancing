import pandas as pd

from src.fetch import build_url, load_month


def test_build_url_formats_month():
    assert (
        build_url("202409")
        == "https://s3.amazonaws.com/tripdata/202409-citibike-tripdata.zip"
    )


def test_load_month_reads_cached_parquet(tmp_path):
    raw_dir = tmp_path
    cached = pd.DataFrame({"start_station_id": ["A"], "member_casual": ["member"]})
    cached.to_parquet(raw_dir / "202409.parquet")

    result = load_month("202409", raw_dir=raw_dir)

    assert list(result["start_station_id"]) == ["A"]
