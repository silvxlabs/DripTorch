# External Imports
from shapely.geometry import shape
from numpy.testing import assert_array_almost_equal

# Core Imports
import json
import os.path as path

# Internal Imports
import driptorch as dt

"""
The following defined functions are for testing class objects of unit.py.

We use the construct of "Validation data" for previously generated data,
and the construct of "Test data" for data generated at run time.

Test data is compared against validation data to assert the functionality of
class objects and their associated methods.

To run these tests, call "pytest -ss -v" from the terminal.
"""

SIMULATION_PATH = "resources/simulation_0.json"


def test_json_from_to() -> None:
    """Test BurnUnit JSON writing/reading functionality"""

    validation_data_path = path.join(path.dirname(__file__), SIMULATION_PATH)
    with open(validation_data_path, "r") as file:
        validation_data = json.load(file)

    # Generate test data
    burn_unit = dt.unit.BurnUnit.from_json(
        validation_data["burn_unit"],
        wind_direction=validation_data["args"]["wind_direction"],
    )
    new_json = burn_unit.to_json()

    test_a = burn_unit.polygon.bounds
    test_b = dt.unit.BurnUnit.from_json(
        new_json, wind_direction=validation_data["args"]["wind_direction"]
    ).polygon.bounds
    assert test_a == test_b

    test_a = burn_unit.polygon_segments
    test_b = burn_unit.polygon_segments
    assert test_a == test_b


def test_align_unalign() -> None:
    """Test BurnUnit align functionality"""

    validation_data_path = path.join(path.dirname(__file__), SIMULATION_PATH)
    with open(validation_data_path, "r") as file:
        validation_data = json.load(file)

    burn_unit = dt.unit.BurnUnit.from_json(
        validation_data["burn_unit"],
        wind_direction=validation_data["args"]["wind_direction"],
    )

    # Align the burn unit, then unalign and compare to the original
    aligned = burn_unit.copy()
    aligned._align()
    unaligned = aligned.copy()
    unaligned._unalign()

    test_a = list(burn_unit.polygon.exterior.coords)
    test_b = list(unaligned.polygon.exterior.coords)
    assert_array_almost_equal(
        test_a,
        test_b,
        decimal=5,
        err_msg="\nTest burn_unit and augmented burn_unit are not aligned\n",
    )


def test_buffer_functions() -> None:
    """Test BurnUnit buffer functionality"""

    validation_data_path = path.join(path.dirname(__file__), SIMULATION_PATH)
    with open(validation_data_path, "r") as file:
        validation_data = json.load(file)

    # Generate test data
    args = validation_data["args"]
    burn_unit = dt.unit.BurnUnit.from_json(
        validation_data["burn_unit"],
        wind_direction=validation_data["args"]["wind_direction"],
    )
    firing_area = burn_unit.buffer_control_line(args["front_buffer"])
    firing_area = firing_area.buffer_downwind(args["back_buffer"])
    blackline_area = burn_unit.difference(firing_area)
    validation_firing_area = dt.unit.BurnUnit.from_json(
        validation_data["firing_area"],
        wind_direction=validation_data["args"]["wind_direction"],
    )
    validation_blackline_area = dt.unit.BurnUnit.from_json(
        validation_data["blackline"],
        wind_direction=validation_data["args"]["wind_direction"],
    )

    # Build new firing area and test against the validation data
    test_a = list(firing_area.polygon.exterior.coords)
    test_b = list(validation_firing_area.polygon.exterior.coords)
    assert_array_almost_equal(
        test_a,
        test_b,
        decimal=5,
        err_msg="\nTest firing_area and validation firing_area are not aligned\n",
    )

    # Build new blackline area and test agains the validation data
    test_a = list(blackline_area.polygon.exterior.coords)
    test_b = list(validation_blackline_area.polygon.exterior.coords)
    assert_array_almost_equal(
        test_a,
        test_b,
        decimal=5,
        err_msg="\nTest blackline_area and validation blackline_area are not aligned\n",
    )


def test_polygon_splitter() -> None:
    """Test PolygonSplitter() functionality"""

    validation_data_path = path.join(path.dirname(__file__), SIMULATION_PATH)
    with open(validation_data_path, "r") as file:
        validation_data = json.load(file)

    # Generate validation and test data
    burn_unit_validation = dt.unit.BurnUnit.from_json(
        validation_data["burn_unit"],
        wind_direction=validation_data["args"]["wind_direction"],
    )
    fore_validation = shape(validation_data["burn_unit_fore"])
    aft_validation = shape(validation_data["burn_unit_aft"])
    port_validation = shape(validation_data["burn_unit_port"])
    starboard_validation = shape(validation_data["burn_unit_starboard"])
    polygon_splitter_test = dt.unit.PolygonSplitter()
    polygon_splitter_test.split(burn_unit_validation.polygon)

    # Test PolygonSplitter.split() functionality

    # Check Fore
    test_a = list(polygon_splitter_test.fore.coords)
    test_b = list(fore_validation.coords)
    assert_array_almost_equal(
        test_a,
        test_b,
        decimal=5,
        err_msg="\nTest fore and validation fore are not aligned\n",
    )

    # Check Aft
    test_a = list(polygon_splitter_test.aft.coords)
    test_b = list(aft_validation.coords)
    assert_array_almost_equal(
        test_a,
        test_b,
        decimal=5,
        err_msg="\nTest aft and validation aft are not aligned\n",
    )

    # Check Port
    test_a = list(polygon_splitter_test.port.coords)
    test_b = list(port_validation.coords)
    assert_array_almost_equal(
        test_a,
        test_b,
        decimal=5,
        err_msg="\nTest port and validation port are not aligned\n",
    )

    # Check Starboard
    test_a = list(polygon_splitter_test.starboard.coords)
    test_b = list(starboard_validation.coords)
    assert_array_almost_equal(
        test_a,
        test_b,
        decimal=5,
        err_msg="\nTest starboard and validation starboard are not aligned\n",
    )
