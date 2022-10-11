# External Imports
from shapely import affinity
from shapely.geometry.polygon import Polygon
import numpy as np
from numpy.testing import assert_array_almost_equal
import os.path as path

# Internal Imports
import driptorch as dt
from driptorch.io import *
from tests.resources import testgeoms

# Core imports
import json

"""
The following defined functions are for testing class objects of io.py.

We use the construct of "Validation data" for previously generated data,
and the construct of "Test data" for data generated at run time.

Test data is compared against validation data to assert the functionality of
class objects and their associated methods.

To run these tests, call "pytest -ss -v" from the terminal.
"""

SIMULATION_PATH = "resources/simulation_0.json"
QF_VALIDATION_DATA = "resources/quicfire_output_test.dat"


def test_geojson_io() -> None:
    """Test geoJSON io functionality"""

    test_polygon_4326: Polygon = read_geojson_polygon(testgeoms.test_polygon)
    polygon_points = np.array(
        testgeoms.test_polygon["features"][0]["geometry"]["coordinates"][0]
    )
    test_bounds = (
        np.min(polygon_points[:, 0]),
        np.min(polygon_points[:, 1]),
        np.max(polygon_points[:, 0]),
        np.max(polygon_points[:, 1]),
    )

    assert test_polygon_4326.bounds == test_bounds
    geojson_from_Polygon = write_geojson([test_polygon_4326], 4326)

    # Test recreated geoJSON for order
    test_a = geojson_from_Polygon["features"][0]["geometry"]["coordinates"][0]
    test_b = testgeoms.test_polygon["features"][0]["geometry"]["coordinates"][0]

    assert_array_almost_equal(
        test_a,
        test_b,
        decimal=5,
        err_msg="\nTest polygon and validation polygon are not aligned\n",
    )


def test_projector() -> None:
    """Test the functionality of the Projector.forward(),Projector.backward(), and Projector.estimate_utm_epsg()"""

    location = {"lat": 46.86028, "lon": -113.98278}
    location_UTM_epsg = 32612
    src_epsg = 4326
    dst_epsg: float = Projector.estimate_utm_epsg(
        **location
    )  # Estimate UTM EPSG code from lat and lon position

    # Test Projector.estimate_utm_epsg
    assert dst_epsg == location_UTM_epsg

    projecter = Projector(src_epsg=src_epsg, dst_epsg=dst_epsg)
    test_polygon_4326: Polygon = read_geojson_polygon(
        testgeoms.test_polygon
    )  # Creat Polygon object from geoJSON
    test_polygon_4326_to_UTM: Polygon = projecter.forward(
        test_polygon_4326
    )  # Project from lat/lon to UTM
    test_polygon_4326_to_UTM_to_4326: Polygon = projecter.backward(
        test_polygon_4326_to_UTM
    )  # Project from UTM to lat/lon

    # Generate testing objects. Note that projection operations cannot maintain floating point precision
    # above that of the input points which warrants rounding down.

    test_a = test_polygon_4326.bounds
    test_b = test_polygon_4326_to_UTM_to_4326.bounds

    # Test Projector.forward and Projector.backward
    assert_array_almost_equal(
        test_a,
        test_b,
        decimal=5,
        err_msg="\nTest polygon and rectified polygon are not aligned\n",
    )


def test_web_mercator_funcs() -> None:
    """Test web mercator functionality"""

    test_polygon_4326: Polygon = read_geojson_polygon(testgeoms.test_polygon)
    utm_epsg, test_polygon_4326_to_UTM = Projector.web_mercator_to_utm(
        test_polygon_4326
    )
    test_polygon_4326_to_UTM_to_4326 = Projector.to_web_mercator(
        test_polygon_4326_to_UTM, utm_epsg
    )

    # Generate testing objects. Note that projection operations cannot maintain floating point precision
    # above that of the input points which warrants rounding down.
    test_a = test_polygon_4326.bounds
    test_b = test_polygon_4326_to_UTM_to_4326.bounds

    # Test Projector.forward and Projector.backward
    assert_array_almost_equal(
        test_a,
        test_b,
        decimal=5,
        err_msg="\nTest polygon and rectified polygon are not aligned\n",
    )


def test_write_quickfire() -> None:
    """Test io.write_quicfire()"""

    validation_data_path = path.join(path.dirname(__file__), SIMULATION_PATH)
    with open(validation_data_path, "r") as file:
        validation_data = json.load(file)
    pattern = dt.pattern.Pattern.from_dict(
        validation_data["ring_pattern"], epsg=validation_data["epsg"]
    )
    lower_left = validation_data["lower_left"]
    times = pattern.times
    geometries = pattern.geometry
    elapsed_time = pattern.elapsed_time

    # Translate geometries from the firing technique t
    trans_geoms = []
    for geom in geometries:
        trans_geoms.append(affinity.translate(
            geom, -lower_left[0], -lower_left[1]))
    geometries = trans_geoms

    # Generate quicfire output
    quicfire_output = write_quicfire(
        geometry=geometries, times=times, elapsed_time=elapsed_time, resolution=1
    )
    test_quicfire_path = path.join(path.dirname(__file__), QF_VALIDATION_DATA)

    with open(test_quicfire_path, "r") as test_quicfire_output:
        # Truncate for speed
        test_a = (
            "\n".join(test_quicfire_output.readlines())
            .replace("\n\n", "\n")
            .split("/")[1]
            .strip("\n")
            .split(" ")[:20]
        )
        test_b = (
            quicfire_output.replace("\n\n", "\n")
            .split("/")[1]
            .strip("\n")
            .split(" ")[:20]
        )
    assert test_a == test_b
