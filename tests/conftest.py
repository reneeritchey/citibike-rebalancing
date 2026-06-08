import pandas as pd
import pytest


@pytest.fixture
def sample_trips():
    """Three trips with hand-verifiable net flows.

    Trip 1: A->B, 2024-09-02 08:00 (Mon/weekday), member
    Trip 2: A->B, 2024-09-02 08:30 (Mon/weekday), member
    Trip 3: B->A, 2024-09-07 10:00 (Sat/weekend), casual
    """
    return pd.DataFrame(
        {
            "started_at": [
                "2024-09-02 08:00:00",
                "2024-09-02 08:30:00",
                "2024-09-07 10:00:00",
            ],
            "ended_at": [
                "2024-09-02 08:10:00",
                "2024-09-02 08:45:00",
                "2024-09-07 10:20:00",
            ],
            "start_station_id": ["A", "A", "B"],
            "start_station_name": ["Alpha", "Alpha", "Beta"],
            "start_lat": [40.70, 40.70, 40.80],
            "start_lng": [-74.00, -74.00, -73.90],
            "end_station_id": ["B", "B", "A"],
            "end_station_name": ["Beta", "Beta", "Alpha"],
            "end_lat": [40.80, 40.80, 40.70],
            "end_lng": [-73.90, -73.90, -74.00],
            "member_casual": ["member", "member", "casual"],
        }
    )
