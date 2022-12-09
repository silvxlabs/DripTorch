"""
Utility module for computing distance transforms

TODO: #145 Use Euclidean distance transform when topo scale is zero
"""

import heapq
from ._grid import Grid
from shapely.geometry import LineString
import numpy as np


def gdt(dem: Grid, source_path: LineString, neighborhood_size: int = 1, z_multiplier: int = 1) -> Grid:
    """Compute the geodesic distance transform from a source path on a
    2.5 surface (e.g. digital elevation model)

    Parameters
    ----------
    dem : Grid
        Digital elevation model
    source_path : LineString
        Source path from which to compute the geodesic distances
    neighborhood_size : int, optional
        Size of neighborhood to evaluate during distance computation, by default 4

    Returns
    -------
    Grid
        Geodesic distance transform
    """

    gdt = GeodesicDistanceTransform(
        dem, source_path, neighborhood_size, z_multiplier)
    return gdt.solve()


class Heap:
    """A heap class for the priority queue"""

    def __init__(self, x=None):
        """Constructor"""
        if x:
            self.list = x
        else:
            self.list = []
        heapq.heapify(self.list)

    def push(self, x):
        """Push to the queue"""
        if isinstance(x, list):
            [heapq.heappush(self.list, item) for item in x]
        else:
            heapq.heappush(self.list, x)

    def pop(self):
        """Pop from the queue; extract min"""
        return heapq.heappop(self.list)

    def __len__(self):
        return len(self.list)


class GeodesicDistanceTransform:
    """Class for computing the geodesic distance transform on a DEM"""

    def __init__(self, dem: Grid, source_path: LineString, neighborhood_size: int = 1, z_multiplier: int = 1):
        """Constructor

        Parameters
        ----------
        dem : Grid
            Input elevation raster
        source_path : LineString
            Source path in from which to compute the geodesic distances
        neighborhood_size : int, optional
            Size of the neighborhood to evaluate during distance computation,
            by default 4
        """

        # TODO: #144 Auto default DEM padding value in GDT class

        # Initialize the priority queue
        self.PQ = Heap()

        # Pad the DEM to avoid edge effects
        self.dem = dem.pad(10, np.inf)
        if z_multiplier != 1:
            self.dem.data *= z_multiplier

        # Create source grid
        source = Grid.like(self.dem, fill_value=0)
        source.draw_line(source_path)

        # Initialize cost distance grid
        self.cost_distance = Grid.like(self.dem, fill_value=np.inf)
        self.cost_distance.data[source.data == 1] = 0

        # Initialize the local distance kernel for neighborhood evaluation
        # The scale parameter here assumes square pixels
        self.neighborhood_size = neighborhood_size
        self.local_distance_kernel = self.get_local_distance_kernel(
            neighborhood_size, self.dem.transform.res_x)

        # Stack the distance to the source cells with the (i,j) indices
        # to initialize the priority queue
        source_indices = np.argwhere(source.data == 1)
        distance_source_indices = np.hstack(
            (np.zeros((len(source_indices), 1)), source_indices))

        # Enqueue the distance and indices of the source cells
        self.PQ.push(list(map(tuple, distance_source_indices)))

    @classmethod
    def get_local_distance_kernel(cls, neighborhood_size: int = 1, scale: float = 1) -> np.ndarray:
        """Builds a squared local distance kernel for neighborhood evaluation

        Parameters
        ----------
        neighborhood_size : int, optional
            Size of the neighborhood. This controls the adjacency degree of each
            in the network, by default 4
        scale : float, optional
            Scale parameter used to correct intercell distance if not unit
            distance, by default 1

        Returns
        -------
        np.ndarray
           Squared local distance kernel for neighborhood evaluation
        """

        k = neighborhood_size

        # Initialize the kernel with zeros
        local_distance_kernel = np.zeros((k * 2 + 1, k * 2 + 1))

        # Compute euclidean distance from the center of the kernel
        for i in range(-k, k + 1):
            for j in range(-k, k + 1):
                local_distance_kernel[i + k, j + k] = np.sqrt(i**2 + j**2)

        # Scale and sqaure the kernel to avoid sqauring on each neiborhood evaluation
        return (local_distance_kernel * scale)**2

    def _evaluate_neighbors(self, distance: float, i: int, j: int) -> None:
        """Private method for evaluating the neighbors of a cell

        Parameters
        ----------
        distance : float
            Current accumulated distance of the center cell
        i : int
            Row index of the center cell
        j : int
            Column index of the center cell
        """

        k = self.neighborhood_size

        # For each neighbor, compute the accumlated distance and conditionally
        # enqueue the neighbor's index and distance if the accumulated distance
        # is less than the current cost distance
        for ii in range(-k, k + 1):
            for jj in range(-k, k + 1):

                # Compute the change in elevation
                dz = self.dem.data[i, j] - self.dem.data[i+ii, j+jj]

                # Add the 3D distance to the accumulated distance
                neighbor_distance = distance + np.sqrt(
                    dz**2 + self.local_distance_kernel[ii+k, jj+k])

                # If the neighbor distance is less than the current cost distance,
                # update the cost distance and enqueue the neighbor
                # and push the the queue
                if neighbor_distance < self.cost_distance.data[i+ii, j+jj]:
                    self.cost_distance.data[i+ii, j+jj] = neighbor_distance
                    self.PQ.push((neighbor_distance, i+ii, j+jj))

    def solve(self) -> Grid:
        """Run Dijkstra's algorithm to compute the geodesic distance transform

        Returns
        -------
        Grid
            Geodesic distance to each grid cell from the provided source line
        """

        # While the priority queue is not empty, pop the minimum distance
        # and evaluate the neighbors
        while len(self.PQ) > 0:
            distance, i, j = self.PQ.pop()
            i, j = int(i), int(j)
            if distance <= self.cost_distance.data[i, j]:
                self._evaluate_neighbors(distance, i, j)

        # Unpad the cost distance grid and return
        self.cost_distance.data[self.cost_distance.data == np.inf] = 0
        return self.cost_distance.pad(-10)
