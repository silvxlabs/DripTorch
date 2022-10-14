
# Core Imports
from datetime import datetime
import json
import os.path as path

# Internal Imports
import driptorch as dt
from driptorch.io import *
from driptorch._version import __version__
from resources import simulations


def generate_simulations(
    unit_bounds: dict,
    front_buffer: int,
    back_buffer: int,
    wind_direction: float,
    igniter_speed: float,
    igniter_rate: float,
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
        wind_direction (float): Wind direction azimuth
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
        unit_bounds, wind_direction=wind_direction)
    polygonsplitter = dt.unit.PolygonSplitter()
    polygonsplitter.split(burn_unit.polygon)
    simulation_data["burn_unit_fore"] = polygonsplitter.fore.__geo_interface__
    simulation_data["burn_unit_aft"] = polygonsplitter.aft.__geo_interface__
    simulation_data["burn_unit_port"] = polygonsplitter.port.__geo_interface__
    simulation_data["burn_unit_starboard"] = polygonsplitter.starboard.__geo_interface__

    firing_area = burn_unit.buffer_control_line(front_buffer)
    firing_area = firing_area.buffer_downwind(back_buffer)
    blackline_area = burn_unit.difference(firing_area)
    domain = burn_unit.copy()
    simulation_data["epsg"] = domain.utm_epsg
    simulation_data["lower_left"] = domain.bounds.min(axis=0).tolist()
    simulation_data["burn_unit"] = burn_unit.to_json()
    simulation_data["firing_area"] = firing_area.to_json()
    simulation_data["blackline"] = blackline_area.to_json()

    dash_igniter = dt.Igniter(igniter_speed, igniter_rate)
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
            igniter_spacing, igniter_depth, heat_depth
        )
        simulation_data["strip_pattern"] = strip_pattern.to_dict()

    return simulation_data



def patch_simulation(simulation_path:str, input_data:dict) -> None:
    """Patch a given simulation data set with input data. Marks the time, current Drip Torch Verion
       and updated fields

    Args:
        simulation_path (str): Path to the simulation data
        input_data (dict): Data to be patched into the simulation formated as {Field:Data}
    """

    simulation_data_path = path.join(path.dirname(__file__), simulation_path)
    with open(simulation_data_path, "r") as file:
        simulation_data = json.load(file)

    fields = list(input_data.keys())
    patch_data = {
        "date": datetime.now().isoformat(),
        "version": dt._version.__version__,
        "fields":fields
    }
    try:
        simulation_data["patch_history"].append(patch_data)
    except KeyError:
        simulation_data["patch_history"] = [patch_data]

    for k,v in input_data.items():
        try:
            simulation_data[k] = json.dumps(v)
        except Error as e:
            print(f"\n Error: {e} \n Patching to {simulation_path} failed for {k}\n")

    with open(simulation_data_path, "w") as file:
        json.dump(simulation_data, file)
    

if __name__ == "__main__":
    simargs = simulations.simulation_args
    simulation_data = generate_simulations(**simargs)
    input_data_fields = ["igniter","firing_crew"]

    input_data = {
        k : simulation_data[k] for k in input_data_fields
    }

    simulation_path = path.join(path.dirname(__file__),
                           "resources/simulation_0.json")

    patch_simulation(simulation_path, input_data)
    
    
    '''
    with open(write_path, "w") as file:
        json.dump(simulation_data, file)
    '''