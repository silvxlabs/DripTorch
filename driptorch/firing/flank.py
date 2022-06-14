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
from shapely.geometry import LineString, MultiLineString


class Flank(FiringBase):

    def __init__(self, burn_unit: BurnUnit, ignition_crew: IgnitionCrew):
        """Constructor

        Args:
            burn_unit (BurnUnit): Area bounding the ignition paths
            ignition_crew (IgnitionCrew): Ignition crew assigned to the burn
        """

        # Initialize the base class
        super().__init__(burn_unit, ignition_crew)

    def generate_pattern(self, depth: float) -> Pattern:
        """Generate a flank fire ignition pattern

        Args:
            depth (float): Horizontal distance in meters between igniters and heats

        Returns:
            Pattern: Spatiotemporal ignition pattern
        """

        return self._generate_pattern(depth=depth)

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

        # Extract the bounding extent of the firing area
        bbox = self._burn_unit.get_bounds()
        x_min, y_min = bbox[:, 0].min(), bbox[:, 1].min()
        x_max, y_max = bbox[:, 0].max(), bbox[:, 1].max()

        # Set up the initial start positions along the y-axis
        y_range = np.arange(y_min + depth, y_max, depth)

        # Initialize loop control parameters
        cur_heat = 0
        cur_igniter = 0

        # For each start position, build a path and assign to a heat and igniter
        for i, y in enumerate(y_range):

            # Build the path and clip to firing area boundary
            line = LineString(((x_min, y), (x_max, y)))
            line = line.intersection(self._burn_unit.polygon)

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
