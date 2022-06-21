"""
Spatiotemporal patterns and the infamous temporal propagator
"""

# Core imports
from __future__ import annotations
from time import time as unix_time
import warnings

# Internal imports
from .io import write_geojson, write_quicfire

# External imports
import awkward as ak
import numpy as np
import pandas as pd
from shapely.errors import ShapelyDeprecationWarning
from shapely import affinity
from shapely.geometry import MultiPoint, MultiLineString, LineString

# Turn off Pandas copy warning (or figure out how to do it like the Panda wants)
pd.options.mode.chained_assignment = None

# Turn off the Shapely deprecation warning about about future removal
# of the array interface. This happens when a Pandas takes a list of Shapely
# geometies and casts to a list of ndarray objects. GeoPandas would fix this
# but it's not worth the added complexity of GDAL C binary deps. This is fine
# as long as we don't upgrade the Shapely req to v2.
warnings.filterwarnings("ignore", category=ShapelyDeprecationWarning)


class Pattern:

    def __init__(self, heat: list[int], igniter: list[int], leg: list[int],
                 times: list[list[float]], geometry: list[LineString], utm_epsg: int):
        """Constructor

        Args:
            heat (list[int]): Heat of the path
            igniter (list[int]): Igniter id assigned to the path
            leg (list[int]): Leg for the path
            times (list[list[float]]): Coordinate arrival times for the path
            geometry (list[LineString]): Path geometry
            utm_epsg (int): UTM EPSG code for the CRS that the paths are projected in.
        """

        self.heat = heat
        self.igniter = igniter
        self.leg = leg
        self.times = times
        self.geometry = geometry
        self.utm_epsg = utm_epsg

    @classmethod
    def from_dict(cls, paths_dict: dict, utm_epsg: int) -> Pattern:
        """Alternative contructor for initializing a Pattern object with a dictionary
        of path parameters

        Args:
            paths_dict (dict): Dictionary of path parameters
            utm_epsg (int): UTM EPSG code for the CRS that the paths are currently projected in.

        Returns:
            Pattern: A new instance of Pattern
        """

        return cls(
            paths_dict['heat'],
            paths_dict['igniter'],
            paths_dict['leg'],
            paths_dict['times'],
            paths_dict['geometry'],
            utm_epsg=utm_epsg
        )

    def to_dict(self) -> dict:
        """Returns the Pattern path parameters as a dictionary

        Returns:
            dict: Pattern path parameters
        """

        return {
            'heat': self.heat,
            'igniter': self.igniter,
            'leg': self.leg,
            'times': self.times,
            'geometry': self.geometry
        }

    @staticmethod
    def empty_path_dict() -> dict:
        """Helper method for initializing a path parameter dictionary

        Returns:
            dict: Empty path dictionary
        """

        return {
            'heat': [],
            'igniter': [],
            'leg': [],
            'geometry': []
        }

    def to_json(self) -> dict:
        """Write the Pattern to a GeoJSON dictionary

        Returns:
            dict: Timestamped GeoJSON representation of the firing pattern
        """

        # The Timedstamed GeoJSON plug in won't take a time for each coordinate in
        # the sub line string of a MLS, apparently it wants a single time to represent
        # the entire sub line (Either they have a bug or I'm missing something).
        for i, geom in enumerate(self.geometry):
            if isinstance(geom, MultiLineString):
                # Only keep the start time for each sub line
                self.times[i] = [time[0] for time in self.times[i]]

        # Read the jagged times array as an Awkward array for vectorized operations
        times = ak.Array(self.times)

        # Convert to milliseconds since Epoch (this is what Leaflet wants)
        times = (times * 1000) + (unix_time() * 1000)

        # Set the props and styling
        props = {'heat': self.heat, 'igniter': self.igniter,
                 'leg': self.leg, 'times': times.to_list()}
        style = {'icon': 'circle', 'style': {
            'color': '#ff0000', 'radius': 1}}

        # Send off to the GeoJSON writer and return
        return write_geojson(self.geometry, self.utm_epsg, properties=props, style=style)

    def translate(self, x_off: float, y_off: float) -> Pattern:

        geoms = self.geometry
        trans_geoms = []
        for geom in geoms:
            trans_geoms.append(affinity.translate(geom, x_off, y_off))

        self.geometry = trans_geoms

        return self

    def to_quicfire(self, filename: str = None) -> None | str:
        """Write paths dictionary to QUIC-fire ignition file format.

        Args:
            filename (str, optional): If provided, write the ignition file to the
                filename. Defaults to None.

        Returns:
            None | str: None if filename provided, string containing the ignition file if not.
        """

        if filename:
            with open(filename, 'w') as f:
                f.write(write_quicfire(self.geometry, self.times))
        else:
            return write_quicfire(self.geometry, self.times)


class TemporalPropagator:
    """
    This class takes spatial ignition paths and propagates time
    through their coordinates.
    """

    def __init__(self, spacing: float, sync_end_time: bool = False):
        """Class constructor

        Args:
            spacing (float): Stagger spacing between igniters in a heat (meters)
            sync_end_time (bool, optional): If true synchronize igniters within
                a heat to finish simultaneously. Defaults to False.
        """

        self.spacing = spacing
        self.sync_end_time = sync_end_time

    def forward(self, paths, ignition_crew):

        # Create a Pandas DataFrame from the initialized paths dictionary
        self.paths = pd.DataFrame(paths)
        self.ignition_crew = ignition_crew

        # TODO: #6 Check for geometry, heat, igniter and leg columns in Propagator.
        # Geometry must of type LineString

        # Setup some new dataframe columns
        self.paths['start_time'] = 0
        self.paths['end_time'] = 0
        self.paths['times'] = None
        self.paths['times'] = self.paths['times'].astype('object')

        # Sort dataframe by heat, igniter, leg (in that order)
        self.paths.sort_values(by=['heat', 'igniter', 'leg'], ascending=[
            True, True, True], inplace=True)

        # Run the initial forward pass through the paths
        self._init_path_time(self.spacing)

        # Synchronize within heat end times if specified (e.g. ring ignition)
        if self.sync_end_time:
            self._sync_end_time()

        # Compute the arrival time for each coordinate in each path
        self._compute_arrival_times()

        # Drop the intermidary columns
        self.paths.drop(['start_time', 'end_time'],
                        axis=1, inplace=True)

        return self.paths.to_dict(orient='list')

    def _init_path_time(self, spacing: float):
        """ Helper method to run the initial time propagation.

        Args:
            spacing (float): Stagger spacing between igniters in a heat
        """

        # Loop over each ignition path and compute the start time and end time
        for index, path in self.paths.iterrows():

            # Get the heat, igniter and leg indices from the current path
            i, j, k = path.heat, path.igniter, path.leg
            velocity = self.ignition_crew[j].velocity

            # The first check here handles multileg paths. If we're not on the
            # first leg, then we need to compute the distance between the last
            # coordinate of the previous leg and the first coordinate of the
            # current leg and see how long it takes the igniter to get there
            if k != 0:

                # Get the previous path leg
                prev_leg = self.paths.loc[(self.paths.heat == i) & (
                    self.paths.igniter == j) & (self.paths.leg == k-1)]

                # Grab the geometries of the previous and current leg
                prev_leg_geom = prev_leg.geometry.iloc[0]
                cur_leg_geom = path.geometry

                # The shapely distance function gives the shortest distance between
                # the geometries
                distance = prev_leg_geom.distance(cur_leg_geom)

                # Now take the end time of the previous leg and the travel time
                # to get the start time of the current leg
                prev_leg_end_time = prev_leg.end_time.values[0]
                path.start_time = prev_leg_end_time + distance / velocity

            # This check is for the first igniter of a heat (except the first heat,
            # that igniter's start is time zero). The first igniter of a heat can
            # start after the maximum end time of all igniters in the previous heat
            elif (i != 0) and (j == 0):

                # Get the maximum end time from all igniters in the previous heat
                prev_heat_max_end_time = self.paths.loc[self.paths.heat ==
                                                        i-1, 'end_time'].max()

                # The current igniter's start time is the previous heat max end time
                path.start_time = prev_heat_max_end_time

            # This check is for any igniter following the first one. Note that
            # multileg ignition paths are caught in the first check above, so
            # this always deals with the first leg. We'll start by giving the
            # igniter the same start time as the previous one, but igniters don't
            # always start along a line parallel to a coordinate frame axis and
            # ignition paths are not always straight lines. So, we have to do a
            # vector projection to compute the offset in the helper function
            # `_get_offset`. We'll also apply the spacing there as well.
            elif j != 0:

                # Get the previous and current igniters (again, no need to use
                # k the leg index, these will all be leg 0 due to the catch
                # above)
                cur_igniter = self.paths.loc[(
                    self.paths.heat == i) & (self.paths.igniter == j)]
                prev_igniter = self.paths.loc[(
                    self.paths.heat == i) & (self.paths.igniter == j-1)]

                # Get the previous igniter's start time
                prev_start_time = prev_igniter.start_time.values[0]

                # Compute the offset due to stagger spacing and incongruence
                # along a coordinate frame axis
                path.start_time = prev_start_time + self._get_offset(
                    prev_igniter, cur_igniter, spacing, velocity)

            # The last condition we have caught yet is the first igniter of the
            # first heat. That igniter gets a start time of zero
            else:
                path.start_time = 0

            # Calculate path end time (seconds along path plus start time)
            # path.end_time = path.start_time + path.meters / velocity
            path.end_time = path.start_time + path.geometry.length / velocity

            # Insert row back into paths dataframe
            self.paths.loc[index] = path

        # Depending of the arrange of igniter start positions it is
        # possible that the minimum start time is less than zero. We fix
        # that by adding the minimum back to all start and end times
        min_start_time = self.paths['start_time'].min()
        if min_start_time != 0:
            self.paths['start_time'] -= min_start_time
            self.paths['end_time'] -= min_start_time

    def _get_offset(self, prev_igniter: pd.Series, cur_igniter: pd.Series, spacing: float, velocity: float) -> float:
        """Compute the offset time between the previous and current igniters

        Args:
            prev_igniter (pd.Series): Dataframe row of previous igniter
            cur_igniter (pd.Series): Dataframe row of current igniter
            spacing (float): Stagger spacing (meters)
            velocity (float): Speed of the igniter (meters/second)

        Returns:
            float: Offset time between previous and current igniters
        """

        # We need three coordinates to construct two vectors: the
        # first coordinate from the current igniter and the first
        # and second coordinate from the preivous igniter
        cur_igniter_first_pos = np.array(
            cur_igniter.geometry.iloc[0].coords[0])
        prev_igniter_first_pos = np.array(
            prev_igniter.geometry.iloc[0].coords[0])
        prev_igniter_second_pos = np.array(
            prev_igniter.geometry.iloc[0].coords[1])

        # Now construct two vectors. First a vector from the
        # previous igniter's first position to the current igniter's
        # first position. And second a vector from the previous
        # igniters first position to the previous igniters second
        # position
        a_vec = cur_igniter_first_pos - prev_igniter_first_pos
        b_vec = prev_igniter_second_pos - prev_igniter_first_pos

        # Now we can project the a vector onto the unit b vector and
        # compute its magnitude which give the offset distance
        offset_distance = a_vec.dot(b_vec/np.linalg.norm(b_vec))

        # Add the stagger spacing distance and divide by velocity
        # for travel time
        return (spacing + offset_distance) / velocity

    def _sync_end_time(self):
        """ Helper method to synchronize end times"""

        # TODO: #7 What about multileg ignition paths when synchronizing end times?

        # Get the unique heat indecies
        heats = np.sort(self.paths.heat.unique())

        # For each heat find the maximum end time and adjust the start time accordingly
        for i in heats:

            # Grab the dataframe rows for the current heat
            cur_heat = self.paths[self.paths.heat == i]

            # Compute difference between start time and max end time
            max_end_time = cur_heat.end_time.max()
            time_diff = max_end_time - cur_heat.end_time

            # Adjust the start time s.t. end time is equal to the max end time
            cur_heat.start_time = cur_heat.start_time + time_diff
            cur_heat.end_time = max_end_time

            # Place the current heat back in the dataframe
            self.paths[self.paths.heat == i] = cur_heat

    def _compute_arrival_times(self):
        """For each path, ask the igniter what line type they are
        suppose to lay down and call the respective methods.
        """

        for index, path in self.paths.iterrows():
            cur_igniter = self.ignition_crew[path.igniter]
            if cur_igniter.interval == 0:
                self._lines(index, path, cur_igniter.velocity)
            elif cur_igniter.interval < 0:
                self._dashes(index, path, cur_igniter.velocity,
                             -cur_igniter.interval)
            else:
                self._dots(index, path, cur_igniter.velocity,
                           cur_igniter.interval)

    def _lines(self, index: int, path: pd.Series, velocity: float):
        """Compute arrival times along each igniter's coordinate sequence
        without stopping (solid ignition paths)
        """

        # Get the coordinate sequence as a numpy array
        coords = np.array(path.geometry.coords)

        # Reset the arrival time to the start time of the current path
        arrival_time = path.start_time

        # Initialize the arrival time array for the current path
        path_times = [arrival_time]

        # Loop of the coordinate sequence except the last one
        for i, xy in enumerate(coords[:-1]):

            # Get the next coordinate in the sequence and compute the distance
            # between it and the current coordinate
            next_xy = coords[i+1]
            meters = np.linalg.norm(xy - next_xy)

            # Update the arrival time and add to the times array for the
            # current path
            arrival_time = arrival_time + (meters/velocity)
            path_times.append(arrival_time)

        self.paths.at[index, 'times'] = path_times

    def _dashes(self, index: int, path: pd.Series, velocity: float, interval: float):
        """Compute arrival times along each igniter's coordinate sequence
        by picking up and putting down ignitions (dashes)
        """

        # We'll have a start time and end time for each dash. Initialize
        # the start time to the current path's start time
        start_time = path.start_time

        # Get a range of distances along the length of the path spaced by
        # the ignition rate
        distances = np.arange(0, path.geometry.length, interval)

        # Interpolate points at those distance along the path
        points = MultiPoint([path.geometry.interpolate(distance)
                             for distance in distances])

        # Set the arrays for the current path arrival times and
        # dash geometries
        path_times = []
        line_segs = []

        # Reset the fire boolean for controlling when the ignition is active
        fire = True
        point_geoms = list(points.geoms)

        # Loop over the interpolated points except the last
        for i, point in enumerate(point_geoms[:-1]):

            # Get the current and next point coordinates
            xy = np.array(point.coords)[0]
            next_xy = np.array(point_geoms[i+1].coords)[0]

            # Comput the distance between points and the travel time
            meters = np.linalg.norm(xy - next_xy)
            end_time = float(start_time + (meters/velocity))

            # IF fire is active for this segment then add start and end
            # times to the current path arrival time arrray and append
            # the dash to the line segment array
            if fire:
                path_times.append([start_time, end_time])
                # path_times.append(end_time)
                line_segs.append([xy.tolist(), next_xy.tolist()])

            # Toogle the fire boolean and update the start time
            fire ^= True
            start_time = end_time

        # Add the current path arrival times to the global times array
        # and create a multileg line string and append to the new geometry
        # array
        self.paths.at[index, 'times'] = path_times
        self.paths.at[index, 'geometry'] = MultiLineString(line_segs)

    def _dots(self, index: int, path: pd.Series, velocity: float, interval: float):
        """Compute arrival times along each igniter's coordinate sequence
        for interpolated equally spaced points (dots)
        """

        arrival_time = path.start_time

        # Get a range of distances along the length of the path space by
        # the ignition rate
        distances = np.arange(0, path.geometry.length, interval)

        # Interpolate points at those distance along the path
        points = MultiPoint([path.geometry.interpolate(distance)
                             for distance in distances])

        # Set the initial arrival time
        path_times = [arrival_time]

        # For each interpolated point except the last
        for i, point in enumerate(points[:-1]):

            # Get the current and next points
            xy = np.array(point.coords)
            next_xy = np.array(points[i+1].coords)

            # Compute the distance between points and travel time
            meters = np.linalg.norm(xy - next_xy)
            arrival_time = arrival_time + (meters/velocity)

            # Add the arrival time to the current path's time array
            path_times.append(arrival_time)

        # Add the current path's time array to the global time array and
        # add the multipar point geometry to the new geometries array
        self.paths.at[index, 'times'] = path_times
        self.paths.at[index, 'geometry'] = points
