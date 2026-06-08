import pydeck as pdk


def net_to_color(net: float, max_abs: float) -> list:
    """Diverging color: red (drains) -> pale grey (balanced) -> blue (overflows)."""
    if max_abs <= 0:
        return [200, 200, 200, 180]
    t = max(-1.0, min(1.0, net / max_abs))
    if t >= 0:
        return [int(200 * (1 - t)), int(200 * (1 - t)), int(200 + 55 * t), 200]
    t = -t
    return [int(200 + 55 * t), int(200 * (1 - t)), int(200 * (1 - t)), 200]


def station_view_state(lat: float, lng: float) -> pdk.ViewState:
    """Camera focused on a single station (zoomed, tilted for the 3D columns)."""
    return pdk.ViewState(
        latitude=lat, longitude=lng, zoom=15, pitch=45, bearing=0
    )


def build_column_layer(df) -> pdk.Layer:
    """3D column per station; height = |net|, color = signed net via net_to_color."""
    return pdk.Layer(
        "ColumnLayer",
        data=df,
        get_position=["lng", "lat"],
        get_elevation="elevation",
        elevation_scale=4,
        radius=30,
        get_fill_color="color",
        pickable=True,
        auto_highlight=True,
    )


def build_highlight_layer(row) -> pdk.Layer:
    """Bright ring marking the selected station. `row` is a 1-row DataFrame."""
    return pdk.Layer(
        "ScatterplotLayer",
        data=row,
        get_position=["lng", "lat"],
        get_radius=60,
        get_fill_color=[255, 255, 0, 120],
        get_line_color=[255, 255, 0, 255],
        stroked=True,
        line_width_min_pixels=3,
        pickable=False,
    )
