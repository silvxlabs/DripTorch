import numpy as np
import heapq
import matplotlib.pyplot as plt
from shapely.geometry import LineString
import itertools
import pdb
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
        heapq.heappush(self.list,x)
    
    def pop(self):
        return heapq.heappop(self.list)



class Raster:
    def __init__(self,raster:np.ndarray,transform:np.ndarray=None,noData:float=np.nan) -> None:
        self.rows,self.cols = raster.shape
        self.raster = raster.flatten()
        self.inds = np.arange(self.raster.shape[0])
        self.neighbor_Kernel = [-self.cols-1,-self.cols,-self.cols+1,-1,1,self.cols-1,self.cols,self.cols+1]
        
        self._world2ind = None
        self._ind2world = None
        if transform is not None:
            self._world2ind = transform.copy()
            self._ind2world = np.linalg.inv(transform)
        

    def get_Index(self,index:int) -> np.ndarray:
        # Return the 2d index given the 1d index
        return np.array([index//self.cols,index%self.cols]).astype(int)
    
    def get_Neighbors(self,index:int) -> list:
        """
        Return the 1d neighborhood indicies for the neighborhood of a given pixel and check bounds
        -------+-------+-----
        -cols-1| -cols | -cols+1
        -------+-------+-----
        -1     | 0     | +1
        -------+-------+-----
        cols-1 | cols  | cols+1
        -------+-------+-----
        + index
        """
        
      
        matcoords = np.array(self.get_Index(index)) # get 2d coords
        neighborhood = self.neighbor_Kernel + index
        # check if we are at the boundary
        if matcoords[0] <= 0: # If we are at the first row
            neighborhood[:3] = -999
        if matcoords[0] >= self.rows-1: # If we are at the last row
            neighborhood[-3:] = -999
        if matcoords[1] <= self.cols-1: # If we are at the first column
            remove = [0,3,5]
            neighborhood[remove] = -999
        if matcoords[1] >= self.cols-1: # If we are at the last column
            remove = [2,4,7]
            neighborhood[remove] = -999
        
        # remove out of bounds inds
        neighborhood = list(filter(lambda x: x != -999, neighborhood))
    
        # get 2d locs of neighborhood
        locs = [self.get_Index(x) for x in neighborhood]
    
        # get 2d distance to each point and stash that with index in the tuple
        distances = [np.linalg.norm((x-matcoords)) for x in locs]
        
        # join neighborhood indicies and their respective distances from the origin point
        neighbors_dists = list(zip([index]*len(neighborhood),neighborhood,distances))
           
        return neighbors_dists

    def __getitem__(self,key):
        return self.raster[key]
    
    def __setitem__(self,key,item):
        self.raster[key] = item

    def world2ind(self,location,round=True) -> np.ndarray:
        # Map from spatial coordinates to raster coords
        if self._world2ind is not None:
            point = [location[0],location[1],1]
            index = self._world2ind@point
            index = index[:-1]
            if round:
                index = index.astype(int)
            return index
        else:
            return None 

    def ind2world(self,index)-> np.ndarray:
        # Map from raster coordinates to world coords
        if self._ind2world is not None:
            point = [index[0],index[1],1]
            world = self._ind2world@point
            return world[:-1]
        else:
            return None


class ElevationRaster(Raster):
    def __init__(self,raster: np.ndarray, transform: np.ndarray):
        super().__init__(raster=raster,transform=transform)

    def generate_source_cost(self,path:list) -> np.ndarray:
        """Generate a source array given a starting path, where the 
        source cells are the edge row closest to the start path

        Args:
            path (list): _description_

        Returns:
            np.ndarray: _description_
        """
        
        start,stop = path[:2],path[2:]
        start_mat,stop_mat = self.world2ind(start),self.world2ind(stop)
        if self.rows - start_mat[0] > self.rows//2:
            source_slice = np.s_[-1,:]
        else:
            source_slice = np.s_[0,:]
        source_array = np.zeros((self.rows,self.cols)).astype(bool)
        source_array[source_slice] = True

        cost_raster = np.ones((self.rows,self.cols))
        cost_raster *= np.inf
        cost_raster[source_slice] = 0

        cost_raster = Raster(cost_raster)
        source_raster = SourceRaster(source_array)

        return cost_raster,source_raster

    
class SourceRaster(Raster):
    def __init__(self,raster:np.ndarray):
        super().__init__(raster=raster)

    @property
    def locations(self) -> np.ndarray:
        return self.inds[self.raster]


class CostDistance:
    def __init__(self,raw_paths:dict,elevation_raster:ElevationRaster,raster_offset = (7690,7764)):
        self.elevation_raster = elev_raster
        self.raw_paths = raw_paths
        self.cost_raster,self.source_raster = self.elevation_raster.generate_source_cost(self.raw_paths["geometry"][0].bounds)
        source_neighbors = [self.source_raster.get_Neighbors(index) for index in  self.source_raster.locations]
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
                neighbors = [self.cost_raster.get_Neighbors(loc)]
                neighbor_costs = self._compute_costs(neighbors)
                for c in neighbor_costs:
                    self.PQ.push(c)
        cost_surface = self.cost_raster.raster.reshape((self.cost_raster.rows,self.cost_raster.cols))
        levels = [igniter_depth]
        while levels[-1] < np.max(cost_surface):
            for i in range(num_igniters - 1):
                levels.append(levels[-1] + igniter_depth)
            levels.append(levels[-1] + heat_depth)
        contours = plt.contour(cost_surface,levels=levels)
       
        heats = []
        heat_set = []
        current_heat = 0

        # path_vertices = [x.get_paths() for x in contours.collections]
        # pdb.set_trace()
        # path_vertices = [x[0].vertices for x in path_vertices if len(x)>1]
        # pdb.set_trace()
        for (i,contour) in enumerate(contours.allsegs):
            path = list(itertools.chain.from_iterable(contour))
        
            
            if i//num_igniters > current_heat:
                
                current_heat = i//num_igniters
                heats.append(heat_set)
                heat_set = []
            
            heat_set.append(
                path
            )

        
        # Convert 
        
        for i, heat in enumerate(heats):
            for j,path in enumerate(heat):
                path = np.array(path) + self.raster_offset
                path_world = LineString([self.elevation_raster.ind2world(p) for p in path.tolist()])
                index = i*len(heat) + j 
                raw_paths["geometry"][index] = path_world
                
        return raw_paths,cost_surface
            
        

if __name__ == "__main__":
    
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
    point_crew = dt.IgnitionCrew.clone_igniter(dash_igniter, num_igniters)
    technique = dt.firing.Strip(firing_area, point_crew)
    raw_paths = technique.raw_paths(paths=dt.Pattern.empty_path_dict(),spacing=igniter_spacing,depth=igniter_depth,heat_depth=heat_spacing,side='left')

    elev_raster = ElevationRaster(raster=elevs,transform=transform)

    CD = CostDistance(raw_paths=raw_paths,elevation_raster=elev_raster)
    raw_paths,test = CD.iterate(num_igniters,igniter_depth,heat_spacing)

    pdb.set_trace()
    # np.save("cost_surface",test)
    # plt.rcParams["figure.figsize"] = (160/8,90/8)
    # plt.imshow(test.reshape(elev_raster.rows,elev_raster.cols))
    # for heat in raw_paths:
    #     for igniter in heat:
    #         plt.plot(heat[:,0],heat[:,1])
    
    # plt.colorbar()
    # plt.show()
 