# Core Imports
import json
import os.path as path

# Internal Imports
import driptorch as dt

# External Imports
from numpy.testing import assert_array_almost_equal


"""
The following defined functions are for testing respective firing techniques in driptorch/firing.

We use the construct of "Validation data" for previously generated data,
and the construct of "Test data" for data generated at run time.

Test data is compared against validation data to assert the functionality of
class objects and their associated methods.

To run these tests, call "pytest -ss -v" from the terminal.
"""

SIMULATION_PATH = "resources/simulation_0.json"

def test_back_technique() -> None:

    validation_data_path = path.join(path.dirname(__file__), SIMULATION_PATH)
    with open(validation_data_path, "r") as file:
        validation_data = json.load(file)

    sim_args = validation_data["args"]
    igniter = dt.Igniter(
       velocity = sim_args["igniter_speed"])

    ignition_crew = dt.IgnitionCrew.clone_igniter(
        igniter, sim_args["number_igniters"])

    burn_unit = dt.unit.BurnUnit.from_json(
        validation_data["firing_area"],
        wind_direction=sim_args["wind_direction"]
    )

    technique = dt.firing.Back(burn_unit, ignition_crew)
    test_pattern = technique.generate_pattern(sim_args["offset"])

    validation_pattern = validation_data["back_pattern"]

    test_a = test_pattern.times
    test_b = validation_pattern["times"]

    assert_array_almost_equal(test_a, test_b,decimal=5)

def test_head_technique() -> None:

    validation_data_path = path.join(path.dirname(__file__), SIMULATION_PATH)
    with open(validation_data_path, "r") as file:
        validation_data = json.load(file)

    sim_args = validation_data["args"]
    igniter = dt.Igniter(
       velocity = sim_args["igniter_speed"])

    ignition_crew = dt.IgnitionCrew.clone_igniter(
        igniter, sim_args["number_igniters"])

    burn_unit = dt.unit.BurnUnit.from_json(
        validation_data["firing_area"],
        wind_direction=sim_args["wind_direction"]
    )

    technique = dt.firing.Head(burn_unit, ignition_crew)
    test_pattern = technique.generate_pattern(sim_args["offset"])

    validation_pattern = validation_data["head_pattern"]

    test_a = test_pattern.times
    test_b = validation_pattern["times"]

    assert_array_almost_equal(test_a, test_b,decimal=5)


def test_flank_technique() -> None:

    validation_data_path = path.join(path.dirname(__file__), SIMULATION_PATH)
    with open(validation_data_path, "r") as file:
        validation_data = json.load(file)

    sim_args = validation_data["args"]
    igniter = dt.Igniter(
       velocity = sim_args["igniter_speed"])

    ignition_crew = dt.IgnitionCrew.clone_igniter(
        igniter, sim_args["number_igniters"])

    burn_unit = dt.unit.BurnUnit.from_json(
        validation_data["firing_area"],
        wind_direction=sim_args["wind_direction"]
    )

    technique = dt.firing.Flank(burn_unit, ignition_crew)
    test_pattern = technique.generate_pattern(sim_args["igniter_depth"],sim_args["heat_depth"])

    validation_pattern = validation_data["flank_pattern"]

    test_a = test_pattern.times
    test_b = validation_pattern["times"]

    assert_array_almost_equal(test_a, test_b,decimal=5)


def test_strip_technique() -> None:

    validation_data_path = path.join(path.dirname(__file__), SIMULATION_PATH)
    with open(validation_data_path, "r") as file:
        validation_data = json.load(file)

    sim_args = validation_data["args"]
    igniter = dt.Igniter(
       velocity = sim_args["igniter_speed"])

    ignition_crew = dt.IgnitionCrew.clone_igniter(
        igniter, sim_args["number_igniters"])

    burn_unit = dt.unit.BurnUnit.from_json(
        validation_data["firing_area"],
        wind_direction=sim_args["wind_direction"]
    )

    technique = dt.firing.Strip(burn_unit, ignition_crew)
    test_pattern = technique.generate_pattern(sim_args["igniter_spacing"],sim_args["igniter_depth"],sim_args["heat_depth"])

    validation_pattern = validation_data["strip_pattern"]

    test_a = test_pattern.times
    test_b = validation_pattern["times"]

    assert_array_almost_equal(test_a, test_b,decimal=5)


def test_inferno_technique() -> None:

    validation_data_path = path.join(path.dirname(__file__), SIMULATION_PATH)
    with open(validation_data_path, "r") as file:
        validation_data = json.load(file)

    sim_args = validation_data["args"]

    burn_unit = dt.unit.BurnUnit.from_json(
        validation_data["firing_area"],
        wind_direction=sim_args["wind_direction"]
    )

    technique = dt.firing.Inferno(burn_unit)
    test_pattern = technique.generate_pattern()

    validation_pattern = validation_data["inferno_pattern"]

    test_a = test_pattern.times
    test_b = validation_pattern["times"]

    assert_array_almost_equal(test_a, test_b,decimal=5)


def test_ring_technique() -> None:

    validation_data_path = path.join(path.dirname(__file__), SIMULATION_PATH)
    with open(validation_data_path, "r") as file:
        validation_data = json.load(file)

    sim_args = validation_data["args"]
    igniter = dt.Igniter(
       velocity = sim_args["igniter_speed"])

    ignition_crew = dt.IgnitionCrew.clone_igniter(
        igniter, sim_args["number_igniters"])

    burn_unit = dt.unit.BurnUnit.from_json(
        validation_data["firing_area"],
        wind_direction=sim_args["wind_direction"]
    )

    technique = dt.firing.Ring(burn_unit, ignition_crew)
    test_pattern = technique.generate_pattern(sim_args["offset"])

    validation_pattern = validation_data["ring_pattern"]

    test_a = test_pattern.times[0]
    test_b = validation_pattern["times"][0]

    assert_array_almost_equal(test_a, test_b,decimal=5)
