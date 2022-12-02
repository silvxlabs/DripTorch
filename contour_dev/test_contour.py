
# External Imports

import numpy as np 
import matplotlib.pyplot as plt
from scipy.stats import norm
import shapely
from shapely.geometry import Polygon,Point,shape

# Core Imports
import sys
import json
import os.path as path


# Internal Imports
sys.path.append("/driptorch")
import driptorch as dt
from driptorch.firing import flank
from driptorch._grid import Grid,Transform

# Define burn unit spatial data in GeoJSON format
elevs = np.squeeze(np.load("/Users/franklyndunbar/Project/Silvx/bm_dem.npy"))
transform =  np.load("/Users/franklyndunbar/Project/Silvx/bm_transform.npy")
bounds = "/Users/franklyndunbar/Project/Silvx/bm_geojson.geojson"

with open(bounds,'rb') as _file:
    blue_mountain = json.load(_file)

polygon = blue_mountain["features"][0]["geometry"]
polygon["type"] = 'Polygon'
coords = np.squeeze(np.array(polygon["coordinates"]))

blue_mountain_polygon = Polygon(coords)

elev_raster = Grid(
    data=elevs,
    transform=Transform.from_map_matrix(transform),
    epsg=32611)

burn_unit = dt.BurnUnit(blue_mountain_polygon,utm_epsg=32611,firing_direction=0,dem=elev_raster)
bounds = burn_unit.bounds
firing_area = burn_unit.buffer_control_line(5)
firing_area = firing_area.buffer_downwind(20)
blackline_area = burn_unit.difference(firing_area)
dash_igniter = dt.Igniter(1,dash_length=.5)

num_igniters = 5
igniter_spacing = 5
igniter_depth = 5
heat_spacing = 10

args = {
    "spacing":igniter_spacing,
    "depth": igniter_depth,
    "heat_depth": heat_spacing,
    "side": 'right',
    "cost_raster": True,
    "sigma": 6
}

point_crew = dt.IgnitionCrew.clone_igniter(dash_igniter, num_igniters)
technique = dt.firing.StripContour(firing_area, point_crew)
pattern,cost_surface = technique.generate_pattern(**args)

plt.imshow(cost_surface.data.reshape((cost_surface.rows,cost_surface.cols)).astype(int))
plt.show()

