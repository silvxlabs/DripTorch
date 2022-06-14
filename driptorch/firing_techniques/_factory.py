"""
Class factory for accessing ignition pattern generators
"""

# Import all the firing technique classes
from .back import Back
from .strip import Strip
from .flank import Flank
from .ring import Ring
from .head import Head

from ..personnel import IgnitionCrew
from ..unit import BurnUnit


class FiringFactory:

    # Any new firing technique should be added to this class attribute
    techniques = {
        'back': Back,
        'strip': Strip,
        'flank': Flank,
        'ring': Ring,
        'head': Head
    }

    def __new__(self, firing_technique: str, burn_unit: BurnUnit,
                ignition_crew: IgnitionCrew) -> Strip | Flank | Ring | Head | Back:
        """Return an instance of a pattern generator

        Args:
            firing_technique (str): Firing techni Area bounding the ignition paths_description_
            ignition_crew (IgnitionCrew): Ignition crew assigned to the operation

        Returns:
            Strip | Flank | Ring | Head | Back: Pattern generator instance for the firing technique
        """

        return self.patterns[firing_technique](burn_unit, ignition_crew)


# Need to define a function here for add the class method due to Python's for-loop
# variable scoping, otherwise the method definitions get overridden (overrode? jk)
def add_technique_method(technique_name):
    def fn(cls, *args):
        return FiringFactory.techniques[technique_name](*args)
    setattr(FiringFactory, technique_name, classmethod(fn))


# Add alternative initializers to the PatternFactory class. This makes it possible
# to dot off of the class for a specific pattern (e.g. PatternFactory.strip(*args))
for technique_name in FiringFactory.techniques:
    add_technique_method(technique_name)
