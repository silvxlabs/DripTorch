"""
Pattern generator for ring firing
"""

# Core imports
import warnings

# Internal imports
from ._base import FiringBase
from ..unit import BurnUnit
from ..personnel import IgnitionCrew
from ..pattern import Pattern
from ..warnings import CrewSizeWarning


class Ring(FiringBase):
    """Ring firing involves two igniters walking along the boundary of the firing area from the
    downwind to the upwind side of the unit

    Parameters
    ----------
    burn_unit : BurnUnit
        Area bounding the ignition paths
    ignition_crew : IgnitionCrew
        Ignition crew assigned to the burn
    """

    def __init__(self, burn_unit: BurnUnit, ignition_crew: IgnitionCrew):

        # Check the number of igniters in the ignition crew; should be two
        if len(ignition_crew) < 2:
            ignition_crew = IgnitionCrew.clone_igniter(ignition_crew[0], 2)
            warnings.warn(CrewSizeWarning(CrewSizeWarning.cloning_first))
        elif len(ignition_crew) > 2:
            ignition_crew = IgnitionCrew.from_list(ignition_crew[:2])
            warnings.warn(CrewSizeWarning(CrewSizeWarning.only_using_two))
        else:  # ignition crew size == 2
            pass

        # Initialize the base class
        super().__init__(burn_unit, ignition_crew)

    def generate_pattern(self, offset: float) -> Pattern:
        """Generate a ring fire ignition patter

        Parameters
        ----------
        offset : float
            Offset in meters from the boundary that the igniter will walk

        Returns
        -------
        Pattern
            Spatiotemporal ignition pattern
        """

        return self._generate_pattern(offset=offset, sync_end_time=True, align=False)

    def _init_paths(self, paths: dict, **kwargs) -> dict:
        """Initialize spatial part of the ignition paths.

        Notes:
            Overrides the `_init_paths()` method in the base class

        Args:
            paths (dict): Empty pattern path dictionary

        Returns:
            dict: Pattern path dictionary with initial untimed paths
        """

        # Buffer the burn unit by the offset parameter
        firing_area = self._burn_unit.buffer_control_line(
            kwargs.get('offset', 0))

        # Get the port and starboard boundary segments from the buffered unit object
        port_line = firing_area.polygon_segments.port
        starboard_line = firing_area.polygon_segments.starboard

        # Reverse the port line coords so that both igniters start at the fore
        # anchor point and end at the aft anchor point
        port_line.coords = list(port_line.coords)[::-1]

        # Both igniters get assigned to the same heat and each igniter
        # path only has a single leg
        paths['heat'] = [0, 0]
        paths['igniter'] = [0, 1]
        paths['leg'] = [0, 0]
        paths['geometry'] = [port_line, starboard_line]

        return paths
