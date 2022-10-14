"""
Pattern generator for flank firing
"""

# Internal imports
from ._base import FiringBase
from ..unit import BurnUnit
from ..personnel import IgnitionCrew
from ..pattern import Pattern

# External imports
import numpy as np
from shapely.geometry import Point, MultiPoint, LineString, MultiLineString


class Flank(FiringBase):
    """Flank fire sets ignition paths in the direction of the wind.

    Parameters
    ----------
    burn_unit : BurnUnit
        Area bounding the ignition paths
    ignition_crew : IgnitionCrew
        Ignition crew assigned to the burn
    """

    def __init__(self, burn_unit: BurnUnit, ignition_crew: IgnitionCrew):
        """Constructor

        Args:
            burn_unit (BurnUnit): Area bounding the ignition paths
            ignition_crew (IgnitionCrew): Ignition crew assigned to the burn
        """

        # Initialize the base class
        super().__init__(burn_unit, ignition_crew)

    def generate_pattern(self, depth: float = None, heat_depth: float = None, side: str = 'right', time_offset_heat: float = 0) -> Pattern:
        """Generate a flank fire ignition pattern

        Parameters
        ----------
        depth : float, optional
            Depth in meters between igniters. Defaults to None.
        heat_depth : float, optional
            Depth in meters between heats. Defaults to None.
        side : str, optional
            Side of the wind vector to start the ignition. Defaults to 'right'. Options are 'left' or 'right'.

        Returns
        -------
        Pattern
            Spatiotemporal ignition pattern
        """

        return self._generate_pattern(depth=depth, heat_depth=heat_depth, side=side, return_trip=True, time_offset_heat=time_offset_heat)

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

        # If depth=None, compute depth by equally spacing ignitors. This make sense for flank
        # technique since we don't what ignitors walking back downwind in the fire
        # they just ignited.
        if not depth:
            depth = (y_max - y_min) / (len(self._ignition_crew) + 1)

        # Set up the initial start positions along the y-axis
        # If no heat depth is specified, then we have constant spacing between igniters and heats
        if not heat_depth:
            y_range = np.arange(y_min + depth, y_max, depth)
        # If a heat depth is specified, then we have constant spacing between igniters,
        # but potentially a different spacing between heats.
        else:
            y_range = []
            cur_y = y_min + depth
            i = 0
            while cur_y < y_max:
                y_range.append(cur_y)
                if (i+1) % len(self._ignition_crew) == 0:
                    cur_y = y_range[i] + heat_depth
                else:
                    cur_y = y_range[i] + depth
                i += 1

        # Flip the y_range if we're on the right side
        if side == 'left':
            y_range = y_range[::-1]

        # Initialize loop control parameters
        cur_heat = 0
        cur_igniter = 0

        # For each start position, build a path and assign to a heat and igniter
        for i, y in enumerate(y_range):

            # Build the path and clip to firing area boundary
            line = LineString(((x_min, y), (x_max, y)))
            line = line.intersection(self._burn_unit.polygon)

            # Edge case: In rare cases, the line along the top of the envelope becomes a point following
            # the intersection (pretty sure this is a numerica precision issue). In this case, we need to
            # just skip this path.
            if isinstance(line, (Point, MultiPoint)):
                continue

            # Get lines or multipart lines in the same structure for looping below
            if isinstance(line, LineString):
                line = [line]
            elif isinstance(line, MultiLineString):
                line = list(line.geoms)

            # Assign the path to a heat, igniter and leg
            for j, part in enumerate(line):
                paths['heat'].append(cur_heat)
                paths['igniter'].append(cur_igniter)
                paths['leg'].append(j)
                paths['geometry'].append(part)

            # Update loop control parameters
            cur_igniter += 1
            if (i+1) % len(self._ignition_crew) == 0:
                cur_igniter = 0
                cur_heat += 1

        return paths
