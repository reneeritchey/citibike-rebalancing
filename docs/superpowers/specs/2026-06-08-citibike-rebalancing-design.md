# Out of Balance: Mapping NYC's Citi Bike Rebalancing Problem

**Date:** 2026-06-08
**Status:** Approved design — ready for implementation planning
**Type:** Portfolio project (urban analytics: interactive data visualization + analysis)

## Goal

A polished, interactive portfolio piece that answers one sharp question:

> **Which Citi Bike stations chronically run empty or overflow, and how large is the daily "bike-moving" burden that imbalance creates?**

Every trip moves exactly one bike, so each station accrues a **net flow** (arrivals − departures). Persistent imbalance is what forces Citi Bike to physically truck bikes between stations — a real operational cost. We map and quantify it.

The audience is hiring managers for urban-analytics / data-science roles. Success = analysis-forward narrative, visually striking interactive map, and a live public URL.

## Scope

- **In scope:** one representative month of Citi Bike trips; station × hour net-flow analysis; drainer/filler classification; rebalancing-burden metric; an interactive Streamlit + pydeck app with station search/zoom-to-station and a per-station drill-down.
- **Out of scope (YAGNI):** multi-month/seasonal comparison, weather joins, taxi data, predictive modeling, live/real-time data, user accounts.

## Tech Stack

- **Language:** Python (single stack end-to-end).
- **Analysis:** pandas (+ pyarrow for parquet).
- **App:** Streamlit.
- **Map:** pydeck (deck.gl) over a dark Mapbox basemap.
- **Supporting charts:** Altair (or Plotly).
- **Deployment:** GitHub → Streamlit Community Cloud (free public URL).

## Data

- **Source:** Citi Bike public trip data, `https://s3.amazonaws.com/tripdata/`.
- **Month:** September 2024 (high ridership, weather-neutral, recent). ~3–4M trips.
- **Relevant columns:** `started_at`, `ended_at`, `start_station_id`, `start_station_name`, `start_lat`, `start_lng`, `end_station_id`, `end_station_name`, `end_lat`, `end_lng`, `member_casual`, `rideable_type`.
- **Cleaning rules:**
  - Drop rows with null coordinates or missing station id/name (log dropped count).
  - Dedup station coordinates: a station id may carry slightly varying lat/lng across rows → assign each station its **median** lat/lng.
  - Flag round trips (start station == end station); they contribute 0 net flow but count as activity.

## Analysis

1. **Station × hour net flow** — for each station and hour-of-day (0–23), `net = arrivals − departures`, split by weekday vs. weekend and by `member_casual`. Departures counted at the start station, arrivals at the end station.
2. **Cumulative daily drift** — net flow accumulated through the day per station (the lead visual): stations diverge from morning, peak imbalance at rush hours, reset overnight.
3. **Classification** — label each station as a chronic **drainer** (net-negative, runs empty), **filler** (net-positive, overflows), or **balanced**, via a threshold on average daily net flow.
4. **Rebalancing burden** — sum of positive daily net flows across stations = minimum number of bikes that must be moved per day to reset the system. This is the headline KPI.

### Filters driving the views
Hour-of-day, weekday vs. weekend, member vs. casual, minimum-trips threshold (hide tiny stations).

## Application Design

### Visuals
- **Main map — pydeck `ColumnLayer` (3D columns).** One column per station: **height = magnitude** of net imbalance; **color = diverging scale** (deep red = drains empty, deep blue = overflows, pale = balanced). Hover tooltip: station name, arrivals, departures, net.
- **Hour slider** drives the map: dragging 0→23 re-renders columns to show **cumulative drift through that hour**. Optional "▶ play" auto-advances the hour for an animated effect.
- **Supporting charts:** citywide net-flow-by-hour line (the "tidal pulse"); top-10 drainers and top-10 fillers (horizontal bars).
- **KPI header row:** total trips; **daily rebalancing burden** (bikes to move); # chronic drainers; # chronic fillers.

### Station selection & zoom-to-station
- **Searchable station picker** in the sidebar (type-to-search dropdown of all station names). Selecting a station:
  - **Flies the map to it** — updates pydeck `view_state` (centered lat/lng, higher zoom, slight 3D pitch).
  - **Highlights it** — distinct highlight layer (bright ring / enlarged column) above the field.
  - **Opens a station detail panel** — that station's KPIs (arrivals, departures, net, classification) and its **hourly net-flow curve** showing why it drains or fills.
- **Technical note / known constraint:** Streamlit's `st.pydeck_chart` does not reliably round-trip click-on-a-column events to Python, so direct map-click selection is unreliable. The **searchable dropdown is the robust design** (and better UX across ~2,000 stations). Click-to-select is a **stretch goal** only if a clean event-handling route proves viable.

### Layout
Sidebar = filters (hour, weekday/weekend, member/casual, min-trips) + station picker. Main pane = KPI row → big map → two-column supporting charts → collapsible "How this works / methodology" note.

## Repo Structure

```
citibike-rebalancing/
├── data/{raw,processed}/        # gitignored
├── src/
│   ├── fetch.py        # download + cache the month
│   ├── transform.py    # clean → station×hour net-flow table
│   └── metrics.py      # classification + KPIs
├── app/
│   ├── streamlit_app.py
│   └── layers.py       # pydeck layer builders
├── tests/              # unit tests on aggregation/metrics
├── requirements.txt
└── README.md           # narrative, screenshots/GIF, live link
```

## Data Flow

`fetch.py` (download raw CSV, cached locally) → `transform.py` (clean + aggregate → `data/processed/station_hour.parquet`) → app reads the small parquet → renders instantly. Heavy work runs **once, offline**; the deployed app stays fast.

## Testing

- **TDD on pure functions:** net-flow aggregation and drainer/filler classification verified against small hand-built fixtures (known trips → known net flow).
- **Data validation:** schema check on download; dropped-row counts logged.
- **UI:** Streamlit app verified manually.

## Error Handling

- Download retries + downloaded-file size/schema validation.
- Null-coordinate / missing-station rows dropped with counts logged.
- Empty filter results show a friendly "no stations match" message instead of a broken map.

## Deployment

Push to GitHub → deploy on Streamlit Community Cloud → public URL for the portfolio. README carries the narrative plus a screenshot/GIF so it lands even without clicking through.

## Open Questions / Assumptions

- Assumes September 2024 file is available in the documented Citi Bike S3 schema; if the month's files are split into multiple CSVs, `fetch.py` concatenates them.
- Mapbox basemap may require a free Mapbox token as a Streamlit secret; pydeck's default basemap is the fallback.
