# External Imports
from shapely import affinity
from shapely.geometry.polygon import Polygon
from shapely.geometry import shape
import numpy as np
import os.path as path
import json


# Internal Imports
import driptorch as dt
from driptorch.io import *

from tests.resources import testgeoms

def test_geojson_io() -> None:
    """Test geoJSON io functionality 
    """
    test_polygon_4326: Polygon = read_geojson_polygon(testgeoms.test_polygon)
    polygon_points = np.array(testgeoms.test_polygon["features"][0]["geometry"]["coordinates"][0])
    test_bounds = (np.min(polygon_points[:,0]),np.min(polygon_points[:,1]),np.max(polygon_points[:,0]),np.max(polygon_points[:,1]))

    assert test_polygon_4326.bounds == test_bounds
    geojson_from_Polygon = write_geojson([test_polygon_4326],4326)

    # Test recreated geoJSON for order
    assert geojson_from_Polygon["features"][0]["geometry"]["coordinates"][0][0][0] == testgeoms.test_polygon["features"][0]["geometry"]["coordinates"][0][0][0]

def test_projector() -> None:
    """Test the functionality of the Projector.forward(),Projector.backward(), and Projector.estimate_utm_epsg()
    """

    location = {"lat":46.86028,"lon":-113.98278}
    location_UTM_epsg = 32612
    src_epsg = 4326
    dst_epsg: float = Projector.estimate_utm_epsg(**location) # Estimate UTM EPSG code from lat and lon position

    # Test Projector.estimate_utm_epsg
    assert dst_epsg == location_UTM_epsg

    projecter = Projector(src_epsg=src_epsg,dst_epsg=dst_epsg)
    test_polygon_4326: Polygon = read_geojson_polygon(testgeoms.test_polygon) # Creat Polygon object from geoJSON
    test_polygon_4326_to_UTM: Polygon = projecter.forward(test_polygon_4326) # Project from lat/lon to UTM
    test_polygon_4326_to_UTM_to_4326: Polygon = projecter.backward(test_polygon_4326_to_UTM) # Project from UTM to lat/lon

    # Generate testing objects. Note that projection operations cannot maintain floating point precision 
    # above that of the input points which warrants rounding down.

    test_a = [round(x,5) for x in test_polygon_4326.bounds]
    test_b = [round(x,5) for x in test_polygon_4326_to_UTM_to_4326.bounds]

    # Test Projector.forward and Projector.backward
    assert test_a == test_b
    
def test_web_mercator_funcs() -> None:
    """Test web mercator functionality
    """

    test_polygon_4326: Polygon = read_geojson_polygon(testgeoms.test_polygon)
    utm_epsg, test_polygon_4326_to_UTM = Projector.web_mercator_to_utm(test_polygon_4326)
    test_polygon_4326_to_UTM_to_4326 = Projector.to_web_mercator(test_polygon_4326_to_UTM,utm_epsg)

    # Generate testing objects. Note that projection operations cannot maintain floating point precision 
    # above that of the input points which warrants rounding down.
    test_a = [round(x,5) for x in test_polygon_4326.bounds]
    test_b = [round(x,5) for x in test_polygon_4326_to_UTM_to_4326.bounds]

    # Test Projector.forward and Projector.backward
    assert test_a == test_b


    
def test_write_quickfire() -> None:
    """Test io.write_quicfire()
    """
    validation_data_path = path.join(path.dirname(__file__),"resources/simulation_0.json")
    with open(validation_data_path,"r") as file:
        validation_data = json.load(file)
        pattern = dt.pattern.Pattern.from_dict(validation_data["ring_pattern"],epsg=validation_data["epsg"])
        burn_unit = dt.unit.BurnUnit.from_json(validation_data["burn_unit"],wind_direction=validation_data["args"]["wind_direction"])
        lower_left = validation_data["lower_left"]
        times = pattern.times
        geometries = pattern.geometry
        elapsed_time = pattern.elapsed_time

    #Translate geometries from the firing technique t
    trans_geoms = []
    for geom in geometries:
        trans_geoms.append(affinity.translate(
            geom, -lower_left[0], -lower_left[1]))
    geometries = trans_geoms

    # Generate quicfire output
    quicfire_output = write_quicfire(geometry=geometries,times=times,elapsed_time=elapsed_time,resolution=1)
    test_quicfire_path = path.join(path.dirname(__file__), "resources/quicfire_output_test.dat")
    
    with open(test_quicfire_path,"r") as test_quicfire_output:
        # Truncate for speed
        test_a = '\n'.join(test_quicfire_output.readlines()).replace("\n\n","\n").split("/")[1].strip("\n").split(" ")[:20]
        test_b = quicfire_output.replace("\n\n","\n").split("/")[1].strip("\n").split(" ")[:20]
        assert test_a == test_b
    