"""
Pattern generator for strip-head firing
"""

# Internal imports
from ._base import FiringBase
from ..unit import BurnUnit
from ..personnel import IgnitionCrew
from ..pattern import Pattern
from ..pattern import Pattern, TemporalPropagator

from .._grid import CostDistanceDEM
from ..contour import CostDistance


# External imports
from shapely.geometry import LineString, MultiLineString
import numpy as np
import pdb

class StripContour(FiringBase):
    """Strip firing produces ignition paths perpendicular to the firing direction. Igniters are staggered with their heats
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

    def generate_pattern(self, spacing: float = 0, depth: float = 0, heat_depth: float = 0, side: str = 'right', heat_delay: float = 0, cost_raster = False, **kwargs) -> Pattern:
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
            Side of the firing vector to start the ignition. Defaults to 'right'. Options are 'left' or 'right'.

        Returns
        -------
        Pattern
            Spatiotemporal ignition pattern
        """
        # Extract the bounding extent of the firing area
        bbox = self._burn_unit.bounds
        x_min, y_min = bbox[:, 0].min(), bbox[:, 1].min()
        x_max, y_max = bbox[:, 0].max(), bbox[:, 1].max()

        if side == 'right':
            starty,endy = y_min,y_max
        else:
            starty,endy = y_max,y_min

        start_path = np.array([
            [x_min,starty],
            [x_min,endy]
        ])

        elevation_raster = CostDistanceDEM.from_grid(self._burn_unit.dem)
        cost_distance = CostDistance(start_path,elevation_raster)
        paths,cost_raster = cost_distance.iterate(
            len(self._ignition_crew),
            depth,
            heat_depth,
            side,
            burn_unit = self._burn_unit,
            sigma = kwargs.get("sigma",0)
        )

    
        "DEBUG"
        import matplotlib.pyplot as plt
        geoms = paths["geometry"]
        geoms = [np.array(x) for x in geoms]
        colors = ['r','b','g','y','k']
        for i,line in enumerate(geoms):
            if line.shape[0] > 0:
                c = paths["igniter"][i]%len(colors)
                plt.scatter(line[:,0],line[:,1],c=colors[c])
        #plt.show()
       
        "DEBUG"
        
        # Now we can unalign the paths before passing to the propagator
        # if kwargs.get('align', True):
        #     paths['geometry'] = self._unalign(paths['geometry'])

        # Configure the propagator for pushing time through the paths
        propagator = TemporalPropagator(
            spacing,
            sync_end_time=kwargs.get('sync_end_time', False),
            return_trip=kwargs.get('return_trip', False),
        )

        # Compute arrival times for each coordinate in each path
        timed_paths = propagator.forward(
            paths, self._ignition_crew, heat_delay)

        # Hand the timed paths over to the Pattern class and return an instance

        pattern = Pattern.from_dict(timed_paths, self._burn_unit.utm_epsg)

        if cost_raster:
            return pattern,cost_raster
        else:
            return pattern