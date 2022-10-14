
# Internal imports
from ..pattern import Pattern, TemporalPropagator
from ..personnel import IgnitionCrew
from ..unit import BurnUnit

# External imports
from shapely import affinity
from shapely.geometry import LineString


class FiringBase:

    def __init__(self, burn_unit: BurnUnit, ignition_crew: IgnitionCrew):
        """Constructor

        Args:
            burn_unit (BurnUnit): Area bounding the ignition paths
            ignition_crew (IgnitionCrew): Crew assigned to the firing operation
        """

        self._burn_unit = burn_unit.copy()
        self._ignition_crew = ignition_crew

    def _generate_pattern(self, **kwargs) -> Pattern:
        """Private method that run all the common operations for initializing paths
        and timed pattern generation

        Returns:
            Pattern: Spatiotemporal ignition pattern
        """

        # Get a template dictionary for the paths object
        empty_paths = Pattern.empty_path_dict()

        # Need to wind-align the burn unit for laying out paths
        if kwargs.get('align', True):
            self._burn_unit._align()

        # Run the path initialization method
        init_paths = self._init_paths(empty_paths, **kwargs)

        # Now we can unalign the paths before passing to the propagator
        if kwargs.get('align', True):
            init_paths['geometry'] = self._unalign(init_paths['geometry'])

        # Configure the propagator for pushing time through the paths
        propagator = TemporalPropagator(
            kwargs.get('spacing', 0),
            sync_end_time=kwargs.get('sync_end_time', False),
            return_trip=kwargs.get('return_trip', False),
        )

        # Compute arrival times for each coordinate in each path
        timed_paths = propagator.forward(init_paths, self._ignition_crew,kwargs.get('time_offset_heat',0))

        # Hand the timed paths over to the Pattern class and return an instance
        return Pattern.from_dict(timed_paths, self._burn_unit.utm_epsg)

    def _init_paths(self, empty_paths: dict, **kwargs) -> dict:
        """Template method to be overloaded by the pattern generator class inheriting
        this as a base class.

        Args:
            empty_paths (dict): Pattern path dictionary

        Returns:
            dict: Pattern dictionary with initial paths (only the spatial part)
        """

        return empty_paths

    def _unalign(self, lines: list[LineString]) -> list[LineString]:
        """Helper method for unaligning the ignition paths after spatial initialization

        Args:
            geometries (list[LineString]): Wind-aligned line strings

        Returns:
            list[LineString]: Unaligned line strings
        """

        # Empty list for added the unaligned lines
        unaligned_lines = []
        for line in lines:
            unaligned_lines.append(
                affinity.rotate(
                    line, -self._burn_unit.wind_alignment_angle,
                    self._burn_unit.centroid
                )
            )

        return unaligned_lines
