# Core imports
from __future__ import annotations

# Internal imports
from .io import Projector

# External imports
import gcsfs
import numpy as np
from scipy.interpolate import griddata
from scipy.ndimage import gaussian_filter
from skimage import draw
from skimage.measure import find_contours
from shapely.geometry import Polygon, MultiPoint, LineString, MultiLineString
import zarr


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

        self.affine = np.array([
            [self.res_x, 0, self.upper_left_x],
            [0, self.res_y, self.upper_left_y],
            [0, 0, 1]
        ])

        self.affine_inv = np.linalg.inv(self.affine)

    def get_matrix_indices(self, coords: np.ndarray) -> np.ndarray:
        """Converts world coordinates to matrix coordinates

        Parameters
        ----------
        coords : np.ndarray
            Coordinate array

        Returns
        -------
        np.ndarray
            Matrix coordinates
        """

        # Handle single coordinate case
        if len(coords.shape) < 2:
            coords = coords.reshape(1, -1)

        # Add homogeneous coordinate and compute coordinates
        coords = np.hstack((coords, np.ones((coords.shape[0], 1))))
        indices = self.affine_inv.dot(coords.T).T

        # Strip homogeneous coordinate and return
        return indices[:, :-1].astype(int)

    def get_world_coordinates(self, indices: np.ndarray) -> np.ndarray:
        """Convert matrix indices to world coordinates

        Parameters
        ----------
        indices : np.ndarray
            Index array

        Returns
        -------
        np.ndarray
            World coordinates
        """

        # Handle single index case
        if len(indices.shape) < 2:
            indices = indices.reshape(1, -1)

        # Add homogeneous coordinate and compute indices
        indices = np.hstack((indices, np.ones((indices.shape[0], 1))))
        coords = self.affine.dot(indices.T).T

        # Strip homogeneous coordinate and return
        return coords[:, :-1]

    @classmethod
    def from_affine(cls, affine_matrix: np.ndarray) -> Transform:
        """Create a Transform object from an affine transformation matrix

        Parameters
        ----------
        affine_matrix : np.ndarray
            Affine transformation matrix

        Returns
        -------
        Transform
            New Transform object
        """

        res_x = affine_matrix[0, 0]
        res_y = affine_matrix[1, 1]
        ul_x = affine_matrix[0, 2]
        ul_y = affine_matrix[1, 2]

        return Transform(ul_x, ul_y, res_x, res_y)

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
    """Class for storing and manipulating raster data"""

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
        self.rows, self.cols = self.data.shape[:2]

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

    def copy(self) -> Grid:
        """Copy the grid

        Returns
        -------
        Grid
            Copied grid
        """

        return Grid(self.data.copy(), self.transform, self.epsg)

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
        y = np.arange(dst_bounds.north, dst_bounds.south - dst_res, -dst_res)
        xx, yy = np.meshgrid(x, y)

        # Interpolated the reprojected points to the new grid space
        data = griddata(points, self.data.flatten(), (xx, yy), method='linear')

        # Build the new grid transform
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
            # Also, we need to scale by the resolution defined in the transform.
            # Also, this is a great example of how NOT to use list comprehensions.
            contours.append(MultiLineString(
                [(np.fliplr(i * np.array([self.transform.res_y, self.transform.res_x])).T).T +
                 [bounds.west, bounds.south] for i in isoline]))

        return contours

    def pad(self, n: int, value: float | int | None = None):
        """Add or subtract padding of `n` cells to the grid. If `n` is positive,
        you can optionally specify a `value` to pad with.

        Parameters
        ----------
        n : int
            Number of cells to add to the boundary
        value : float | int, optional
            Fill value for the padded cells, by default 0.0
        """

        # Check if we're adding or subtracting the padding
        if n > 0:
            padded_data = np.pad(self.data, (n, n), constant_values=value)
        elif n < 0:
            padded_data = self.data[-n:n, -n:n]

        # Recompute the transform
        new_transform = Transform(
            self.transform.upper_left_x - n * self.transform.res_x,
            self.transform.upper_left_y + n * self.transform.res_y,
            self.transform.res_x,
            self.transform.res_y
        )

        return Grid(padded_data, new_transform, self.epsg)

    @classmethod
    def like(cls, grid: Grid, fill_value: float | int = 0) -> Grid:
        """Create a new grid like an existing grid and fill with a constant value

        Parameters
        ----------
        grid : Grid
            Grid shape, transform and projection to copy
        fill_value : float | int, optional
            Value to fill the grid with, by default 0

        Returns
        -------
        Grid
            New grid
        """

        data = np.zeros_like(grid.data)

        if fill_value != 0:
            data[...] = fill_value

        return cls(data, grid.transform, grid.epsg)

    def draw_line(self, line: LineString, fill_value: float | int = 1) -> None:
        """Rasterize a shapely LineString object

        Parameters
        ----------
        line : LineString
            Line string to rasterize
        fill_value : float | int, optional
            Value to assign to cells representing the line, by default 1
        """

        # Get the coordinate of the shapely LineString object
        x, y = line.coords.xy

        # Stack coords into a 2xn coordinate array and convert to matrix indices
        geo_coords = np.array([x, y]).T
        matrix_coords = self.transform.get_matrix_indices(geo_coords)

        # Rasterize each segment in the line string
        for i in range(0, matrix_coords.shape[0] - 1):
            rr, cc = draw.line(
                matrix_coords[i, 1], matrix_coords[i, 0], matrix_coords[i + 1, 1], matrix_coords[i + 1, 0])
            self.data[rr, cc] = fill_value

    def smooth(self, sigma: int):
        """Apply a Gaussian filter to the grid

        Parameters
        ----------
        sigma : int
            Standard deviation of the Gaussian kernel
        """

        self.data = gaussian_filter(self.data, sigma=sigma)


class AlbersConusDEM(Grid):
    """Child grid class for the Albers CONUS DEM"""

    def __init__(self):
        """Constructor"""

        # Connect to the Albers DEM on GCS
        gcs = gcsfs.GCSFileSystem(token='anon')
        gcs_map = gcs.get_mapper(
            'driptorch-silvxlabs/dem/USGS_3DEP_30m_CONUS.zarr')
        data = zarr.open(gcs_map)

        # Pull the transform from the zarr attributes
        transform = Transform.from_geo_transform(data.attrs['transform'])

        # Call the parent constructor
        super().__init__(data, transform, 5070)
