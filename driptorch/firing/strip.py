"""
Pattern generator for strip-head firing
"""

# Internal imports
from ._base import FiringBase
from ..unit import BurnUnit
from ..personnel import IgnitionCrew
from ..pattern import Pattern

# External imports
from shapely.geometry import LineString, MultiLineString
import numpy as np


class Strip(FiringBase):
    """Strip firing produces ignition paths perpendicular to the wind direction. Igniters are staggered with their heats
    and each heat alternates on which side of the unit they start.

    Parameters
    ----------
    burn_unit : BurnUnit
        Area bounding the ignition paths
    ignition_crew : IgnitionCrew
        Ignition crew assigned to the burn
    """

    def __init__(self, burn_unit: BurnUnit, ignition_crew: IgnitionCrew):

        # Initialize the base class
        super().__init__(burn_unit, ignition_crew)

    def generate_pattern(self, spacing: float = 0, depth: float = 0, heat_depth: float = 0, side: str = 'right', heat_delay: float = 0) -> Pattern:
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
            Side of the wind vector to start the ignition. Defaults to 'right'. Options are 'left' or 'right'.

        Returns
        -------
        Pattern
            Spatiotemporal ignition pattern
        """

        return self._generate_pattern(spacing=spacing, depth=depth, heat_depth=heat_depth, side=side, heat_delay=heat_delay)

    def _init_paths(self, paths: dict, **kwargs) -> dict:
        """Initialize spatial part of the ignition paths.

        Notes:
            Overrides the `_init_paths()` method in the base class.

        Args:
            paths (dict): Empty pattern path dictionary

        Returns:
            dict: Pattern path dictionary with initial untimed paths
        """

        # Get the depth parameter from the keyword args (This is required in the
        # `generate_pattern()` method of this class)
        depth = kwargs['depth']
        heat_depth = kwargs['heat_depth']
        side = kwargs['side']

        # Extract the bounding extent of the firing area
        bbox = self._burn_unit.bounds
        x_min, y_min = bbox[:, 0].min(), bbox[:, 1].min()
        x_max, y_max = bbox[:, 0].max(), bbox[:, 1].max()

        # Set up the initial start positions along the y-axis
        # If no heat depth is specified, then we have constant spacing between igniters and heats
        if not heat_depth:
            x_range = np.arange(x_min + depth, x_max, depth)
        # If a heat depth is specified, then we have constant spacing between igniters,
        # but potentially a different spacing between heats.
        else:
            x_range = []
            cur_x = x_min + depth
            i = 0
            while cur_x < x_max:
                x_range.append(cur_x)
                if (i+1) % len(self._ignition_crew) == 0:
                    cur_x = x_range[i] + heat_depth
                else:
                    cur_x = x_range[i] + depth
                i += 1

        # Initialize loop control parameters
        cur_heat = 0
        cur_igniter = 0
        direction_toggle = False if side == 'left' else True

        # For each start position, build a path and assign to a heat and igniter
        for i, x in enumerate(x_range):

            # Each heat alternates direction
            if direction_toggle:
                line = LineString(((x, y_min), (x, y_max)))
            else:
                line = LineString(((x, y_max), (x, y_min)))

            # Clip the line to the firing area
            line = line.intersection(self._burn_unit.polygon)

            # Get lines or multipart lines in the same structure for looping below
            if isinstance(line, LineString):
                line_list = [line]
            elif isinstance(line, MultiLineString):
                line_list = list(line.geoms)
            # Edge case: In rare cases, the line along the top of the envelope becomes a point following
            # the intersection (pretty sure this is a numerical precision issue). In this case, we need to
            # just skip this path.
            else:
                continue

            # Assign the path to a heat, igniter and leg
            for j, part in enumerate(line_list):
                paths['heat'].append(cur_heat)
                paths['igniter'].append(cur_igniter)
                paths['leg'].append(j)
                paths['geometry'].append(part)

            # Update loop control parameters
            cur_igniter += 1
            if (i+1) % len(self._ignition_crew) == 0:
                cur_igniter = 0
                cur_heat += 1
                direction_toggle ^= True

        return paths
