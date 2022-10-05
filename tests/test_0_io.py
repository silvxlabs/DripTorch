# External Imports
from shapely.geometry import shape
from shapely.geometry.polygon import Polygon
import numpy as np


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
    test_polygon_4326: Polygon = read_geojson_polygon(testgeoms.test_polygon)



    test_polygon_4326_to_UTM: Polygon = projecter.forward(test_polygon_4326) # Project from lat/lon to UTM
    test_polygon_4326_to_UTM_to_4326: Polygon = projecter.backward(test_polygon_4326_to_UTM) # Project from UTM to lat/lon

    # Generate testing objects. Note that projection operations cannot maintain floating point precision 
    # above that of the input points which warrants rounding down.

    test_a = [round(x,5) for x in test_polygon_4326.bounds]
    test_b = [round(x,5) for x in test_polygon_4326_to_UTM_to_4326.bounds]

    # Test Projector.forward and Projector.backward
    assert test_a == test_b
    
def test_web_mercator_funcs() -> None:

    test_polygon_4326: Polygon = read_geojson_polygon(testgeoms.test_polygon)

    utm_epsg, test_polygon_4326_to_UTM = Projector.web_mercator_to_utm(test_polygon_4326)

    test_polygon_4326_to_UTM_to_4326 = Projector.to_web_mercator(test_polygon_4326_to_UTM,utm_epsg)


    # Generate testing objects. Note that projection operations cannot maintain floating point precision 
    # above that of the input points which warrants rounding down.

    test_a = [round(x,5) for x in test_polygon_4326.bounds]
    test_b = [round(x,5) for x in test_polygon_4326_to_UTM_to_4326.bounds]

    # Test Projector.forward and Projector.backward
    assert test_a == test_b


    
