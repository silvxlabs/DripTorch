
# Core Imports
from datetime import datetime
import json
import os.path as path
import sys

# Internal Imports
sys.path.append("../driptorch")
import driptorch as dt
from driptorch.io import *
from driptorch._version import __version__
from resources import simulations


def generate_simulations(
    unit_bounds: dict,
    front_buffer: int,
    back_buffer: int,
    firing_direction: float,
    igniter_speed: float,
    number_igniters: float,
    offset: float,
    igniter_spacing: float = None,
    igniter_depth: float = None,
    heat_depth: float = None,
    **kwargs
) -> dict:
    """Generates a suite of all available patterns from a set of arguments

    Args:
        unit_bounds (dict): geoJSON of the unit bondary
        front_buffer (int): Width (meters) of the front buffer
        back_buffer (int): Width (meters) of the back buffer
        firing_direction (float): firing direction azimuth
        igniter_speed (float): Speed of the igniter (meters/second)
        igniter_rate (float): Ignition rate in ipm (ignitions per meter) or ips (ignitions per second).
                Use the `rate_units` parameter to specifiy meters or seconds. An interval of 0 specifies
                a solid ignition line, while a negative value denotes a dashed ignition line and positve a
                dotted ignition line.
        number_igniters (float): Number of igniters for simulation
        offset (float): Offset distance in meters from the unit boundary
        igniter_spacing (float, optional): Staggering distance in meters between igniters within a heat. Defaults to None.
        igniter_depth (float, optional): Depth in meters between igniters. If None, depth is computed by equally spacing igniters. Defaults to None.
        heat_depth (float, optional): Depth in meters between igniter heats. This argument is ignored if depth is None. Defaults to None.

    Returns:
        dict: Simulation data dictionary of validation data
    """

    simulation_date = datetime.now().isoformat()
    simulation_version = __version__
    simulation_data = {
        "version": simulation_version,
        "date": simulation_date,
        "args": locals(),
    }

    burn_unit = dt.BurnUnit.from_json(
        unit_bounds, firing_direction=firing_direction)
    polygonsplitter = dt.unit.PolygonSplitter()
    polygonsplitter.split(burn_unit.polygon)
    simulation_data["burn_unit_fore"] = polygonsplitter.fore.__geo_interface__
    simulation_data["burn_unit_aft"] = polygonsplitter.aft.__geo_interface__
    simulation_data["burn_unit_port"] = polygonsplitter.port.__geo_interface__
    simulation_data["burn_unit_starboard"] = polygonsplitter.starboard.__geo_interface__

    firing_area = burn_unit.buffer_control_line(front_buffer)
    firing_area = firing_area.buffer_downwind(back_buffer)
    blackline_area = burn_unit.difference(firing_area)
    domain = firing_area.copy()
    simulation_data["epsg"] = domain.utm_epsg
    simulation_data["lower_left"] = domain.bounds.min(axis=0).tolist()
    simulation_data["burn_unit"] = burn_unit.to_json()
    simulation_data["firing_area"] = firing_area.to_json()
    simulation_data["blackline"] = blackline_area.to_json()

    dash_igniter = dt.Igniter(igniter_speed)
    point_crew = dt.IgnitionCrew.clone_igniter(dash_igniter, number_igniters)

    simulation_data["igniter"] = dash_igniter.to_json()
    simulation_data["firing_crew"] = point_crew.to_json()

    # Inferno Technique
    inferno_technique = dt.firing.Inferno(firing_area)
    inferno_pattern = inferno_technique.generate_pattern()
    simulation_data["inferno_pattern"] = inferno_pattern.to_dict()

    # Ring Technique
    ring_technique = dt.firing.Ring(firing_area, point_crew)
    ring_pattern = ring_technique.generate_pattern(offset)
    simulation_data["ring_pattern"] = ring_pattern.to_dict()

    # Make validation data for quicfire
    ring_pattern.to_quicfire(firing_area,"quicfire_output_test_ring.dat")

    # Head Technique
    head_technique = dt.firing.Head(firing_area, point_crew)
    head_pattern = head_technique.generate_pattern(offset)
    simulation_data["head_pattern"] = head_pattern.to_dict()

    # Back Technique
    back_technique = dt.firing.Back(firing_area, point_crew)
    back_pattern = back_technique.generate_pattern(offset)
    simulation_data["back_pattern"] = back_pattern.to_dict()
    if igniter_depth:

        # Flank Technique
        flank_technique = dt.firing.Flank(firing_area, point_crew)
        flank_pattern = flank_technique.generate_pattern(
            igniter_depth, heat_depth)
        simulation_data["flank_pattern"] = flank_pattern.to_dict()
    if igniter_depth and igniter_spacing:

        # Strip Technique
        strip_technique = dt.firing.Strip(firing_area, point_crew)
        strip_pattern = strip_technique.generate_pattern(
            spacing=igniter_spacing, depth=igniter_depth, heat_depth=heat_depth
        )
        simulation_data["strip_pattern"] = strip_pattern.to_dict()

    return simulation_data

def patch_simulation_data(read_path: str, patch_data: dict) -> None:
    """Patch a given simulation dataset with updated values

    Args:
        read_path (str): relative path to simulation data
        patch_data (dict): dictionary of data and its respective value
    """
    with open(read_path, "r") as file:
        sim_data = json.load(file)

    for k,v in patch_data.items():
        sim_data[k] = v

    with open(read_path, "w") as file:
        json.dump(sim_data, file)

if __name__ == "__main__":
    simargs = simulations.simulation_args
    simulation_data = generate_simulations(**simargs)
    write_path = path.join(path.dirname(__file__),
                           "resources/simulation_0.json")
    patch_data = {"strip_pattern":simulation_data["strip_pattern"]}

    patch_simulation_data(write_path,patch_data=patch_data)
