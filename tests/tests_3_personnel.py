# External Imports
import numpy as np
from numpy.testing import assert_array_almost_equal
import json

# Core Imports
import os
import os.path as path
from datetime import datetime
import itertools
import tempfile

# Internal Imports
import driptorch as dt
from tests.resources import simulations


"""
The following defined functions are for testing class objects of personnel.py.

We use the construct of "Validation data" for previously generated data,
and the construct of "Test data" for data generated at run time.

Test data is compared against validation data to assert the functionality of
class objects and their associated methods.

To run these tests, call "pytest -ss -v" from the terminal.
"""

SIMULATION_PATH = "resources/simulation_0.json"
QF_VALIDATION_PATH = "resources/quicfire_output_test.dat"

def test_igniter() -> None:
    """Test personnel.Igniter() and personnel.IgnitionCrew() functionality
    """
    validation_data_path = path.join(path.dirname(__file__), SIMULATION_PATH)
    
    with open(validation_data_path, "r") as file:
        validation_data = json.load(file)
    igniter_test = dt.igniter(validation_data["args"]["ignitor_speed"],validation_data["args"]["ignitor_speed"])
    ignition_crew_test = dt.IgnitionCrew.clone_igniter(igniter_test,validation_data["args"]["number_ignitors"])
    
    igniter_validation = dt.Igniter().from_json(validation_data["igniter"])
    ignition_crew_validation = dt.IgnitionCrew.from_json(validation_data["firing_crew"])

    test_a = igniter_test
    test_b = igniter_validation
    assert test_a == test_b

    test_a = ignition_crew_test
    test_b = ignition_crew_validation
    assert test_a == test_b

    test_a = ignition_crew_test.add_igniter(igniter_test)
    test_b = ignition_crew_validation.add_igniter(igniter_test)
    assert test_a == test_b