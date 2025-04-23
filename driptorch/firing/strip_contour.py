"""
Pattern generator for contour following strip
"""

# Internal imports
from ._base import FiringBase
from ..unit import BurnUnit
from ..personnel import IgnitionCrew
from ..pattern import Pattern
from .._grid import Bounds
from .._distance import gdt

# External Imports
import numpy as np
from shapely.geometry import LineString, MultiLineString
from shapely.ops import substring


class StripContour(FiringBase):
    """Strip-contour firing is similar to strip firing, with the option to include
    topographic influences on the ignition paths.

    Parameters
    ----------
    burn_unit : BurnUnit
        Area bounding the ignition paths
    ignition_crew : IgnitionCrew
        Ignition crew assigned to the burn
    """

    def __init__(self, burn_unit: BurnUnit, ignition_crew: IgnitionCrew):
        """Constructor

        Parameters
        ----------
        burn_unit : BurnUnit
            Burn unit to generate pattern for
        ignition_crew : IgnitionCrew
            Ignition crew to use for pattern generation
        """
        raise NotImplementedError(
            "The StripContour firing pattern is currently unavailable due to DEM data access issues. "
            "Please use other firing pattern types like Strip or Ring instead."
        )

    def generate_pattern(self, spacing: float = 0, depth: float = 0, heat_depth: float = 0, side: str = 'right', heat_delay: float = 0, topo_scale: int = 1) -> Pattern:
        """Pattern generator for strip-contour firing

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
        topo_scale: int, optional
            Scale factor for topographic influence on ignition paths. Defaults to 1.

        Returns
        -------
        Pattern
            Spatiotemporal ignition pattern
        """

        return self._generate_pattern(spacing=spacing, depth=depth, heat_depth=heat_depth, side=side, heat_delay=heat_delay, elevation_influence=topo_scale, align=False)

    def _init_paths(self, paths: dict, **kwargs) -> dict:
        """Initialize spatial part of the ignition paths.

        Notes
        -----
        Overrides the `_init_paths()` method in the base class.

        Parameters
        ----------
        paths : dict
            Dictionary of empty ignition paths

        Returns
        -------
        dict
            Dictionary of untimed ignition paths
        """

        # Pick up some parameters from the kwargs that come from the base class generator method
        depth = kwargs['depth']
        heat_depth = kwargs['heat_depth']
        side = kwargs['side']
        elevation_influence = kwargs['elevation_influence']

        # Temporarily align the burn unit to the firing vector
        self._burn_unit._align()

        # Get the bounding box and re-align the burn unit
        bbox = self._burn_unit.bounds
        x_min, y_min, y_max = bbox[:, 0].min(
        ), bbox[:, 1].min(), bbox[:, 1].max()
        self._burn_unit._unalign()

        # Create a source line for the cost distance transform. This line
        # is the left edge of the aligned bounding box
        source_line = LineString([(x_min, y_min), (x_min, y_max)])

        # Now re-align the source line to the actually world orientiation
        # and clip it to the original burn unit extent
        source_line = self._unalign([source_line])[0]
        clip_bounds = Bounds.from_polygon(self._burn_unit.polygon).to_polygon()
        clip_bounds = self._burn_unit.dem.bounds.to_polygon()
        source_line = source_line.intersection(clip_bounds)

        # Compute the geodesic distance transform for the burn unit DEM and source line
        cost_distance = gdt(self._burn_unit.dem,
                            source_line, neighborhood_size=1, z_multiplier=elevation_influence)

        # Determine level set values for ignition path slicing
        if heat_depth == depth:
            levels = range(depth, int(np.max(cost_distance.data)), depth)
        else:
            levels = [depth]
            while levels[-1] < np.max(cost_distance.data):
                for i in range(len(self._ignition_crew) - 1):
                    levels.append(levels[-1] + depth)
                levels.append(levels[-1] + heat_depth)

        # Get the level sets
        contours = cost_distance.get_contours(levels)

        # Clip paths to the burn unit polygon and assign igniters, legs, and heats
        cur_heat = 0
        cur_igniter = 0
        direction_toggle = False if side == 'left' else True
        for i, line in enumerate(contours):

            # Clip the line to the burn unit polygon
            line = line.intersection(self._burn_unit.polygon)

            # Validate the geometry and format for temporal propagation
            if isinstance(line, LineString):
                if not line.is_empty:
                    line_list = [line]
            elif isinstance(line, MultiLineString):
                line_list = [line for line in line.geoms if not line.is_empty]
            else:
                continue

            # Alternate the starting side as we move between heats
            if direction_toggle:
                r_line_list = []
                for line in line_list[::-1]:
                    r_line_list.append(substring(line, line.length, 0))
                line_list = r_line_list

            # Add the line to the paths dictionary and assign geometry to igniter, leg, and heat
            for j, part in enumerate(line_list):
                paths['heat'].append(cur_heat)
                paths['igniter'].append(cur_igniter)
                paths['leg'].append(j)
                paths['geometry'].append(part)

            # Increment the igniter and heat and alternate the direction toggle
            cur_igniter += 1
            if (i+1) % len(self._ignition_crew) == 0:
                cur_igniter = 0
                cur_heat += 1
                direction_toggle ^= True

        return paths
