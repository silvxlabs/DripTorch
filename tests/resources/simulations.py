from .testgeoms import test_polygon

simulation_args = {
    "unit_bounds" : test_polygon,
    "front_buffer" : 5,
    "back_buffer" : 20,
    "wind_direction" : 0,
    "ignitor_speed" : 1.8,
    "ignitor_rate" : -1/20,
    "number_ignitors" : 2,
    "offset" : 50,
    "ignitor_spacing" : 5,
    "ignitor_depth" : 5,
    "heat_depth" : 50,
}