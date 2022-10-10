from .testgeoms import test_polygon

simulation_args = {
    "unit_bounds" : test_polygon,
    "front_buffer" : 5,
    "back_buffer" : 20,
    "wind_direction" : 0,
    "igniter_speed" : 1.8,
    "igniter_rate" : -1/20,
    "number_igniters" : 2,
    "offset" : 50
}