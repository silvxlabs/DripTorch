"""
Spatiotemporal patterns and the infamous temporal propagator
"""

# Core imports
from __future__ import annotations
import copy
from time import time as unix_time
import warnings

# Internal imports
from .io import Projector, write_geojson, write_quicfire
from .unit import BurnUnit
from .errors import EPSGError

# External imports
import awkward as ak
import numpy as np
import pandas as pd
from shapely.errors import ShapelyDeprecationWarning
from shapely import affinity
from shapely.geometry import MultiPoint, MultiLineString, LineString, shape


# Turn off Pandas copy warning (or figure out how to do it like the Panda wants)
pd.options.mode.chained_assignment = None


"""

Turn off the Shapely deprecation warning about about future removal
of the array interface. This happens when a Pandas takes a list of Shapely
geometries and casts to a list of ndarray objects. GeoPandas would fix this
but it's not worth the added complexity of GDAL C binary deps. This is fine
as long as we don't upgrade the Shapely req to v2.

"""
warnings.filterwarnings("ignore", category=ShapelyDeprecationWarning)


class Pattern:
    """Patterns are objects that store the spatial and temporal components of a
    firing technique.

    Parameters
    ----------
    heat : list[int]
        Heat of the path
    igniter : list[int]
        Igniter id assigned to the path
    leg : list[int])
        Leg for the path
    times : list[list[float]]
        Coordinate arrival times for the path
    geometry : list[LineString]
        Path geometry
    epsg : int
        EPSG code for path geometry
    """

    def __init__(self, heat: list[int], igniter: list[int], leg: list[int], times: list[list[float]],
                 geometry: list[LineString], epsg: int,
                 ):

        self.heat = heat
        self.igniter = igniter
        self.leg = leg
        self.times = times
        self.geometry = geometry
        self.epsg = epsg

        # Compute the total elapsed time for the ignition crew
        times_ak = ak.Array(self.times)
        min_time = ak.min(times_ak)
        max_time = ak.max(times_ak)
        self.elapsed_time = max_time - min_time

    @classmethod
    def from_dict(cls, paths_dict: dict, epsg: int) -> Pattern:
        """Alternative constructor for initializing a Pattern object with a dictionary
        of path parameters

        Parameters
        ----------
        paths_dict : dict
            Dictionary of path parameters
        epsg : Int
            EPSG code of path geometries

        Returns
        -------
        Pattern
            A new instance of Pattern
        """

        paths_dict["geometry"] = [shape(x) for x in paths_dict["geometry"]]
        return cls(
            paths_dict["heat"],
            paths_dict["igniter"],
            paths_dict["leg"],
            paths_dict["times"],
            paths_dict["geometry"],
            epsg,
        )

    def to_dict(self) -> dict:
        """Returns the Pattern path parameters as a dictionary

        Returns
        -------
        dict
            Pattern path parameters
        """

        return {
            "heat": self.heat,
            "igniter": self.igniter,
            "leg": self.leg,
            "times": self.times,
            # convert to geoJSON for storage
            "geometry": [x.__geo_interface__ for x in self.geometry],
        }

    @staticmethod
    def empty_path_dict() -> dict:
        """Helper method for initializing a path parameter dictionary

        Returns
        -------
        dict
            Empty path dictionary
        """

        return {"heat": [], "igniter": [], "leg": [], "geometry": []}

    def to_json(self) -> dict:
        """Write the Pattern to a GeoJSON dictionary

        Returns
        -------
        dict
            Timestamped GeoJSON representation of the firing pattern
        """

        # Copy the times array
        times = self.times.copy()

        # The Timedstamed GeoJSON plugin in won't take a time for each coordinate in
        # the sub line string of a MLS, apparently it wants a single time to represent
        # the entire sub line (Either they have a bug or I'm missing something).
        for i, geom in enumerate(self.geometry):
            if isinstance(geom, MultiLineString):
                # Only keep the start time for each sub line
                times[i] = [time[0] for time in times[i]]

        # Read the jagged times array as an Awkward array for vectorized operations
        times = ak.Array(times)

        # Convert to milliseconds since Epoch (this is what Leaflet wants)
        times = (times * 1000) + (unix_time() * 1000)

        # Set the props and styling
        props = {
            "heat": self.heat,
            "igniter": self.igniter,
            "leg": self.leg,
            "times": times.to_list(),
        }
        style = {"icon": "circle", "style": {"color": "#ff0000", "radius": 1}}

        # Send off to the GeoJSON writer and return
        return write_geojson(
            self.geometry,
            self.epsg,
            properties=props,
            style=style,
            elapsed_time=self.elapsed_time,
        )

    def translate(self, x_off: float, y_off: float) -> Pattern:
        """Translate pattern geometry along the x and y axis by the supplied
        x and y offset amounts.

        Parameters
        ----------
        x_off : float
            Offset along the x axis
        y_off : float
            Offset along the y axis

        Returns
        -------
        Pattern
            New Pattern object with translated geometries
        """

        # Translate the path geometries
        geoms = self.geometry
        trans_geoms = []
        for geom in geoms:
            trans_geoms.append(affinity.translate(geom, x_off, y_off))

        # Create a clone of the existing Pattern object and replace the geometries
        # with the translated geometries
        obj_copy = copy.copy(self)
        obj_copy.geometry = trans_geoms

        # Return the new Pattern object
        return obj_copy

    def to_quicfire(self, burn_unit: BurnUnit, filename: str = None, time_offset=0,
                    resolution: int = 1, dst_epsg: int = None) -> None | str:
        """Write paths dictionary to QUIC-fire ignition file format.

        Parameters
        ----------
        burn_unit : BurnUnit
            Burn unit that defines the extent of the QF simulation
        filename : str, optional
            If provided, write the ignition file to the filename. Defaults to None.
        time_offset : float, optional
            Time offset to add to the ignition times. Defaults to 0.
        resolution : int, optional
            Horizontal resolution of QUIC-fire domain (meters). Defaults to 1.
        dst_epsg : int, optional
            EPSG code for the destination projection. Defaults to None.

        Returns
        -------
        None | str
            None if filename provided, string containing the ignition file if not.
        """

        times = self.times.copy()
        geometry = self.geometry.copy()
        domain = burn_unit.copy()

        # Apply time offset if not zero
        if time_offset:
            times = ak.Array(times)
            times = times + time_offset
            times = times.to_list()

        # Reproject burn_unit and geometry to destination epsg if provided
        if dst_epsg:
            projector = Projector(domain.utm_epsg, dst_epsg)

            domain.polygon = projector.forward(domain.polygon)

            reproj_geoms = []
            for geom in geometry:
                reproj_geoms.append(projector.forward(geom))
            geometry = reproj_geoms

        # Translate pattern geometry to the origin or the CRS according to the burn unit extent
        lower_left = domain.bounds.min(axis=0)
        trans_geoms = []
        for geom in geometry:
            trans_geoms.append(affinity.translate(
                geom, -lower_left[0], -lower_left[1]))
        geometry = trans_geoms

        # Check if filename was provided and write to it if so
        if filename:
            with open(filename, "w") as f:
                f.write(
                    write_quicfire(
                        geometry, times, self.elapsed_time, resolution=resolution
                    )
                )
        # Otherwise return QF ignition file to client as string
        else:
            return write_quicfire(
                geometry, times, self.elapsed_time, resolution=resolution
            )

    def merge(self, pattern: Pattern, time_offset: float = 0, inplace: bool = False) -> Pattern:
        """Merge an input pattern with self

        Parameters
        ----------
        pattern : Pattern
            Input pattern to be merged into self
        time_offset : float
            Time offset between patterns (seconds)
        inplace : bool, optional
            Overwrites Pattern object if true, otherwise return new Pattern object. Defaults to True.

        Raises
        ------
        EPSGError.non_equivalent: EPSG code for input pattern does not match self.epsg

        Returns
        -------
        Pattern
            Merged pattern object
        """

        # Check that the EPSG codes are the same
        if pattern.epsg != self.epsg:
            raise EPSGError.non_equivalent

        # Get an empty path dictionary
        merged_dict = self.empty_path_dict()

        # Delay times in the second pattern by the elapsed time of the first pattern and offset
        delayed_times = (
            ak.max(self.times) + time_offset + ak.Array(pattern.times)
        ).to_list()

        # Build merged pattern attributes
        merged_dict["heat"] = self.heat + pattern.heat
        merged_dict["igniter"] = self.igniter + pattern.igniter
        merged_dict["leg"] = self.leg + pattern.leg
        merged_dict["times"] = self.times + delayed_times
        merged_dict["geometry"] = self.geometry + pattern.geometry

        # Instantiate a new Pattern object
        merged_pattern = self.from_dict(merged_dict, self.epsg)

        # Compute summed elapse time
        merged_pattern.elapsed_time = (
            self.elapsed_time + time_offset + pattern.elapsed_time
        )

        # If inplace then overwrite self with the merged pattern
        if inplace:
            self = merged_pattern

        # If inplace is False then return the merged pattern. This is outside
        # of the if statement so that the merged pattern is still return in case
        # the user sets the method to a variable
        return merged_pattern


class TemporalPropagator:
    """
    This class takes spatial ignition paths and propagates time
    through their coordinates.
    """

    def __init__(
        self, spacing: float = 0, sync_end_time: bool = False, return_trip: bool = False
    ):
        """Class constructor

        Args:
            spacing (float): Stagger spacing between igniters in a heat (meters). Defaults to 0.
            sync_end_time (bool, optional): If true synchronize igniters within
                a heat to finish simultaneously. Defaults to False.
            return_trip (bool, optional): If true, incorporate the time it takes for a heat
                of igniters to return to the opposite side of the burn unit (use only for flank ignition).
                Defaults to False.
        """

        self.spacing = spacing
        self.sync_end_time = sync_end_time
        self.return_trip = return_trip

    def forward(self, paths:dict, ignition_crew:IgnitionCrew, time_offset_heat:float) -> None:
        """Compute and store time values for the provided paths dicitionary and its respective
           ignition crew.

        Args:
            paths (dict): Dictionary containing the paths generated by a given technique
            ignition_crew (IgnitionCrew): The set of ignitors responsible to generating the paths
            time_offset_heat (float, optional): Time delay between ignition heats.
        Returns:
            None: Inplace operation.
        """
        # Create a Pandas DataFrame from the initialized paths dictionary
        self.paths = pd.DataFrame(paths)
        self.ignition_crew = ignition_crew

        # Geometry must of type LineString

        # Setup some new dataframe columns
        self.paths["start_time"] = 0
        self.paths["end_time"] = 0
        self.paths["times"] = None
        self.paths["times"] = self.paths["times"].astype("object")

        # Sort dataframe by heat, igniter, leg (in that order)
        self.paths.sort_values(
            by=["heat", "igniter", "leg"], ascending=[True, True, True], inplace=True
        )

        # Run the initial forward pass through the paths
        self._init_path_time(self.spacing,time_offset_heat)

        # Synchronize within heat end times if specified (e.g. ring ignition)
        if self.sync_end_time:
            self._sync_end_time()

        # Compute the arrival time for each coordinate in each path
        self._compute_arrival_times()

        # Drop the intermidary columns
        self.paths.drop(["start_time", "end_time"], axis=1, inplace=True)

        return self.paths.to_dict(orient="list")

    def _init_path_time(self, spacing: float,time_offset_heat:float):
        """Helper method to run the initial time propagation.

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
                prev_leg = self.paths.loc[
                    (self.paths.heat == i)
                    & (self.paths.igniter == j)
                    & (self.paths.leg == k - 1)
                ]

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
                prev_heat_max_end_time = self.paths.loc[
                    self.paths.heat == i - 1, "end_time"
                ].max()

                # The current igniter's start time is the previous heat max end time
                path.start_time = prev_heat_max_end_time

                # If return_trip is turned on, then incorporate the return trip before this heat starts
                if self.return_trip:
                    path.start_time += path.geometry.length / velocity

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
                cur_igniter = self.paths.loc[
                    (self.paths.heat == i) & (self.paths.igniter == j)
                ]
                prev_igniter = self.paths.loc[
                    (self.paths.heat == i) & (self.paths.igniter == j - 1)
                ]

                # Get the previous igniter's start time
                prev_start_time = prev_igniter.start_time.values[0]

                # Compute the offset due to stagger spacing and incongruence
                # along a coordinate frame axis
                path.start_time = prev_start_time + self._get_offset(
                    prev_igniter, cur_igniter, spacing, velocity
                )

            # The last condition we have caught yet is the first igniter of the
            # first heat. That igniter gets a start time of zero
            else:
                path.start_time = 0
            
            # Apply heat interval time offset
            if i > 0:
                path.start_time += time_offset_heat

            # Calculate path end time (seconds along path plus start time)
            # path.end_time = path.start_time + path.meters / velocity
            path.end_time = path.start_time + path.geometry.length / velocity

            # Insert row back into paths dataframe
            self.paths.loc[index] = path

        # Depending of the arrange of igniter start positions it is
        # possible that the minimum start time is less than zero. We fix
        # that by adding the minimum back to all start and end times
        min_start_time = self.paths["start_time"].min()
        if min_start_time != 0:
            self.paths["start_time"] -= min_start_time
            self.paths["end_time"] -= min_start_time

    def _get_offset(
        self,
        prev_igniter: pd.Series,
        cur_igniter: pd.Series,
        spacing: float,
        velocity: float,
    ) -> float:
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
        offset_distance = a_vec.dot(b_vec / np.linalg.norm(b_vec))

        # Add the stagger spacing distance and divide by velocity
        # for travel time
        return (spacing + offset_distance) / velocity

    def _sync_end_time(self):
        """Helper method to synchronize end times"""

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
            if (cur_igniter.gap_length == None) and (cur_igniter.dash_length == None):
                self._lines(index, path, cur_igniter.velocity)
            elif cur_igniter.dash_length != None:
                self._dashes(index, path, cur_igniter.velocity,
                             cur_igniter.gap_length, cur_igniter.dash_length)
            else:
                self._dots(index, path, cur_igniter.velocity,
                           cur_igniter.gap_length)

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
            next_xy = coords[i + 1]
            meters = np.linalg.norm(xy - next_xy)

            # Update the arrival time and add to the times array for the
            # current path
            arrival_time = arrival_time + (meters / velocity)
            path_times.append(arrival_time)

        self.paths.at[index, "times"] = path_times

    def _dashes(self, index: int, path: pd.Series, velocity: float, gap_length: float, dash_length: float):
        """Compute arrival times along each igniter's coordinate sequence
        by picking up and putting down ignitions (dashes)
        """

        # We'll have a start time and end time for each dash. Initialize
        # the start time to the current path's start time
        start_time = path.start_time

        # Get a range of distances along the length of the path spaced by
        # the ignition rate
        if not gap_length:
            distances = np.arange(0, path.geometry.length, dash_length)
        else:
            distances = []
            sum_length = 0
            toggle = True
            while sum_length < path.geometry.length:
                distances.append(sum_length)
                if toggle:
                    sum_length += dash_length
                else:
                    sum_length += gap_length
                toggle ^= True

        # Interpolate points at those distance along the path
        points = MultiPoint(
            [path.geometry.interpolate(distance) for distance in distances]
        )

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
            next_xy = np.array(point_geoms[i + 1].coords)[0]

            # Comput the distance between points and the travel time
            meters = np.linalg.norm(xy - next_xy)
            end_time = float(start_time + (meters / velocity))

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
        self.paths.at[index, "times"] = path_times
        self.paths.at[index, "geometry"] = MultiLineString(line_segs)

    def _dots(self, index: int, path: pd.Series, velocity: float, gap_length: float):
        """Compute arrival times along each igniter's coordinate sequence
        for interpolated equally spaced points (dots)
        """

        arrival_time = path.start_time

        # Get a range of distances along the length of the path space by
        # the ignition rate
        distances = np.arange(0, path.geometry.length, gap_length)

        # Interpolate points at those distance along the path
        points = MultiPoint(
            [path.geometry.interpolate(distance) for distance in distances]
        )

        # Set the initial arrival time
        path_times = [arrival_time]

        # For each interpolated point except the last
        for i, point in enumerate(points[:-1]):

            # Get the current and next points
            xy = np.array(point.coords)
            next_xy = np.array(points[i + 1].coords)

            # Compute the distance between points and travel time
            meters = np.linalg.norm(xy - next_xy)
            arrival_time = arrival_time + (meters / velocity)

            # Add the arrival time to the current path's time array
            path_times.append(arrival_time)

        # Add the current path's time array to the global time array and
        # add the multipar point geometry to the new geometries array
        self.paths.at[index, "times"] = path_times
        self.paths.at[index, "geometry"] = points
