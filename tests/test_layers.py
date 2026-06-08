from app.layers import net_to_color, station_view_state


def test_net_to_color_endpoints_and_midpoint():
    assert net_to_color(0, 10) == [200, 200, 200, 200]
    assert net_to_color(10, 10) == [0, 0, 255, 200]      # max positive -> blue
    assert net_to_color(-10, 10) == [255, 0, 0, 200]     # max negative -> red


def test_net_to_color_handles_zero_max():
    assert net_to_color(5, 0) == [200, 200, 200, 180]


def test_station_view_state_centers_on_station():
    vs = station_view_state(40.75, -73.99)
    assert vs.latitude == 40.75
    assert vs.longitude == -73.99
    assert vs.zoom == 15
    assert vs.pitch == 45
