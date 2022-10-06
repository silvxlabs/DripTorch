"""
Burn operation personnel
"""

# Core imports
from __future__ import annotations
import copy
import json

# Internal imports
from .errors import *


class Igniter:
    """An igniter is anything with a velocity and ignition interval, like a person
    carrying a drip torch or a drone dispatching DAIDs.
    """

    def __init__(self, velocity: float, interval: float, interval_units: str = 'meters'):
        """Constructor computes and stores the interval in ignitions per meter (ipm)
        and ignitions per second (ips).

        Args:
            velocity (float): Speed of the igniter (meters/second)
            interval (float): Ignition interval in ipm (ignitions per meter) or ips (ignitions per second).
                Use the `interval_units` parameter to specifiy meters or seconds. An interval of 0 specifies
                a solid ignition line, while a negative value denotes a dashed ignition line and positve a
                dotted ignition line.
            interval_units (str, optional): Units for the ignition interval, must be "meters" or "seconds".
                Defaults to 'meters'.
        """

        self.velocity = velocity
        self.interval_units = interval_units

        # Solid ignition line
        if interval == 0:
            self.interval = 0

        # Compute ipm and ips for dashes and dots
        elif interval_units == 'seconds':
            self.interval = 1.0 / (interval / velocity)
        else:
            self.interval = 1.0/interval

    @classmethod
    def from_json(cls, json_str: str) -> Igniter:
        """Create an Igniter from a JSON string.

        Args:
            json_str (str): JSON string

        Returns:
            driptorch.Igniter: Igniter object
        """

        return Igniter(**json.loads(json_str))

    def copy(self) -> Igniter:
        """Sometimes we need to copy a particular Igniter because they're so good
        at what they do.

        Returns:
            driptorch.Igniter: A copy of the this Ignitor object
        """

        return copy.copy(self)

    def to_json(self) -> str:
        """Convert the Igniter to a JSON string.

        Returns:
            str: JSON string
        """

        return json.dumps(self.__dict__)


class IgnitionCrew:
    """
    An ignition crew is a collection of igniters. Sometime you may want your igniters
    to all have the same velocity and/or interval. You can specifiy these constraints
    in the constructor.
    """

    def __init__(self, same_velocity: bool = True, same_interval: bool = True):
        """Constructor

        Args:
            same_velocity (bool, optional): True requires all igniters of an instance
                to have equal velocities. Defaults to True.
            same_interval (bool, optional): True requires all igniter of an instance
                to have equal interval values. Defaults to True.
        """

        self._same_velocity = same_velocity
        self._same_interval = same_interval
        self._velocity_req = None
        self._interval_req = None

        self._igniters = []

    @classmethod
    def from_list(cls, igniters: list[Igniter], **kwargs) -> IgnitionCrew:
        """Alternate constructor for building an ignition crew from a list of igniters

        Args:
            igniters (List[Igniter]): List of Igniter objects

        Returns:
            IgnitionCrew: An IgnitionCrew object with igniters from provided list
        """

        ignition_crew = cls(**kwargs)

        # Add igniters from provided list to the crew object
        for igniter in igniters:
            ignition_crew.add_igniter(igniter)

        return ignition_crew

    @classmethod
    def clone_igniter(cls, igniter: Igniter, clones: int, **kwargs) -> IgnitionCrew:
        """Alternate constructor for building an ignition crew by cloning a given
        igniters `n` times.

        Args:
            igniter (Igniter): The Igniter object to clone
            clones (int): Number of clones (number of igniters in crew)

        Returns:
            IgnitionCrew: An IgnitionCrew object with `n` clones of the specified Igniter
        """

        igniters = [igniter.copy() for _ in range(clones)]

        return cls.from_list(igniters, **kwargs)

    @classmethod
    def from_json(cls, json_str: str) -> IgnitionCrew:
        """Create an IgnitionCrew from a JSON string.

        Args:
            json_str (str): JSON string

        Returns:
            driptorch.IgnitionCrew: IgnitionCrew object
        """

        # Load the JSON string into a dictionary
        crew_dict = json.loads(json_str)

        # Create an ignition crew object
        return IgnitionCrew.from_list([Igniter(**igniter) for igniter in crew_dict['igniters']],
                                      same_velocity=crew_dict['same_velocity'],
                                      same_interval=crew_dict['same_interval'])

    def add_igniter(self, igniter: Igniter):
        """Add an igniter to the crew

        Args:
            igniter (Igniter): Igniter object to add to the crew
        """

        # Check the igniter's velocity
        self._validate_velocity(igniter.velocity)
        self._validate_interval(igniter.interval)

        # If the validator didn't raise an exception, then add the igniter to the crew
        self._igniters.append(igniter)

    def to_json(self) -> str:
        """Convert the IgnitionCrew to a JSON string.

        Returns:
            str: JSON string
        """

        # Create a dictionary to hold the crew's attributes and encode to JSON
        return json.dumps({'same_velocity': self._same_velocity,
                           'same_interval': self._same_interval,
                           'igniters': [igniter.__dict__ for igniter in self._igniters]})

    def _validate_velocity(self, velocity: float):
        """Private helper method to validate the velcity of the candidate igniter
        against the velocity requirement of the crew.

        Args:
            velocity (float): Velocity of the candidate igniter

        Raises:
            IgniterError: Exception raised if igniter's velocity is invalid
        """

        if self._same_velocity:
            if self._velocity_req:
                if velocity != self._velocity_req:
                    raise IgniterError(IgniterError.unequal_velocities)
            else:
                self._velocity_req = velocity

    def _validate_interval(self, interval: float):
        """Private helper method to validate the interval of the candidate igniter
        against the interval requirement of the crew.

        Args:
            interval (float): Ignition interval of the candidate igniter

        Raises:
            IgniterError: Exception raised if igniter's interval is invalid
        """

        if self._same_interval:
            if self._interval_req:
                if interval != self._interval_req:
                    raise IgniterError(IgniterError.unequal_intervals)
            else:
                self._interval_req = interval

    def __getitem__(self, index):

        return self._igniters[index]

    def __len__(self):

        return len(self._igniters)

    def __iter__(self):

        for i in range(self.__len__()):
            yield self._igniters[i]
