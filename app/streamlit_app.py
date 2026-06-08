import sys
from pathlib import Path

# Streamlit puts the script's own folder (app/) on sys.path, not the repo root,
# so make the repo root importable for the `src` and `app` packages regardless
# of the working directory (local or Streamlit Community Cloud).
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import altair as alt
import pandas as pd
import pydeck as pdk
import streamlit as st

from src.metrics import (
    station_net,
    classify_stations,
    rebalancing_burden,
    cumulative_drift,
)
from app.layers import (
    net_to_color,
    station_view_state,
    build_column_layer,
    build_highlight_layer,
)

PROCESSED = ROOT / "data" / "processed" / "station_hour.parquet"

st.set_page_config(page_title="Out of Balance — Citi Bike", layout="wide")


@st.cache_data
def load_netflow() -> pd.DataFrame:
    return pd.read_parquet(PROCESSED)


if not PROCESSED.exists():
    st.error("Processed data not found. Run `python -m src.build 202409` first.")
    st.stop()

netflow = load_netflow()

st.title("Out of Balance: NYC's Citi Bike Rebalancing Problem")
st.caption(
    "Every trip moves one bike. Stations that chronically drain or overflow force "
    "Citi Bike to truck bikes around. This maps that imbalance for September 2024."
)

# --- Sidebar filters ---
st.sidebar.header("Filters")
day_type = st.sidebar.radio("Day type", ["weekday", "weekend"], index=0)
rider = st.sidebar.radio("Rider", ["all", "member", "casual"], index=0)
min_trips = st.sidebar.slider("Minimum trips at station (per day)", 0, 50, 5)
hour = st.sidebar.slider("Cumulative drift through hour", 0, 23, 9)

picker_options = ["(none)"] + sorted(netflow["station_name"].dropna().unique().tolist())
selected_name = st.sidebar.selectbox("Zoom to station", picker_options, index=0)

# --- Apply filters ---
view = netflow[netflow["day_type"] == day_type]
if rider != "all":
    view = view[view["member_casual"] == rider]

# Cumulative drift through the chosen hour, per station.
drift = cumulative_drift(view, up_to_hour=hour)
activity = station_net(view)
activity["volume"] = activity["arrivals"] + activity["departures"]
drift = drift.merge(activity[["station_id", "volume"]], on="station_id", how="left")

coords = netflow[["station_id", "station_name", "lat", "lng"]].drop_duplicates(
    "station_id"
)
drift = drift.merge(coords, on="station_id", how="left")
drift = drift[drift["volume"] >= min_trips]

if drift.empty:
    st.warning("No stations match these filters. Try lowering the minimum trips.")
    st.stop()

# --- Map encodings ---
max_abs = float(drift["net"].abs().max()) or 1.0
drift["elevation"] = drift["net"].abs()
drift["color"] = drift["net"].apply(lambda n: net_to_color(n, max_abs))

# --- KPI row (over the full day for the current filters) ---
classified = classify_stations(view, threshold=10.0)
k1, k2, k3, k4 = st.columns(4)
k1.metric("Trips (avg/day)", f"{int(view['departures'].sum()):,}")
k2.metric("Rebalancing burden (bikes/day)", f"{int(rebalancing_burden(view)):,}")
k3.metric("Chronic drainers", int((classified["category"] == "drainer").sum()))
k4.metric("Chronic fillers", int((classified["category"] == "filler").sum()))

# --- Map ---
layers = [build_column_layer(drift)]
initial_view = pdk.ViewState(latitude=40.74, longitude=-73.98, zoom=11, pitch=45)

if selected_name != "(none)":
    sel = drift[drift["station_name"] == selected_name]
    if not sel.empty:
        row = sel.iloc[0]
        layers.append(build_highlight_layer(sel))
        initial_view = station_view_state(row["lat"], row["lng"])

st.pydeck_chart(
    pdk.Deck(
        layers=layers,
        initial_view_state=initial_view,
        map_style="dark_no_labels",
        tooltip={
            "html": "<b>{station_name}</b><br/>net: {net}",
            "style": {"color": "white"},
        },
    ),
    # Keying on the selected station forces the deck.gl component to remount when
    # the selection changes, so it re-applies `initial_view_state` and actually
    # flies to the station. Without this, deck.gl keeps its current camera across
    # reruns and the "zoom to station" never moves the map. The key intentionally
    # excludes the filters so panning/zooming survives slider changes.
    key=f"deck-{selected_name}",
)

# --- Supporting charts ---
left, right = st.columns(2)

pulse = (
    view.groupby("hour", as_index=False)["net"]
    .sum()
    .rename(columns={"net": "citywide_net"})
)
left.subheader("Citywide net flow by hour (the tidal pulse)")
left.altair_chart(
    alt.Chart(pulse)
    .mark_area(opacity=0.6)
    .encode(x="hour:O", y="citywide_net:Q")
    .properties(height=260),
    use_container_width=True,
)

top_drain = drift.nsmallest(10, "net")
top_fill = drift.nlargest(10, "net")
right.subheader("Top drainers (red) and fillers (blue)")
right.altair_chart(
    alt.Chart(pd.concat([top_drain, top_fill]))
    .mark_bar()
    .encode(
        x="net:Q",
        y=alt.Y("station_name:N", sort="-x", title="station"),
        color=alt.condition("datum.net < 0", alt.value("#d6604d"), alt.value("#4393c3")),
    )
    .properties(height=260),
    use_container_width=True,
)

# --- Station drill-down ---
if selected_name != "(none)":
    st.subheader(f"Station detail: {selected_name}")
    sel_id = coords[coords["station_name"] == selected_name]["station_id"].iloc[0]
    sel_rows = view[view["station_id"] == sel_id]
    s_net = station_net(sel_rows)["net"].iloc[0] if not sel_rows.empty else 0.0
    category = "drainer" if s_net <= -10 else "filler" if s_net >= 10 else "balanced"
    c1, c2, c3 = st.columns(3)
    c1.metric("Net (avg/day)", f"{s_net:.1f}")
    c2.metric("Category", category)
    c3.metric(
        "Trips (avg/day)",
        f"{int(sel_rows['departures'].sum() + sel_rows['arrivals'].sum())}",
    )
    hourly = sel_rows.groupby("hour", as_index=False)["net"].sum()
    st.altair_chart(
        alt.Chart(hourly).mark_bar().encode(
            x="hour:O",
            y="net:Q",
            color=alt.condition("datum.net < 0", alt.value("#d6604d"), alt.value("#4393c3")),
        ).properties(height=240),
        use_container_width=True,
    )

with st.expander("How this works / methodology"):
    st.markdown(
        "- **Net flow** = arrivals − departures, per station. Negative = drains empty; "
        "positive = overflows.\n"
        "- Counts are normalized to **average per day** of the selected day type, so "
        "weekday and weekend are comparable.\n"
        "- **Cumulative drift through hour H** sums each station's net flow for hours 0–H.\n"
        "- **Rebalancing burden** = sum of positive per-station net flow = the minimum "
        "bikes that must be moved to reset the system each day.\n"
        "- Data: Citi Bike public trip data, September 2024."
    )
