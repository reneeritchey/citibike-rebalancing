# Out of Balance: NYC's Citi Bike Rebalancing Problem

An interactive map of which Citi Bike stations chronically run empty or overflow,
and how many bikes must be trucked around each day to reset the system.

**Live demo:** _add Streamlit Community Cloud URL after deploy_

<!-- After running the app, capture a screenshot of the map and save it to
docs/screenshot.png, then uncomment the line below. -->
<!-- ![screenshot](docs/screenshot.png) -->

## The question
Every trip moves exactly one bike, so each station accrues a net flow
(arrivals − departures). Persistent imbalance forces Citi Bike to physically
rebalance bikes — a real operational cost. This project maps and quantifies it
for September 2024. With the default filters, the system carries a rebalancing
burden of roughly **4,300 bikes per weekday** across ~120 chronically imbalanced
stations.

## Highlights
- 3D pydeck map: column height = imbalance magnitude, color = drains (red) vs overflows (blue)
- Hour slider animates cumulative daily drift toward rush hours
- Weekday/weekend and member/casual filters
- Searchable station picker that zooms to any station with a per-station drill-down
- Headline metric: **daily rebalancing burden** (bikes that must be moved)

## Run locally
```bash
pip install -r requirements.txt
python -m src.build 202409        # downloads + processes one month (~hundreds of MB)
streamlit run app/streamlit_app.py
```

## Tests
```bash
pytest -q
```

## How it works
`src/fetch.py` downloads/caches a month → `src/transform.py` cleans and aggregates to
average-per-day net flow per station/hour → `src/metrics.py` classifies stations and
computes the rebalancing burden → `src/build.py` writes `data/processed/station_hour.parquet`
→ `app/streamlit_app.py` reads that parquet and renders the map.

## Deploy
Push to GitHub and deploy on [Streamlit Community Cloud](https://streamlit.io/cloud)
with `app/streamlit_app.py` as the entrypoint. Because `data/` is gitignored, either
force-add the processed file (`git add -f data/processed/station_hour.parquet`) or run
`python -m src.build 202409` as part of the deploy. The map uses a Carto dark basemap,
so **no Mapbox token is required**.

## Data
[Citi Bike System Data](https://citibikenyc.com/system-data) — September 2024.
