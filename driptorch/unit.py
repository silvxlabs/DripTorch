"""
Reading and manipulating a burn unit geometry and splitting
the boundary to wind-centric segments
"""

# Core imports
from __future__ import annotations
import copy

# Internal imports
from .io import Projector, write_geojson, read_geojson_polygon

# External imports
import numpy as np
from shapely.geometry import Polygon, LineString, Point
from shapely import affinity


# TODO: #8 Base class shapely polygon and extend in BurnUnit class
class BurnUnit:

    def __init__(self, polygon: Polygon, wind_direction: float, utm_epsg: int = None):
        """Constructor

        Args:
            polygon (Polygon): Shapely polygon geometry object
            wind_direction (float): Wind direction (degrees)
            utm (int): UTM EPSG code of spatial data. If not provided it is assumed
                that coordinates are in 4326 and will be converted to UTM. Defaults to None.
        """

        # Set the global EPSG source
        if not utm_epsg:
            utm_epsg, polygon = Projector.web_mercator_to_utm(polygon)

        # Store instance attributes
        self.utm_epsg = utm_epsg
        self.polygon = polygon
        self.wind_direction = wind_direction
        self.centroid = polygon.centroid
        self.polygon_segments = PolygonSplitter()

        # Compute the angle used to rotate the unit s.t. the wind direction
        # is congruent with the positive x-axis
        self.wind_alignment_angle = (self.wind_direction - 90) % 360

        # Align the unit, run the boundary splitting algorithm for
        # anchors and segs, and then unalign
        self._align()
        self.polygon_segments.split(self.polygon)
        self._unalign()

    @classmethod
    def from_json(cls, geojson: dict, wind_direction: float) -> BurnUnit:
        """Alternative constructor used to create a BurnUnit object from
        a GeoJSON dictionary.

        Args:
            geojson (dict): GeoJSON dictionary
            wind_direction (float): Wind direction (degrees)
            epsg (int): EPSG code of the input GeoJSON. Defaults to 4326.

        Returns:
            BurnUnit: New instance of a BurnUnit
        """

        # Read the GeoJSON as a shapely polygon
        polygon = read_geojson_polygon(geojson)

        return cls(polygon, wind_direction)

    def to_json(self, **kwargs) -> dict:
        """Write the BurnUnit boundary to a GeoJSON dictionary

        Returns:
            dict: GeoJSON dictionary
        """

        return write_geojson([self.polygon], utm_epsg=self.utm_epsg, **kwargs)

    def _align(self):
        """Align the unit and boundary segs to the wind
        """

        if self.wind_alignment_angle:
            self.polygon = affinity.rotate(
                self.polygon, self.wind_alignment_angle, self.centroid)
            self.polygon_segments.rotate(
                self.wind_alignment_angle, self.centroid)

    def _unalign(self):
        """Revert the unit and boundary seg to their origional orientation
        """

        if self.wind_alignment_angle:
            self.polygon = affinity.rotate(
                self.polygon, -self.wind_alignment_angle, self.centroid)
            self.polygon_segments.rotate(
                -self.wind_alignment_angle, self.centroid)

    def copy(self) -> BurnUnit:
        """Utility method for copying a BurnUnit instance

        Returns:
            BurnUnit: New instance of a BurnUnit
        """

        return copy.copy(self)

    def buffer_control_line(self, width: float) -> BurnUnit:
        """Shrink the burn unit to account for the width of the control line

        Args:
            distance (with): Width of the control line (meters)

        Returns:
            BurnUnit: New instance of a BurnUnit
        """

        # Use shapely's buffer method on the polygon
        buffered_polygon = self.polygon.buffer(-width)

        return BurnUnit(buffered_polygon, self.wind_direction, utm_epsg=self.utm_epsg)

    def buffer_downwind(self, width: float) -> BurnUnit:
        """Create a downwind blackline buffer

        Args:
            width (float): Width of downwind buffer (meters)

        Returns:
            BurnUnit: New instance of a BurnUnit
        """

        # Buffer the fore line by the blackline width parameter
        fore_line_buffer = self.polygon_segments.fore.buffer(
            width, cap_style=3)

        # Now take the difference between the current firing area and the fore line
        # buffer to cut out the downwind blackline area
        buffered_polygon = self.polygon.difference(fore_line_buffer)

        return BurnUnit(buffered_polygon, self.wind_direction, utm_epsg=self.utm_epsg)

    def difference(self, burn_unit: BurnUnit) -> BurnUnit:
        """Return a burn unit instance that is the difference between
        this burn unit and another. Useful for obtaining the blackline
        area for clearing fuels.

        Args:
            burn_unit (BurnUnit): The BurnUnit instance to difference against

        Returns:
            BurnUnit: A new instance of a BurnUnit
        """

        # Use shapely's set-theorectic difference method
        polygon_difference = self.polygon.difference(burn_unit.polygon)

        return BurnUnit(polygon_difference, self.wind_direction, utm_epsg=self.utm_epsg)

    def get_bounds(self) -> np.ndarray:
        """Helper method for fetching the bounding box of the unit

        Returns:
            np.ndarray: Bounding box of the unit
        """

        return np.array(self.polygon.envelope.exterior.coords[:-1])


class PolygonSplitter:

    def __init__(self):
        """Constructor
        """

        # We're just setting these to None to start with so they can be pumped
        # through wind alignment before we compute them
        self.fore: LineString = None
        self.aft: LineString = None
        self.port: LineString = None
        self.starboard: LineString = None

    def rotate(self, angle: float, origin: Point):
        """Helper method to rotate all four boundary segs

        Args:
            angle (float): Angle to rotate line by (degrees)
            origin (Point): Origin of rotation
        """

        self.fore = affinity.rotate(
            self.fore, angle, origin) if self.fore else self.fore
        self.aft = affinity.rotate(
            self.aft, angle, origin) if self.aft else self.aft
        self.port = affinity.rotate(
            self.port, angle, origin) if self.port else self.port
        self.starboard = affinity.rotate(
            self.starboard, angle, origin) if self.starboard else self.starboard

    def split(self, polygon: Polygon):
        """Split the polygon to four wind-centric segments

        Args:
            polygon (Polygon): Polygon to split
        """

        self.coords = np.array(polygon.exterior.coords[:-1])

        # Extract fore, aft, port and starboard anchor points
        fore_idx = self._get_anchor(0)
        aft_idx = self._get_anchor(0, side='upper')
        port_idx = self._get_anchor(1)
        starboard_idx = self._get_anchor(1, side='upper')

        # Extract fore, aft, port and starboard lines
        self.fore = self._get_segment(port_idx, starboard_idx)
        self.aft = self._get_segment(starboard_idx, port_idx)
        self.port = self._get_segment(aft_idx, fore_idx)
        self.starboard = self._get_segment(fore_idx, aft_idx)

    def _get_segment(self, start_idx: int, end_idx: int) -> LineString:
        """Compute burn unit exterior line strings (subsequence of polygon coordinates)
        that make up the four wind-centric parts of the burn unit: fore, aft, port and starboard.

        Args:
            start_idx (int): Starting index in coordinate sequence for line
            end_idx (int): Ending index in coordinate sequence for line

        Returns:
            LineString: wind-centric subsequence of the polygon
        """

        # If the start index is greater than the end index, then we need to roll
        # through the end of the array and concatenate the to segments
        if start_idx > end_idx:
            seg_a = self.coords[start_idx:]
            seg_b = self.coords[:end_idx+1]
            line = np.concatenate([seg_a, seg_b])

        # Otherwise, we can grab the entire substring in one go
        else:
            line = self.coords[start_idx:end_idx+1]

        # Convert to shapely LineString object and return
        return LineString(line)

    def _get_anchor(self, dimension: int, side='lower') -> int:
        """Compute anchor point indecies

        Args:
            dimension (int): Dimension to extract anchor from (x or y)
            side (str, optional): Lower or upper side of the burn unit. Defaults to 'lower'.

        Returns:
            int: Index of anchor point in the polygon coordinate sequence
        """

        # Condtionally extract minimum and maximum anchor point in the linear
        # ring for the specified dimension
        if side == 'lower':
            idx = np.where(self.coords[:, dimension] ==
                           self.coords[:, dimension].min())[0]
        else:
            idx = np.where(self.coords[:, dimension] ==
                           self.coords[:, dimension].max())[0]

        # If more than one anchor, select the most upwind anchor
        if len(idx) > 1:
            idx = idx[np.argmax(self.coords[idx, 0])]
        else:
            idx = idx[0]

        # Convert to shapely Point geometry and return
        return idx
