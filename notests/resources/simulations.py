# Core imports
from datetime import datetime
import json

# Internal imports
import driptorch as dt
from .testgeoms import test_polygon

simulation_args = {
    "unit_bounds": test_polygon,
    "front_buffer": 5,
    "back_buffer": 20,
    "firing_direction": 0,
    "igniter_speed": 0.804,
    "igniter_depth": 10,
    "igniter_spacing": 10,
    "number_igniters": 2,
    "heat_depth": 10,
    "offset": 50
}

