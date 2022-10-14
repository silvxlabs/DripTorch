"""
Pattern generator for inferno firing
"""

# Internal imports
from ..unit import BurnUnit
from ..pattern import Pattern

# External imports
import numpy as np
from shapely.geometry import LineString, MultiLineString


class Inferno:
    """This technique is set up differently than the other firing techniques. It doesn't
    inherit from the FiringBase class. Time does not need to be propagated so we
    don't pass to the Temporal Propagator.

    Parameters
    ----------
    burn_unit : BurnUnit
        Area bounding the ignition paths
    """

    def __init__(self, burn_unit: BurnUnit):

        # Store the burn unit. Wind direction doesn't matter for this technique, so
        # no need to align the burn unit to the wind.
        self._burn_unit = burn_unit

    def generate_pattern(self) -> Pattern:
        """Generate an inferno ignition pattern

        Returns
        -------
        Pattern
            Spatiotemporal ignition pattern
        """

        paths = Pattern.empty_path_dict()
        paths['times'] = []

        # Extract the bounding extent of the firing area
        bbox = self._burn_unit.bounds
        x_min, y_min = bbox[:, 0].min(), bbox[:, 1].min()
        x_max, y_max = bbox[:, 0].max(), bbox[:, 1].max()

        # Initialize the starting points of the paths at each meter along the y-axis
        y_range = np.arange(y_min, y_max, 1)

        # For each starting point, create a path to the edge of the burn unit
        for y in y_range:

            # Build the path and clip to firing area boundary
            line = LineString(((x_min, y), (x_max, y)))
            line = line.intersection(self._burn_unit.polygon)

            # Handle post-intersection geometries
            if isinstance(line, LineString):
                line = [line]
            elif isinstance(line, MultiLineString):
                line = list(line.geoms)
            else:
                continue

            # Assign heat, igniter, leg, geometry and times to the path
            # The start time and end time are both zero and the same for all paths
            for j, part in enumerate(line):
                paths['heat'].append(0)
                paths['igniter'].append(0)
                paths['leg'].append(j)
                paths['geometry'].append(part)
                paths['times'].append([1.0, 1.0])

        return Pattern.from_dict(paths, epsg=self._burn_unit.utm_epsg)
