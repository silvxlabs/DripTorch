# External Imports
from numpy.testing import assert_array_almost_equal

# Core Imports
import json
import os
import os.path as path
import itertools
import tempfile

# Internal Imports
import driptorch as dt

"""
The following defined functions are for testing class objects of pattern.py.

We use the construct of "Validation data" for previously generated data,
and the construct of "Test data" for data generated at run time.

Test data is compared against validation data to assert the functionality of
class objects and their associated methods.

To run these tests, call "pytest -ss -v" from the terminal.
"""

SIMULATION_PATH = "resources/simulation_0.json"
QF_VALIDATION_PATH = "resources/quicfire_output_test.dat"


def test_pattern_io() -> None:
    """Test the I/O functionality for Pattern
    """

    validation_data_path = path.join(path.dirname(__file__), SIMULATION_PATH)
    qf_validation_data_path = path.join(
        path.dirname(__file__), QF_VALIDATION_PATH)

    with open(validation_data_path, "r") as file:
        validation_data = json.load(file)

    with open(qf_validation_data_path, "r") as file:
        qf_validation_data = "\n".join(file.readlines())

    test_pattern_0 = dt.pattern.Pattern.from_dict(
        validation_data["head_pattern"], epsg=validation_data["epsg"]
    )
    test_pattern_1 = dt.pattern.Pattern.from_dict(
        validation_data["ring_pattern"], epsg=validation_data["epsg"]
    )
    test_burn_unit = dt.BurnUnit.from_json(
        validation_data["burn_unit"],
        wind_direction=validation_data["args"]["wind_direction"],
    )

    # Test Pattern.to_dict()
    test_a = test_pattern_0.to_dict()["times"]
    test_b = validation_data["head_pattern"]["times"]
    assert test_a == test_b

    # Write pattern to quicfire and then open it back up
    test_a = qf_validation_data.split("/")[-1].split("\n").remove("")
    fd, pth = tempfile.mkstemp()
    test_pattern_1.to_quicfire(test_burn_unit, filename=pth)
    with open(pth, "r") as file:
        test_b = "\n".join(file.readlines()).split(
            "/")[-1].split("\n").remove("")
    os.close(fd)
    assert test_a == test_b


def test_merge() -> None:
    """Test the merging functionality for Pattern.merge()
    """

    validation_data_path = path.join(path.dirname(__file__), SIMULATION_PATH)
    qf_validation_data_path = path.join(
        path.dirname(__file__), QF_VALIDATION_PATH)

    with open(validation_data_path, "r") as file:
        validation_data = json.load(file)

    with open(qf_validation_data_path, "r") as file:
        qf_validation_data = "\n".join(file.readlines())

    test_pattern_0 = dt.pattern.Pattern.from_dict(
        validation_data["head_pattern"], epsg=validation_data["epsg"]
    )
    test_pattern_1 = dt.pattern.Pattern.from_dict(
        validation_data["ring_pattern"], epsg=validation_data["epsg"]
    )

    merge_0 = test_pattern_0.merge(test_pattern_1)
    merge_1 = test_pattern_1.merge(test_pattern_0)

    test_a = sorted([x.bounds for x in merge_0.geometry])
    test_b = sorted([x.bounds for x in merge_1.geometry])

    assert_array_almost_equal(
        test_a, test_b, decimal=5, err_msg="\nMerged pattern geometries not aligned.\n"
    )

    test_a = merge_0.elapsed_time
    test_b = merge_1.elapsed_time

    assert_array_almost_equal(
        test_a,
        test_b,
        decimal=5,
        err_msg="\nMerged pattern elapsed times are not equivalent.\n",
    )


def test_translate() -> None:
    """Test the translation functionality for Pattern.translate()
    """

    validation_data_path = path.join(path.dirname(__file__), SIMULATION_PATH)
    qf_validation_data_path = path.join(
        path.dirname(__file__), QF_VALIDATION_PATH)

    with open(validation_data_path, "r") as file:
        validation_data = json.load(file)

    with open(qf_validation_data_path, "r") as file:
        qf_validation_data = "\n".join(file.readlines())

    test_pattern_0 = dt.pattern.Pattern.from_dict(
        validation_data["head_pattern"], epsg=validation_data["epsg"]
    )
    test_pattern_1 = dt.pattern.Pattern.from_dict(
        validation_data["ring_pattern"], epsg=validation_data["epsg"]
    )

    x_off = 100
    y_off = 100

    translated = test_pattern_1.translate(x_off=x_off, y_off=y_off)
    un_translated = translated.translate(x_off=-1 * x_off, y_off=-1 * y_off)

    test_a = [
        x.coords
        for x in list(
            itertools.chain.from_iterable(
                [x.geoms for x in test_pattern_1.geometry])
        )
    ]

    test_b = [
        x.coords
        for x in list(
            itertools.chain.from_iterable(
                [x.geoms for x in un_translated.geometry])
        )
    ]

    assert_array_almost_equal(
        test_a,
        test_b,
        decimal=5,
        err_msg="\nTranslated geometries are not aligned.\n",
    )


def test_temporal_propgation() -> None:
    """Test the functionality of TemporalPropogator()
    """

    validation_data_path = path.join(path.dirname(__file__), SIMULATION_PATH)
    qf_validation_data_path = path.join(
        path.dirname(__file__), QF_VALIDATION_PATH)

    with open(validation_data_path, "r") as file:
        validation_data = json.load(file)

    with open(qf_validation_data_path, "r") as file:
        qf_validation_data = "\n".join(file.readlines())

    dash_igniter = dt.Igniter(
        validation_data["args"]["igniter_speed"],
        validation_data["args"]["igniter_rate"],
    )
    point_crew = dt.IgnitionCrew.clone_igniter(
        dash_igniter, validation_data["args"]["number_igniters"]
    )

    firing_area = dt.BurnUnit.from_json(
        validation_data["firing_area"],
        wind_direction=validation_data["args"]["wind_direction"],
    )

    ring_technique = dt.firing.Ring(firing_area, point_crew)
    ring_pattern_test = ring_technique.generate_pattern(
        validation_data["args"]["offset"]
    )

    ring_pattern_validation = dt.Pattern.from_dict(
        validation_data["ring_pattern"], epsg=validation_data["epsg"]
    )

    test_a = list(itertools.chain.from_iterable(ring_pattern_test.times))
    test_b = list(itertools.chain.from_iterable(ring_pattern_validation.times))

    assert_array_almost_equal(
        test_a,
        test_b,
        decimal=5,
        err_msg="\n Test and validation times are not aligned.\n",
    )
