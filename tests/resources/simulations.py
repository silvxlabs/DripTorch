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
    "wind_direction": 0,
    "igniter_speed": 1.8,
    "igniter_rate": -20,
    "number_igniters": 2,
    "offset": 50
}

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
        "version": dt.__version__,
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
    