#External Imports

import numpy as np
import heapq
import matplotlib.pyplot as plt
from shapely.geometry import LineString
import itertools
import sys
import pdb


# Local Imports

from ._grid import Transform,Bounds,CostDistanceDEM,SourceRasterDEM


# ref: https://pro.arcgis.com/en/pro-app/latest/tool-reference/spatial-analyst/understanding-cost-distance-analysis.htm  # noqa: E501
# ref: https://pro.arcgis.com/en/pro-app/latest/tool-reference/spatial-analyst/how-the-cost-distance-tools-work.htm  # noqa: E501
# ref: https://en.wikipedia.org/wiki/Dijkstra%27s_algorithm

class Heap:
    def __init__(self,x = None):
        if x:
            self.list = x
        else:
            self.list = []
        heapq.heapify(self.list)

    def push(self,x):
        if isinstance(x,list):
            [heapq.heappush(self.list,item) for item in x]
        else:
            heapq.heappush(self.list,x)
    
    def pop(self):
        return heapq.heappop(self.list)



class CostDistance:
    def __init__(self,start_path:np.ndarray, elevation_raster:CostDistanceDEM, raster_offset = (7690,7764)):
        self.elevation_raster = elevation_raster
        self.start_path = start_path
        self.cost_raster,self.source_raster = self.elevation_raster.generate_source_cost(start_path)
        source_neighbors = [self.source_raster.get_neighbors(index) for index in self.source_raster.locations]
        init_costs = self._compute_costs(source_neighbors)
        self.PQ = Heap(init_costs)
        self.raster_offset = np.array(raster_offset)
    
    def _compute_costs(self,edge_set:list) -> list:
        computed_costs = []
        for edges in edge_set:
            for edge in edges:
                start,stop,distance = edge
                dz = self.elevation_raster[start] - self.elevation_raster[stop]
                move_length = np.sqrt(distance**2 + dz**2)
                cost = self.cost_raster[start] + move_length
                computed_costs.append((cost,stop))
        return computed_costs
    
    def iterate(self,num_igniters,igniter_depth,heat_depth) -> np.ndarray:
        # Generate cost surface
        while len(self.PQ.list) > 0:
            cost,loc = self.PQ.pop()
            if cost > self.cost_raster[loc]:
                continue
            else:
                self.cost_raster[loc] = cost
                neighbors = [self.cost_raster.get_neighbors(loc)]
                neighbor_costs = self._compute_costs(neighbors)
                self.PQ.push(neighbor_costs)
        

        levels = [igniter_depth]
        while levels[-1] < np.max(self.cost_raster.data):
            for i in range(num_igniters - 1):
                levels.append(levels[-1] + igniter_depth)
            levels.append(levels[-1] + heat_depth)

        #TODO
        # Incorporate sub-raster offset into calcs
        contours = self.cost_raster.get_contours(levels)
       
        heats = []
        heat_set = []
        current_heat = 0


        for (i,contour) in enumerate(contours):
            if i//num_igniters > current_heat:
                current_heat = i//num_igniters
                heats.append(heat_set)
                heat_set = []

            heat_set.append(
                contour
            )

        
        # Convert 
        
        for i, heat in enumerate(heats):
            for j,path in enumerate(heat):
                path = np.array(path) + self.raster_offset
                path_world = LineString([self.elevation_raster.ind2world(p) for p in path.tolist()])
                index = i*len(heat) + j 
                raw_paths["geometry"][index] = path_world
                
        return raw_paths,cost_surface
