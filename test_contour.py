
# External Imports

import numpy as np 
import matplotlib.pyplot as plt
from scipy.stats import norm
import shapely
from shapely.geometry import Polygon,Point

# Core Imports
import json
import os.path as path
import sys
from collections import namedtuple

# Internal Imports
sys.path.append("/driptorch")
import driptorch as dt
from driptorch.firing import flank
from driptorch.contour import *
# Define burn unit spatial data in GeoJSON format
elevs = np.load("/Users/franklyndunbar/Project/testarea.npy")
transform =  np.load("/Users/franklyndunbar/Project/bluemountain_dem_transform.npy")

blue_mountain = [ [ -114.115414416057106, 46.84141805647527 ], 
[ -114.115414291632106, 46.841120501959843 ], [ -114.115029536394999, 46.840770983423162 ], [ -114.114665457279102, 46.840548989245221 ], 
[ -114.114413512744093, 46.840076418364873 ], [ -114.114525405809005, 46.839461779184177 ], [ -114.114333139108197, 46.839058605593813 ], 
[ -114.113953012275601, 46.838563152635771 ], [ -114.113451259100998, 46.837883698065788 ], [ -114.113224837669506, 46.837587544981723 ], 
[ -114.112789079409595, 46.836901298964847 ], [ -114.112930132494895, 46.836593931018783 ], [ -114.115362037381402, 46.835906544594543 ], 
[ -114.115155840059799, 46.835699418591219 ], [ -114.114651512340302, 46.835676739527457 ], [ -114.113836748826202, 46.835695352398247 ], 
[ -114.113174153126593, 46.835779624664482 ], [ -114.112181587364802, 46.835899281750358 ], [ -114.111299220479907, 46.83588420728352 ], 
[ -114.110869729217498, 46.835757931029612 ], [ -114.110161683708398, 46.835556727734392 ], [ -114.109653672339604, 46.835491082423658 ], 
[ -114.108349803286202, 46.835471042038172 ], [ -114.107654022255502, 46.835554206149077 ], [ -114.107000851808294, 46.835709468827467 ], 
[ -114.106305895096099, 46.835728357206087 ], [ -114.105282095585196, 46.835833565874623 ], [ -114.1055753992798, 46.836516386443613 ], 
[ -114.105737911069895, 46.836894711956553 ], [ -114.106538569463297, 46.837331382367509 ], [ -114.1071623129843, 46.837737434373651 ], 
[ -114.107713413292899, 46.838129136519498 ], [ -114.107982567263093, 46.838551148632902 ], [ -114.108502357207598, 46.839075937037279 ], 
[ -114.108969268362799, 46.839671473567421 ], [ -114.109297059793505, 46.840260548147413 ], [ -114.109857244406001, 46.841438219047838 ], 
[ -114.115414416057106, 46.84141805647527 ] ] 
blue_mountain = Polygon([Point(p) for p in blue_mountain])
burn_unit = dt.BurnUnit(blue_mountain, firing_direction=0)
bounds = burn_unit.bounds
firing_area = burn_unit.buffer_control_line(5)
firing_area = firing_area.buffer_downwind(20)
blackline_area = burn_unit.difference(firing_area)
dash_igniter = dt.Igniter(1,dash_length=.5)

num_igniters = 5
igniter_spacing = 5
igniter_depth = 5
heat_spacing = 10
transform_world_ind = np.linalg.inv(transform)
transform_obj = Transform.from_map_matrix(transform_world_ind)

point_crew = dt.IgnitionCrew.clone_igniter(dash_igniter, num_igniters)
technique = dt.firing.Strip(firing_area, point_crew)
raw_paths = technique._init_paths(intersect=False, paths=dt.Pattern.empty_path_dict(), spacing=igniter_spacing, depth=igniter_depth, heat_depth=heat_spacing, side='left')
start_path = np.asarray(raw_paths["geometry"][0])

elev_raster = CostDistanceDEM(data=elevs,transform=transform_obj,epsg=32611)




CD = CostDistance(start_path,elev_raster)
cost,source = CD.iterate(num_igniters,igniter_depth,heat_spacing)

