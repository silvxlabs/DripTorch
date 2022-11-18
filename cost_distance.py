import numpy as np
import heapq
import matplotlib.pyplot as plt
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
        if transform:
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


class ElevationRaster(Raster):
    def __init__(self,raster:np.ndarray):
        super().__init__(raster=raster)

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
        source_array = np.zeros_like(self.raster).astype(bool)
        source_array[source_slice] = True

        cost_raster = np.ones_like(self.raster)
        cost_raster *= np.inf
        cost_raster[source_slice] = 0

        cost_raster = Raster(cost_raster)
        source_raster = SourceRaster(raster)

        return cost_raster,source_raster

    
class SourceRaster(Raster):
    def __init__(self,raster:np.ndarray):
        super().__init__(raster=raster)

    @property
    def locations(self) -> np.ndarray:
        return self.inds[self.raster]


class CostDistance:
    def __init__(self,raw_paths:dict,elevation_raster:np.ndarray):

        self.elevation_raster = ElevationRaster(elev_raster)
        self.raw_paths = raw_paths
        self.cost_raster,self.source_raster = self.elevation_raster.generate_source_cost(self.raw_paths["geometry"][0])
       
     
        source_neighbors = [self.source_raster.get_Neighbors(index) for index in  self.source_raster.locations]
        init_costs = self._compute_costs(source_neighbors)
        self.PQ = Heap(init_costs)
    
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

        contours = plt.contour(cost_surface, colors='w', lw='0.25', levels=levels)
        
        paths = []
        for i,p in enumerate(contours.collections[0].get_paths()):
            if i == 0:
                current_heat = i//num_igniters
                heat_set = []
        
            heat = i//num_igniters
            if heat > current_heat:
                current_heat = heat
                paths.append(heat_set)
                heat_set = []
            
            else:
                heat_set.append(
                    p.vertices
                )
                
        return paths,cost_surface
            
        

if __name__ == "__main__":
    import matplotlib.pyplot as plt

    elevs = np.load("/Users/franklyndunbar/Project/testarea.npy")
    source_raster = np.zeros_like(elevs).astype(bool)
    cost_raster = np.ones_like(elevs)
    cost_raster *= np.inf
    source_slice = np.s_[0,:]

    source_raster[source_slice] = True
    cost_raster[source_raster==True] =  0

    elev_raster = Raster(elevs)
    cost_raster = Raster(cost_raster)
    source_raster = SourceRaster(source_raster)

    CD = CostDistance(source_raster,cost_raster,elev_raster)
    paths,test = CD.iterate(3,5,12)
    np.save("cost_surface",test)
    plt.rcParams["figure.figsize"] = (160/8,90/8)
    plt.imshow(test.reshape(cost_raster.rows,cost_raster.cols))
    for heat in paths:
        for igniter in heat:
            plt.plot(heat[:,0],heat[:,1])
    
    plt.colorbar()
    plt.show()