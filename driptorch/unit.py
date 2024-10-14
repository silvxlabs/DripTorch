"""
BurnUnit
--------
Reading and manipulating a burn unit geometry and splitting
the boundary to firing-centric segments
"""

# Core imports
from __future__ import annotations
import copy

# Internal imports
from .io import Projector, write_geojson, read_geojson_polygon
from ._grid import Grid, Bounds, AlbersConusDEM

# External imports
import numpy as np
from shapely.geometry import Polygon, LineString, Point, MultiPolygon
from shapely import affinity


class BurnUnit:
    """
    A burn unit is a polygon that is split into segments based on the firing direction.

    Parameters
    -----------
    polygon : shapely.Polygon
        Shapely polygon geometry object
    firing_direction :  float
        firing direction (degrees)
    utm : int
        UTM EPSG code of spatial data. If not provided it is assumed
        that coordinates are in 4326 and will be converted to UTM. Defaults to None.
    """

    def __init__(self,
                 polygon: Polygon,
                 firing_direction: float,
                 utm_epsg: int = None) -> None:

        # Initialize the dem attribute to None so we can detect if it has been fetched or not
        self.dem = None

        # Set the global EPSG source
        if not utm_epsg:
            utm_epsg, polygon = Projector.wgs84_to_utm(polygon)

        # Store instance attributes
        self.utm_epsg = utm_epsg
        self.polygon = polygon
        self.firing_direction = firing_direction
        self.centroid = polygon.centroid
        self.polygon_segments = PolygonSplitter()

        # Compute the angle used to rotate the unit s.t. the firing direction
        # is congruent with the positive x-axis
        self.firing_alignment_angle = (self.firing_direction - 90) % 360

        # Align the unit, run the boundary splitting algorithm for
        # anchors and segs, and then unalign
        self._align()
        self.polygon_segments.split(self.polygon)
        self._unalign()

    @classmethod
    def from_json(cls, geojson: dict, firing_direction: float, **kwargs) -> BurnUnit:
        """Alternative constructor used to create a BurnUnit object from
        a GeoJSON dictionary.

        Parameters
        ----------
        geojson : dict
            GeoJSON dictionary
        firing_direction : float
            firing direction (degrees)
        epsg : int
            EPSG code of the input GeoJSON. Defaults to 4326.

        Returns
        -------
        BurnUnit
            New instance of a BurnUnit
        """

        # Read the GeoJSON as a shapely polygon
        polygon = read_geojson_polygon(geojson)

        return cls(polygon, firing_direction, **kwargs)

    def to_json(self, **kwargs) -> dict:
        """Returns a GeoJSON representation of the ``BurnUnit`` as a string

        Parameters
        ----------
        **kwargs
            Keyword arguments passed to ``write_geojson``

        Examples
        --------
        >>> from shapely.geometry import Polygon
        >>> polygon = Polygon([(-114.478, 47.163), (-114.471, 47.163), (-114.471, 47.167), (-114.478, 47.167)])

        >>> burn_unit = driptorch.BurnUnit(polygon, firing_direction=270)
        >>> burn_unit.to_json()
        '{'type': 'FeatureCollection', 'features': [{'type': 'Feature', 'properties': {}, \
        'geometry': {'type': 'Polygon', 'coordinates': (((-114.478, 47.163), (-114.471, 47.16299999999998), \
        (-114.471, 47.16699999999999), (-114.478, 47.16699999999999), (-114.478, 47.163)),)}}]}'

        """

        return write_geojson([self.polygon], src_epsg=self.utm_epsg, **kwargs)

    def _align(self):
        """Align the unit and boundary segs to the firing
        """

        if self.firing_alignment_angle:
            self.polygon = affinity.rotate(
                self.polygon, self.firing_alignment_angle, self.centroid)
            self.polygon_segments.rotate(
                self.firing_alignment_angle, self.centroid)

    def _unalign(self):
        """Revert the unit and boundary seg to their origional orientation
        """

        if self.firing_alignment_angle:
            self.polygon = affinity.rotate(
                self.polygon, -self.firing_alignment_angle, self.centroid)
            self.polygon_segments.rotate(
                -self.firing_alignment_angle, self.centroid)

    def copy(self) -> BurnUnit:
        """Utility method for copying a BurnUnit instance

        Returns
        -------
        BurnUnit
            New instance of a BurnUnit
        """

        return copy.copy(self)

    def buffer_control_line(self, width: float) -> BurnUnit:
        """Shrink the burn unit to account for the width of the control line

        Parameters
        ----------
        distance : width
            Width of the control line (meters)

        Returns
        -------
        BurnUnit
            New instance of a BurnUnit
        """

        # Use shapely's buffer method on the polygon
        buffered_polygon = self.polygon.buffer(-width)

        return BurnUnit(buffered_polygon, self.firing_direction, utm_epsg=self.utm_epsg)

    def buffer_downwind(self, width: float) -> BurnUnit:
        """Create a downwind blackline buffer

        Parameters
        ----------
        width : float
            Width of downwind buffer (meters)

        Returns
        -------
        BurnUnit
            New instance of a BurnUnit
        """

        # Buffer the fore line by the blackline width parameter
        fore_line_buffer = self.polygon_segments.fore.buffer(
            width, cap_style=3)

        # Now take the difference between the current firing area and the fore line
        # buffer to cut out the downfiring blackline area
        buffered_polygon = self.polygon.difference(fore_line_buffer)

        if isinstance(buffered_polygon, MultiPolygon):
            print('WARNING: downwind buffered geometry is multipolygon; using only largest polygon.')
            multi = list(buffered_polygon)
            max_area = -999999
            for poly in multi:
                if poly.area > max_area:
                    max_area = poly.area
                    max_poly = poly

            buffered_polygon = max_poly

        return BurnUnit(buffered_polygon, self.firing_direction, utm_epsg=self.utm_epsg)

    def difference(self, burn_unit: BurnUnit) -> BurnUnit:
        """Return a burn unit instance that is the difference between
        this burn unit and another. Useful for obtaining the blackline
        area for clearing fuels.

        Parameters
        ----------
        burn_unit : BurnUnit
            The BurnUnit instance to difference against

        Returns
        -------
        BurnUnit
            A new instance of a BurnUnit
        """

        # Use shapely's set-theorectic difference method
        polygon_difference = self.polygon.difference(burn_unit.polygon)

        return BurnUnit(polygon_difference, self.firing_direction, utm_epsg=self.utm_epsg)

    def fetch_dem(self, resolution=3) -> None:
        """Extract elevation data for the burn unit from cloud-hosted CONUS DEM
        """

        # TODO: #146 Use minimum bounding circle to determine DEM extraction padding

        # Setup a projector to get the burn unit's polygon in Albers for extract the
        # USGS 3DEP CONUS DEM
        projector = Projector(self.utm_epsg, 5070)

        # Get the bounds of the input polygon then construct a polygon from the bounds
        # and reproject to Albers
        src_bounds = Bounds.from_polygon(self.polygon)
        src_bounds.west -= 200
        src_bounds.east += 200
        src_bounds.north += 200
        src_bounds.south -= 200
        src_bounds_polygon = src_bounds.to_polygon()
        albers_bounds_polygon = projector.forward(src_bounds_polygon)

        # Now we get the bounds of the reprojected source polygon bounds to ensure
        # we cover the entire area for the interpolated reprojection
        albers_bounds = Bounds.from_polygon(albers_bounds_polygon)

        # Instantiate the Albers CONUS DEM and extract the subarray by the bounds
        albers_dem_conus = AlbersConusDEM()
        albers_sub_dem = albers_dem_conus.extract_by_bounds(
            albers_bounds, padding=3)

        # Reproject from albers to UTM and store as burn unit instance attribute
        self.dem = albers_sub_dem.reproject(
            self.utm_epsg, src_bounds, dst_res=resolution)

    @property
    def bounds(self) -> np.ndarray:
        """Returns the bounding box of the unit

        Returns
        -------
        numpy.ndarray
            Bounding box of the unit
        """

        return np.array(self.polygon.envelope.exterior.coords[:-1])


class PolygonSplitter:

    def __init__(self):
        """Constructor
        """

        # We're just setting these to None to start with so they can be pumped
        # through firing alignment before we compute them
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
        """Split the polygon to four firing-centric segments

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
        that make up the four firing-centric parts of the burn unit: fore, aft, port and starboard.

        Args:
            start_idx (int): Starting index in coordinate sequence for line
            end_idx (int): Ending index in coordinate sequence for line

        Returns:
            LineString: firing-centric subsequence of the polygon
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

        # If more than one anchor, select the most upfiring anchor
        if len(idx) > 1:
            idx = idx[np.argmax(self.coords[idx, 0])]
        else:
            idx = idx[0]

        # Convert to shapely Point geometry and return
        return idx
