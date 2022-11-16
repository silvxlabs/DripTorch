import numpy as np
import heapq
import matplotlib.pyplot as plt

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
        self._world2ind = transform.copy()
        self._ind2world = np.linalg.inv(transform)

    def get_Index(self,index:int) -> np.ndarray:
        # Return the 2d index given the 1d index
        return np.array([index//self.cols,index%self.cols]).astype(int)
    
    def get_Neighbors(self,index:int | list[int]) -> list:
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
        if isinstance(index,int):
            index = [index]

        neighbor_set = []
        for ind in index:
            matcoords = np.array(self.get_Index(ind)) # get 2d coords
            neighborhood = self.neighbor_Kernel + ind
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
            neighbor_set.append(neighbors_dists)

        return neighbor_set

    def __getitem__(self,key):
        return self.raster[key]
    
    def __setitem__(self,key,item):
        self.raster[key] = item

    def world2ind(location,round=True) -> np.ndarray:
        # Map from spatial coordinates to raster coords
        if self._world2ind:
            point = [location[0],location[1],1]
            index = self._world2ind@point
            index = index[:-1]
            if round:
                index = index.astype(int)
            return index
        else:
            return None 

    def ind2world(index)-> np.ndarray:
        # Map from raster coordinates to world coords
        if self._ind2world:
            point = [index[0],index[1],1]
            world = self._ind2world@point
            return world[:-1]
        else:
            return None
    
class SourceRaster(Raster):
    def __init__(self,raster:np.ndarray):
        super().__init__(raster=raster)

    @property
    def locations() -> np.ndarray:
        return self.inds[self.raster]
    
