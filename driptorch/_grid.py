# Core imports
from __future__ import annotations

# Internal imports
from .io import Projector

# External imports
from shapely.geometry import Polygon, MultiPoint, MultiLineString
import numpy as np
import gcsfs
import zarr
from scipy.interpolate import griddata
from skimage.measure import find_contours


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
            self.data.shape[0] * self.transform.res_y,
            self.transform.upper_left_x +
            self.data.shape[1] * self.transform.res_x,
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

        # Need to flip the y axis to get the correct orientation
        #points[:, 1] = points[:, 1][::-1]

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

        # Reproject the points
        points = self.to_cartesian()
        points = projector.forward(MultiPoint(points))
        points = np.array([[p.x, p.y] for p in points])

        x = np.arange(dst_bounds.west, dst_bounds.east + dst_res, dst_res)
        y = np.arange(dst_bounds.north, dst_bounds.south + dst_res, -dst_res)
        xx, yy = np.meshgrid(x, y)

        data = griddata(points, self.data.flatten(), (xx, yy), method='linear')

        new_transform = Transform(
            dst_bounds.west, dst_bounds.south, dst_res, -dst_res)

        return Grid(data, new_transform, dst_epsg)

    def get_contours(self, levels: list) -> list[MultiLineString]:
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

        # Loop over the levels and extract contours
        contours = []
        for level in levels:
            isoline = find_contours(self.data, level)

            # The columns vectors in the 2xn array need to be flipped for (x,y), artifact
            # from the skimage find_contours function.
            # Also, we need to reflect along the y axis before translating to geo position.
            # Also, this is a great example of how NOT to use list comprehensions.
            contours.append(MultiLineString(
                [np.array([[1, 0], [0, -1]]).dot(np.fliplr(i).T).T +
                 [bounds.west, bounds.south] for i in isoline]))

        return contours


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

    # Verification
    # ------------
    # import matplotlib.pyplot as plt

    # plt.imshow(utm_dem_unit.data, extent=(utm_dem_unit.bounds.west,
    #            utm_dem_unit.bounds.east, utm_dem_unit.bounds.south, utm_dem_unit.bounds.north))
    # plt.plot(*polygon.exterior.xy)
    # plt.plot(*utm_bounds_polygon.exterior.xy)
    # plt.show()

    # plt.imshow(utm_dem_unit.data)
    # plt.show()

    # contours = utm_dem_unit.get_contours([1000, 1200, 1250, 1550])

    # for p in contours:
    #     for l in p:
    #         plt.plot(*l.xy)
    # plt.plot(*polygon.exterior.xy)
    # plt.show()
