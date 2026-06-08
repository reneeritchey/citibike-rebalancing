# Chronic Stations Tables Design

**Date:** 2026-06-08
**Status:** Approved design — ready for implementation planning
**Type:** Feature addition to the citibike-rebalancing Streamlit app

## Goal

Let the user see **which exact stations** are chronic drainers and chronic
fillers — not just the counts in the KPI row. Add two sortable tables listing
every station behind those counts.

## Scope

- **In scope:** a "Chronic Stations" section with two `st.dataframe` tables
  (drainers, fillers) listing each qualifying station with its net/arrivals/
  departures; a small tested helper that filters and sorts by category.
- **Out of scope (YAGNI):** adjustable threshold (kept fixed at ±10), map
  labelling/highlighting of chronic stations, a custom download button (the
  built-in `st.dataframe` toolbar already provides search + CSV download),
  removing or changing the existing top-10 bar chart.

## Definition of "chronic"

Reuses the existing classification: `classify_stations(view, threshold=10.0)`
labels a station **drainer** when its total net flow over the period is
`<= -10`, **filler** when `>= 10`, else balanced. This is the same call that
produces the KPI counts, so the tables and the counts cannot drift apart.

- Because classification runs on `view`, the tables respond to the **day-type**
  and **rider** filters, exactly like the KPI row.
- The **min-trips** slider does NOT affect the tables (it only filters the map),
  consistent with how the KPI counts already behave today.

## UX / Layout

A new section titled **"Chronic Stations"** placed **after the supporting
charts** (the tidal-pulse and top-10 bar charts) and before the station
drill-down. Two equal columns via `st.columns(2)`:

```
## Chronic Stations
[ Drainers (66)         ]    [ Fillers (54)          ]
 Station    Net  Arr Dep      Station    Net  Arr Dep
 E 2 St…   -82  ...            E 47 St…  +138 ...
 …(scroll, sortable)          …(scroll, sortable)
```

- Left column header: `#### Drainers (N)` where N is the row count.
- Right column header: `#### Fillers (N)`.
- Each table rendered with `st.dataframe(..., hide_index=True,
  use_container_width=True, height=360)` — giving built-in column-header
  sorting, search, and CSV download via its toolbar, with scroll for long lists.

**Columns (display names), rounded to 1 decimal:**
- `Station` (station name)
- `Net (avg/day)`
- `Arrivals (avg/day)`
- `Departures (avg/day)`

**Default order:** Drainers most-negative net first; Fillers most-positive net
first. (Users can re-sort by clicking headers.)

**Empty state:** If a category has zero stations under the current filters, show
`st.info("No chronic drainers at the current filters.")` (or "fillers") instead
of an empty table.

## Components / Data flow

1. `classified = classify_stations(view, threshold=10.0)` — already computed for
   the KPI row; reuse the same DataFrame (columns: `station_id`, `arrivals`,
   `departures`, `net`, `category`).
2. New pure helper in `src/metrics.py`:
   `chronic_stations(classified, category)` — returns the rows whose
   `category == category`, sorted by `net` ascending for `"drainer"` and
   descending for `"filler"`. Returns the same columns it received (no display
   formatting, no name merge — those stay in the app for testability).
3. In the app: merge the helper's output with `coords`
   (`station_id → station_name`), rename columns to the display names above,
   round to 1 decimal, and render with `st.dataframe`.

## Testing

- **TDD** `chronic_stations`:
  - Given a small classified frame with drainers, fillers, and balanced rows,
    `chronic_stations(df, "drainer")` returns only drainers, sorted by `net`
    ascending (most negative first).
  - `chronic_stations(df, "filler")` returns only fillers, sorted by `net`
    descending (most positive first).
  - A category with no matching rows returns an empty frame.
- Existing 15 tests must stay green.
- **Manual + Playwright verification:** confirm the two tables render, the row
  counts match the KPI drainer/filler counts, and the first drainer row has the
  most-negative net / first filler row the most-positive.

## Success criteria

- The app shows two tables naming every chronic drainer and filler.
- Drainer/filler table row counts equal the KPI "Chronic drainers"/"Chronic
  fillers" numbers for the same filters.
- Tables are sortable and downloadable (via `st.dataframe`'s toolbar) and handle
  the empty case gracefully.
