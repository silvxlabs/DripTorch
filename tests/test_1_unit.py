# External Imports
from shapely import affinity
from shapely.geometry.polygon import Polygon
import numpy as np
import json

# Core Imports
import os.path as path
from datetime import datetime

# Internal Imports
import driptorch as dt
from driptorch.io import *
from driptorch._version import __version__
from tests.resources import simulations

"""
Testing functions for class objects of unit.py

"""

def test_json_from_to() -> None:
    """Test BurnUnit JSON writing/reading functionality
    """
    validation_data_path = path.join(path.dirname(__file__),"resources/simulation_0.json")
    with open(validation_data_path,"r") as file:
        validation_data = json.load(file)

    # Generate test data
    burn_unit = dt.unit.BurnUnit.from_json(validation_data["burn_unit"],wind_direction=validation_data["args"]["wind_direction"])
    new_json = burn_unit.to_json()

    test_a = burn_unit.polygon.bounds
    test_b = dt.unit.BurnUnit.from_json(new_json,wind_direction=validation_data["args"]["wind_direction"]).polygon.bounds
    assert test_a == test_b



def test_align_unalign() -> None:
    """Test BurnUnit align functionality
    """
    validation_data_path = path.join(path.dirname(__file__),"resources/simulation_0.json")
    with open(validation_data_path,"r") as file:
        validation_data = json.load(file)

     burn_unit = dt.unit.BurnUnit.from_json(validation_data["burn_unit"],wind_direction=validation_data["args"]["wind_direction"])
   
    # Align the burn unit, then unalign and compare to the original
    aligned = burn_unit.copy()
    aligned._align()
    unaligned = aligned.copy()
    unaligned._unalign()

    test_a = [x for x in burn_unit.polygon.exterior.coords]
    test_b = [x for x in unaligned.polygon.exterior.coords]
    assert test_a == test_b


def test_buffer_functions() -> None:
    """Test BurnUnit buffer functionality
    """
    truncate = lambda x: (round(x[0],5),round(x[1],5)) #Helper function for rounding down coordinates
    validation_data_path = path.join(path.dirname(__file__),"resources/simulation_0.json")
    with open(validation_data_path,"r") as file:
        validation_data = json.load(file)

    # Generate test data
    args = validation_data["args"]
    burn_unit = dt.unit.BurnUnit.from_json(validation_data["burn_unit"],wind_direction=validation_data["args"]["wind_direction"])
    firing_area = burn_unit.buffer_control_line(args["front_buffer"])
    firing_area = firing_area.buffer_downwind(args["back_buffer"])
    blackline_area = burn_unit.difference(firing_area)
    validation_firing_area = dt.unit.BurnUnit.from_json(validation_data["firing_area"],wind_direction=validation_data["args"]["wind_direction"])
    validation_blackline_area = dt.unit.BurnUnit.from_json(validation_data["blackline"],wind_direction=validation_data["args"]["wind_direction"])

    # Build new firing area and test against the validation data
    test_a = [truncate(x) for x in firing_area.polygon.exterior.coords]
    test_b = [truncate(x) for x in validation_firing_area.polygon.exterior.coords]
    assert test_a == test_b

    # Build new blackline area and test agains the validation data
    test_a = [truncate(x) for x in blackline_area.polygon.exterior.coords]
    test_b = [truncate(x) for x in validation_blackline_area.polygon.exterior.coords]
    assert test_a == test_b