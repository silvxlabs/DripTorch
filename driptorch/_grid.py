# Core imports
from __future__ import annotations

# Internal imports
# from .io import Projector

# External imports
from shapely.geometry import Polygon, MultiPoint, MultiLineString,LineString
import numpy as np
import gcsfs
import zarr
from scipy.interpolate import griddata
from scipy.ndimage import gaussian_filter
from skimage.measure import find_contours
import pdb

class Transform:
    """Helper class to store transform information for raster data"""

    def __init__(self, upper_left_x: float, upper_left_y: float, res_x: float, res_y: float):
        """Constructor

        Parameters
        ----------
        upper_left_x : float
            Upper left x coordinate
        upper_left_y : float
            Upper left y coordinate
        res_x : float
            Resolution in x direction
        res_y : float
            Resolution in y direction
        """

        # Store instance variables
        self.upper_left_x = upper_left_x
        self.upper_left_y = upper_left_y
        self.res_x = res_x
        self.res_y = res_y

        self.build_map_matrix()

    def build_map_matrix(self):
        
        self.ind2worldmatrix = np.array([
            [self.res_x,0,self.upper_left_x],
            [0,-self.res_y,self.upper_left_y],
            [0,0,1]
        ])
        
        self.world2indmatrix = np.linalg.inv(self.ind2worldmatrix)

    def world2ind(self,locs:np.ndarray) -> np.ndarray:
        if len(locs.shape) < 2:
            locs = locs.reshape(1,-1)
        locs = np.hstack((locs,np.ones((locs.shape[0],1))))
        indicies = locs@self.world2indmatrix.T
        return indicies.astype(int)

    def ind2world(self,locs:np.ndarray) -> np.ndarray:
        if len(locs.shape) < 2:
            locs = locs.reshape(1,-1)
        locs = np.hstack((locs,np.ones((locs.shape[0],1))))
        worldpoints = locs@self.ind2worldmatrix.T
        return worldpoints[:,:-1]

    @classmethod
    def from_map_matrix(cls,map:np.ndarray):
        # Take a world to ind mapping matrix and solve for the transform parameters
        
        res_x = np.abs(map[0][0])
        res_y = np.abs(map[1][1])

        ul_x = np.abs(map[0][-1])
        ul_y = np.abs(map[1][-1])
        
        
        return Transform(ul_x,ul_y,res_x,res_y)

        

    @classmethod
    def from_geo_transform(cls, geo_transform: list) -> Transform:
        """Initialize a Transform object from a GDAL-style GeoTransform

        Parameters
        ----------
        geo_transform : list
            GDAL-style GeoTransform

        Returns
        -------
        Transform
            Transform object
        """

        return cls(geo_transform[2], geo_transform[5], geo_transform[0], geo_transform[4])

    def __repr__(self):
        return f'Transform(upper_left_x={self.upper_left_x}, upper_left_y={self.upper_left_y}, res_x={self.res_x}, res_y={self.res_y})'


class Bounds:
    """Helper class for storing raster bounds"""

    def __init__(self, west: float, south: float, east: float, north: float):
        """Constructor

        Parameters
        ----------
        west : float
            Western extent
        south : float
            Southern extent
        east : float
            Eastern extent
        north : float
            Northern extent
        """

        # Store instance variables
        self.west = west
        self.south = south
        self.east = east
        self.north = north

    @classmethod
    def from_polygon(cls, polygon: Polygon) -> Bounds:
        """Create a Bounds object from a shapely Polygon

        Parameters
        ----------
        polygon : Polygon
            Shapely polygon

        Returns
        -------
        Bounds
            Bounds object
        """

        bounds = polygon.bounds
        return cls(*bounds)

    def to_polygon(self) -> Polygon:
        """Convert the bounds to a shapely Polygon

        Returns
        -------
        Polygon
            Shapely polygon
        """

        return Polygon([
            (self.west, self.south),
            (self.east, self.south),
            (self.east, self.north),
            (self.west, self.north)
        ])

    def __repr__(self):
        return f'Bounds({self.west}, {self.south}, {self.east}, {self.north})'


class Grid:
    """Class for storing raster data"""

    def __init__(self, data: np.ndarray | zarr.Array, transform: Transform, epsg: int):
        """Constructor

        Parameters
        ----------
        data : np.ndarray | zarr.Array
            Grid data array
        transform : Transform
            Geographic transform
        epsg : int
            EPSG projection code
        """

        # Store instance variables
        self.data = data
        self.transform = transform
        self.epsg = epsg
        self.row,self.cols = self.data.shape

    @property
    def bounds(self) -> Bounds:
        """Get the bounds of the grid

        Returns
        -------
        Bounds
            Bounds object
        """

        return Bounds(
            self.transform.upper_left_x,
            self.transform.upper_left_y -
            self.rows * self.transform.res_y,
            self.transform.upper_left_x +
            self.cols * self.transform.res_x,
            self.transform.upper_left_y
        )

    def extract_by_bounds(self, bounds: Bounds, padding: int = 0) -> Grid:
        """Extract a sub array by provided bounds object

        Parameters
        ----------
        bounds : Bounds
            Bounds object
        padding : int, optional
            Optional padding in units of cells (not metric), defaults to 0.

        Returns
        -------
        Grid
            Extracted sub grid
        """

        # Snap the bounds to the grid in matrix space
        qx1 = int((bounds.west - self.transform.upper_left_x) /
                  self.transform.res_x - 0.5) - padding
        qy1 = int((bounds.north - self.transform.upper_left_y) /
                  self.transform.res_y - 0.5) - padding
        qx2 = int((bounds.east - self.transform.upper_left_x) /
                  self.transform.res_x + 0.5) + padding
        qy2 = int((bounds.south - self.transform.upper_left_y) /
                  self.transform.res_y + 0.5) + padding

        # Create a new transform for the returned Grid
        new_transform = Transform(
            self.transform.upper_left_x + qx1 * self.transform.res_x,
            self.transform.upper_left_y + qy2 * self.transform.res_y,
            self.transform.res_x,
            self.transform.res_y)

        # Return a new Grid instance with the extracted subarray
        return Grid(self.data[qy1:qy2, qx1:qx2], new_transform, self.epsg)

    def to_cartesian(self) -> np.ndarray:
        """Convert grid space to cartesian space

        Returns
        -------
        np.ndarray
            2xn array of cartesian coordinates
        """

        # Construct a mesh grid of across the grid bounds
        x = np.arange(self.bounds.west, self.bounds.east, self.transform.res_x)
        y = np.arange(self.bounds.south, self.bounds.north,
                      self.transform.res_y)
        xx, yy = np.meshgrid(x, y)

        # Stack the axis arrays into a 2xn array and move points to center of grid cells
        points = np.hstack((xx.reshape(-1, 1), yy.reshape(-1, 1)))
        points[:, 0] += self.transform.res_x / 2
        points[:, 1] += self.transform.res_y / 2

        return points

    def reproject(self, dst_epsg: int, dst_bounds: Bounds, dst_res: int = 30) -> Grid:
        """Reproject the grid to a new projection

        Parameters
        ----------
        src_epsg : int
            Source EPSG projection code
        dst_epsg : int
            Destination EPSG projection code

        Returns
        -------
        Grid
            Reprojected grid
        """

        projector = Projector(self.epsg, dst_epsg)

        # Construct cartesian coordinates for grid and project them to the destination projection
        points = self.to_cartesian()
        points = projector.forward(MultiPoint(points))
        points = np.array([[p.x, p.y] for p in points])

        # Create a new grid space for the interpolated reprojected grid ata
        x = np.arange(dst_bounds.west, dst_bounds.east + dst_res, dst_res)
        y = np.arange(dst_bounds.north, dst_bounds.south + dst_res, -dst_res)
        xx, yy = np.meshgrid(x, y)

        # Interpolated the reprojected points to the new grid space
        data = griddata(points, self.data.flatten(), (xx, yy), method='linear')

        # Build the new grid transform
        new_transform = Transform(
            dst_bounds.west, dst_bounds.south, dst_res, -dst_res)

        return Grid(data, new_transform, dst_epsg)

    def get_contours(self, levels: list,sigma=None) -> list[MultiLineString]:
        """Get contours from the grid. The returned contours are in the geographic/projected
        coordinates, not in matrix space.

        Parameters
        ----------
        levels : list
            List of contour levels to extract

        Returns
        -------
        list[MultiLineString]
            List of contours
        """
        bounds = self.bounds

        if len(self.data.shape) < 2:
            image = self.reshape()
        else:
            image = self.data

        # Loop over the levels and extract contours
        contours = []
        for level in levels:

            try:
            
                #Go from image coords to matrix coords
                isoline = list(map(
                    np.fliplr,find_contours(image[:,::-1], level)
                ))
                
                lines = []
                for line in isoline:
                    line = np.array(line)
                    line[:,0] = image.shape[1] - line[:,0]
                    #line = (np.array([[1, 0], [0, -1]])@line.T).T
                    lines.append(line)
                    
                
             
              
                # Map into world coordinates
                isoline_world = list(map(
                    self.transform.ind2world, lines
                ))
                
                
                # Cast as MultiLineString 
                contours.append(
                    MultiLineString([line for line in isoline_world])
                )
            except ValueError:
                pass

        return contours


    def smooth(self,sigma):
        self.data = self.reshape()
        self.data = gaussian_filter(self.data,sigma=sigma)
        self.data = self.data.flatten()

class AlbersConusDEM(Grid):
    """Child grid class for the Albers CONUS DEM"""

    def __init__(self):
        """Constructor
        """

        # Connect to the Albers DEM on GCS
        gcs = gcsfs.GCSFileSystem(token='anon')
        gcs_map = gcs.get_mapper(
            'driptorch-silvxlabs/dem/USGS_3DEP_30m_CONUS.zarr')
        data = zarr.open(gcs_map)

        # Pull the transform from the zarr attributes
        transform = Transform.from_geo_transform(data.attrs['transform'])

        # Call the parent constructor
        super().__init__(data, transform, 5070)



class CostDistanceDEM(Grid):
    def __init__(self, data: np.ndarray | zarr.Array, transform: Transform, epsg: int):
        super().__init__(data,transform,epsg)
        self.rows,self.cols = self.data.shape 
        self.data = self.data.flatten()
        
        self.inds = np.arange(self.data.shape[0])

        self.neighbor_kernel = [
            -self.cols-1, -self.cols, -self.cols+1, -1, 1, self.cols-1, self.cols, self.cols+1
            ]

        self.neighbor_kernel_dists = [2**.5, 1, 2**.5, 1, 1, 2**.5, 1, 2**.5]

    def build_map(self):
        translation = np.array([
            [-1,0,self.transform.upper_left_x],
            [0,-1,self.transform.upper_left_y]
        ])
        scale = np.array([
            [1/self.transform.res_x,0],
            [0,1/self.transform.res_y]
        ])
        self.world2ind = scale@translation


    def reshape(self) -> np.ndarray:
        return self.data.reshape((self.rows,self.cols))


    def get_index(self,index:int) -> np.ndarray:
        
        return np.array([index//self.cols,index%self.cols]).astype(int)


    def get_neighbors(self,index:int) -> list:
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


        matcoords = np.array(self.get_index(index)) # get 2d coords
        neighborhood = np.array(self.neighbor_kernel.copy()) + index
        distances = np.array(self.neighbor_kernel_dists.copy())
        
        # check if we are at the boundary
        if matcoords[0] <= 0: # If we are at the first row
            remove = [0,1,2]
            neighborhood[remove] = -999
            distances[remove] = -999
        if matcoords[0] >= self.rows-1: # If we are at the last row
            remove = [5,6,7]
            neighborhood[remove] = -999
            distances[remove] = -999
        if matcoords[1] <= self.cols-1: # If we are at the first column
            remove = [0,3,5]
            neighborhood[remove] = -999
            distances[remove] = -999
        if matcoords[1] >= self.cols-1: # If we are at the last column
            remove = [2,4,7]
            neighborhood[remove] = -999
            distances[remove] = -999

        to_keep = neighborhood != -999
        neighborhood = neighborhood[to_keep].tolist()
        distances = distances[to_keep].tolist()
       
        neighbors_distances = list(zip([index]*len(neighborhood),neighborhood,distances))

        return neighbors_distances
    
    def generate_source_cost(self,start_line:np.ndarray):
        """Generate a source array given a starting path, where the 
        source cells are the edge row closest to the start path
        Args:
            path (list): _description_
        Returns:
            np.ndarray: _description_
        """
        
        start,stop = start_line[0,:],start_line[1,:]
        start_mat,stop_mat = np.squeeze(self.transform.world2ind(start)),np.squeeze(self.transform.world2ind(stop))
        dpos = np.squeeze(np.abs(start_mat - stop_mat))[:2]
        #perp_axis = np.argmin(dpos)
        travel_axis = np.argmax(dpos)
        
       
        start_row = start_mat[travel_axis]
        if start_row < self.rows//2:
            source_slice = np.s_[0,:]
        else:
            source_slice = np.s_[-1,:]

        source_array = np.zeros((self.rows,self.cols)).astype(bool)
        source_array[source_slice] = True

        cost_array = np.ones((self.rows,self.cols))
        cost_array *= np.inf
        cost_array[source_slice] = 0

        cost_raster = CostDistanceDEM(data=cost_array,transform=self.transform,epsg=self.epsg)
        source_raster = SourceRasterDEM(data=source_array,transform=self.transform,epsg=self.epsg)
        return cost_raster,source_raster


    def __getitem__(self,key):
        return self.data[key]
    
    def __setitem__(self,key,item):
        self.data[key] = item
    
    @classmethod
    def from_grid(cls,grid:Grid) -> CostDistanceDEM:
        """Return CostDistanceDEM from Grid Object

        Args:
            grid (Grid): Instantiated Grid Instance
        Returns:
            CostDistanceDEM: generated CostDistanceDEM object
        """
        return cls(grid.data,grid.transform,grid.epsg)

class SourceRasterDEM(CostDistanceDEM):
    def __init__(self, data: np.ndarray | zarr.Array, transform: Transform, epsg: int):
        super().__init__(data, transform, epsg)

    @property
    def locations(self) -> np.ndarray:
        """Return the 1d indicies of source locations

        Returns:
            np.ndarray: _description_
        """
        return self.inds[self.data]








def fetch_dem(polygon: Polygon, epsg: int, res: int = 1) -> Grid:
    """Returns a DEM for the bounds of the provided polygon

    Parameters
    ----------
    polygon : Polygon
        Polygon to fetch the DEM for
    epsg : int
        EPSG code to reproject the DEM
    res : int, optional
        Spatial resolution of the returned DEM, by default 1

    Returns
    -------
    Grid
        Elevation grid
    """

    projector = Projector(epsg, 5070)

    # Get the bounds of the input polygon then construct a polygon from the bounds
    # and reproject to Albers
    src_bounds = Bounds.from_polygon(polygon)
    src_bounds_polygon = src_bounds.to_polygon()
    albers_bounds_polygon = projector.forward(src_bounds_polygon)

    # Now we get the bounds of the reprojected source polygon bounds to ensure
    # we cover the entire area for the interpolated reprojection
    albers_bounds = Bounds.from_polygon(albers_bounds_polygon)

    # Instantiate the Albers CONUS DEM and extract the subarray by the bounds
    albers_dem_conus = AlbersConusDEM()
    albers_sub_dem = albers_dem_conus.extract_by_bounds(
        albers_bounds, padding=0)

    # Return the reprojected DEM in the desired projection system
    return albers_sub_dem.reproject(epsg, src_bounds, dst_res=res)
