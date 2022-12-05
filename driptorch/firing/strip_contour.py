"""
Pattern generator for contour following strip
"""

# Internal imports
from ._base import FiringBase
from ..unit import BurnUnit
from ..personnel import IgnitionCrew
from ..pattern import Pattern, TemporalPropagator
from .._grid import Grid, Transform

# External Imports
import numpy as np
import heapq
import zarr
from shapely.geometry import LineString, MultiLineString


class StripContour(FiringBase):
    """Strip firing produces ignition paths perpendicular to the firing direction. Igniters are staggered with their heats
    and each heat alternates on which side of the unit they start.

    Parameters
    ----------
    burn_unit : BurnUnit
        Area bounding the ignition paths
    ignition_crew : IgnitionCrew
        Ignition crew assigned to the burn
    """

    def __init__(self, burn_unit: BurnUnit, ignition_crew: IgnitionCrew):

        # Check if DEM has been fetched for burn unit and fetch if not
        if burn_unit.dem is None:
            burn_unit.fetch_dem()

        # Initialize the base class
        super().__init__(burn_unit, ignition_crew)

    def generate_pattern(self, spacing: float = 0, depth: float = 0, heat_depth: float = 0, heat_delay: float = 0, cost_raster=False, **kwargs) -> Pattern:
        """Generate a flank fire ignition pattern

        Parameters
        ----------
        spacing : float, optional
            Staggering distance in meters between igniters within a heat
        depth : float, optional
            Horizontal distance in meters between igniters and heats
        heat_depth : float, optional
            Depth in meters between igniter heats. If None, heat_depth is equal to igniter depth. Defaults to None.
        heat_delay : float, optional
            Delay in seconds between igniter heats. Defaults to 0.
        side : str, optional
            Side of the firing vector to start the ignition. Defaults to 'right'. Options are 'left' or 'right'.

        Returns
        -------
        Pattern
            Spatiotemporal ignition pattern
        """
        # Extract the bounding extent of the firing area
        bbox = self._burn_unit.bounds
        x_min, y_min = bbox[:, 0].min(), bbox[:, 1].min()
        x_max, y_max = bbox[:, 0].max(), bbox[:, 1].max()

        starty, endy = y_min, y_max
        start_path = np.array([
            [x_min, starty],
            [x_min, endy]
        ])

        cost_distance = CostDistance(start_path, self._burn_unit.dem)

        paths, cost_raster = cost_distance.iterate(
            num_igniters=len(self._ignition_crew),
            igniter_depth=depth,
            heat_depth=heat_depth,
            burn_unit=self._burn_unit,
            sigma=kwargs.get("sigma", 0)
        )

        # Configure the propagator for pushing time through the paths
        propagator = TemporalPropagator(
            spacing,
            sync_end_time=kwargs.get('sync_end_time', False),
            return_trip=kwargs.get('return_trip', False),
        )

        # Compute arrival times for each coordinate in each path
        timed_paths = propagator.forward(
            paths, self._ignition_crew, heat_delay)

        # Hand the timed paths over to the Pattern class and return an instance

        pattern = Pattern.from_dict(timed_paths, self._burn_unit.utm_epsg)

        if cost_raster:
            return pattern, cost_raster
        else:
            return pattern


class CostDistanceDEM(Grid):
    def __init__(self, data: np.ndarray | zarr.Array, transform: Transform, epsg: int):
        super().__init__(data, transform, epsg)
        self.rows, self.cols = self.data.shape
        self.data = self.data.flatten()
        self.inds = np.arange(self.data.shape[0])
        self.neighbor_kernel = [
            -self.cols-1, -self.cols, -self.cols+1, -
            1, 1, self.cols-1, self.cols, self.cols+1
        ]
        self.neighbor_kernel_dists = [2**.5, 1, 2**.5, 1, 1, 2**.5, 1, 2**.5]

    def reshape(self) -> np.ndarray:
        return self.data.reshape((self.rows, self.cols))

    def get_index(self, index: int) -> np.ndarray:

        return np.array([index//self.cols, index % self.cols]).astype(int)

    def get_neighbors(self, index: int) -> list:
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

        matcoords = np.array(self.get_index(index))  # get 2d coords
        neighborhood = np.array(self.neighbor_kernel.copy()) + index
        distances = np.array(self.neighbor_kernel_dists.copy())

        # check if we are at the boundary
        if matcoords[0] <= 0:  # If we are at the first row
            remove = [0, 1, 2]
            neighborhood[remove] = -999
            distances[remove] = -999
        if matcoords[0] >= self.rows-1:  # If we are at the last row
            remove = [5, 6, 7]
            neighborhood[remove] = -999
            distances[remove] = -999
        if matcoords[1] <= self.cols-1:  # If we are at the first column
            remove = [0, 3, 5]
            neighborhood[remove] = -999
            distances[remove] = -999
        if matcoords[1] >= self.cols-1:  # If we are at the last column
            remove = [2, 4, 7]
            neighborhood[remove] = -999
            distances[remove] = -999

        to_keep = neighborhood != -999
        neighborhood = neighborhood[to_keep].tolist()
        distances = distances[to_keep].tolist()

        neighbors_distances = list(
            zip([index]*len(neighborhood), neighborhood, distances))

        return neighbors_distances

    def generate_source_cost(self, start_line: np.ndarray):
        """Generate a source array given a starting path, where the 
        source cells are the edge row closest to the start path
        Args:
            path (list): _description_
        Returns:
            np.ndarray: _description_
        """

        start, stop = start_line[0, :], start_line[1, :]
        start_mat, stop_mat = np.squeeze(self.transform.world2ind(
            start)), np.squeeze(self.transform.world2ind(stop))
        dpos = np.squeeze(np.abs(start_mat - stop_mat))[:2]
        travel_axis = np.argmax(dpos)

        start_row = start_mat[travel_axis]
        if start_row < self.rows//2:
            source_slice = np.s_[0, :]
        else:
            source_slice = np.s_[-1, :]

        source_array = np.zeros((self.rows, self.cols)).astype(bool)
        source_array[source_slice] = True

        cost_array = np.ones((self.rows, self.cols))
        cost_array *= np.inf
        cost_array[source_slice] = 0

        cost_raster = CostDistanceDEM(
            data=cost_array, transform=self.transform, epsg=self.epsg)
        source_raster = SourceRasterDEM(
            data=source_array, transform=self.transform, epsg=self.epsg)
        return cost_raster, source_raster

    def __getitem__(self, key):
        return self.data[key]

    def __setitem__(self, key, item):
        self.data[key] = item

    @classmethod
    def from_grid(cls, grid: Grid):
        """Return CostDistanceDEM from Grid Object

        Args:
            grid (Grid): Instantiated Grid Instance
        Returns:
            CostDistanceDEM: generated CostDistanceDEM object
        """

        return cls(grid.data, grid.transform, grid.epsg)


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


class Heap:
    def __init__(self, x=None):
        if x:
            self.list = x
        else:
            self.list = []
        heapq.heapify(self.list)

    def push(self, x):
        if isinstance(x, list):
            [heapq.heappush(self.list, item) for item in x]
        else:
            heapq.heappush(self.list, x)

    def pop(self):
        return heapq.heappop(self.list)


class CostDistance:
    """Computes the geodesic transform on a raster of elevations
    """

    def __init__(self, start_path: np.ndarray, elevation_raster: CostDistanceDEM | Grid):
        """Intializes the CostDistance object

        Parameters
        ----------
            start_path (np.ndarray): 
                Starting path line in world coordinates

            elevation_raster (CostDistanceDEM | Grid):
                elevation raster that defines the 2.d surface 
        """

        if isinstance(elevation_raster, Grid):
            elevation_raster = CostDistanceDEM.from_grid(elevation_raster)
        self.elevation_raster = elevation_raster
        self.start_path = start_path
        self.cost_raster, self.source_raster = self.elevation_raster.generate_source_cost(
            start_path)
        source_neighbors = [self.source_raster.get_neighbors(
            index) for index in self.source_raster.locations]
        init_costs = self._compute_costs(source_neighbors)
        self.PQ = Heap(init_costs)

    def _compute_costs(self, edge_set: list) -> list:
        """Computes the local cost of each edge within the set
           (i.e. "It costs this much to move from point A to point B along the raster")

        Parameters
        ----------
            edge_set (list): 
                A list of edges, with each edge defined as such:
                [[start loc, stop loc, distance(pixel coords)]]

        Returns
        ----------
            list: The associated cost and the stop location for each edge: [[cost,stop loc]]
        """
        computed_costs = []
        for edges in edge_set:
            for edge in edges:
                start, stop, distance = edge
                dz = self.elevation_raster[start] - self.elevation_raster[stop]
                move_length = np.sqrt(distance**2 + dz**2)
                cost = self.cost_raster[start] + move_length
                computed_costs.append((cost, stop))
        return computed_costs

    def iterate(self, num_igniters, igniter_depth, heat_depth, burn_unit, sigma=None):
        """Performs Djikstra algorithm to compute the geodesic transform, or "cost distance" for the raster
           and finds the respective paths for the ignition pattern arguments.

        Parameters
        ----------
            num_igniters (_type_): Number of igniters 
            igniter_depth (_type_): Spacing between igniters
            heat_depth (_type_): Spacing between heats
            burn_unit (_type_): Burn unit for the simulation
            sigma (_type_, optional): lengthscale for smoothing kernel. Defaults to None.

        Returns
        ----------
            dict,np.ndarray: returns the found paths in world coordinates and the computed cost raster
        """

        # ref: https://pro.arcgis.com/en/pro-app/latest/tool-reference/spatial-analyst/understanding-cost-distance-analysis.htm  # noqa: E501
        # ref: https://pro.arcgis.com/en/pro-app/latest/tool-reference/spatial-analyst/how-the-cost-distance-tools-work.htm  # noqa: E501
        # ref: https://en.wikipedia.org/wiki/Dijkstra%27s_algorithm

        path_dict = {
            'heat': [],
            'igniter': [],
            'leg': [],
            'geometry': []
        }
        # Generate cost surface
        if sigma:
            # smooth the elevation values
            self.elevation_raster.smooth(sigma)

        # Djikstras algorithm
        while len(self.PQ.list) > 0:
            cost, loc = self.PQ.pop()
            if cost > self.cost_raster[loc]:
                continue
            else:
                self.cost_raster[loc] = cost
                neighbors = [self.cost_raster.get_neighbors(loc)]
                neighbor_costs = self._compute_costs(neighbors)
                self.PQ.push(neighbor_costs)

        # Get contour levels that correspond to ignition parameters
        levels = [igniter_depth]
        while levels[-1] < np.max(self.cost_raster.data):
            for i in range(num_igniters - 1):
                levels.append(levels[-1] + igniter_depth)
            levels.append(levels[-1] + heat_depth)

        # Find the contours from the cost raster surface
        contours = self.cost_raster.get_contours(levels)
        heats = []
        heat_set = []
        current_heat = 0
        for (i, contour) in enumerate(contours):
            if i//num_igniters > current_heat:
                current_heat = i//num_igniters
                heats.append(heat_set)
                heat_set = []
            heat_set.append(
                contour
            )

        for i, heat in enumerate(heats):
            for j, path in enumerate(heat):
                if len(path.bounds) > 0:

                    # Crop line to burn unit boundary
                    line_intersect = path.intersection(burn_unit.polygon)
                    # Get lines or multipart lines in the same structure for looping below
                    if isinstance(line_intersect, LineString):
                        line_list = [line_intersect]
                    elif isinstance(line_intersect, MultiLineString):
                        line_list = list(line_intersect.geoms)
                    if len(line_list) > 0:
                        for leg, line_ in enumerate(line_list):
                            if len(line_.bounds) > 1:
                                path_dict["heat"].append(i)
                                path_dict["igniter"].append(j)
                                path_dict["leg"].append(leg)
                                path_dict["geometry"].append(line_)

        return path_dict, self.cost_raster
