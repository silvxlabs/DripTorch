"""
Burn operation personnel
"""

# Core imports
from __future__ import annotations
import copy
import json
import warnings

# Internal imports
from .errors import *
from .warnings import IgniterWarning


class Igniter:
    """An igniter is anything with a velocity and ignition interval, like a person
    carrying a drip torch or a drone dispatching DAIDs.

    Parameters
    ----------
    velocity : float
        Igniter velocity in meters per second
    gap_length : float, optional
        Length in meters between ignitions. Defaults to None.
    dash_length : float, optional
        Length in meters of an ignition line. Defaults to None.

    Notes
    -----
    When both `gap_length` and `dash_length` are `None`, the igniter will produce a continuous line of fire.
    To configure a point igniter, leave `dash_length` as `None` and set `gap_length` to the desired distance 
    between ignition points. To configure a dash igniter, set `dash_length` to the desired length of the fire
    dashes. When configuring a dash igniter, if the `gap_length` is None, the gap between dashes will be the same
    as the dash length. Otherwise, the distance between dashes will be the specified `gap_length`.

    Examples
    --------
    >>> # Create a continuous line igniter
    >>> line_igniter = driptorch.Igniter(1.8)

    >>> # Create a dash igniter with equal dashes and gaps
    >>> equal_dash_igniter = driptorch.Igniter(1.8, dash_length=10)

    >>> # Create a dash igniter with unequal dashes and gaps
    >>> unequal_dash_igniter = driptorch.Igniter(1.8, gap_length=10, dash_length=20)

    >>> # Create a point igniter
    >>> point_igniter = driptorch.Igniter(1.8, gap_length=10)

    """

    def __init__(self, velocity: float, gap_length: float = None, dash_length: float = None):

        if velocity >= 2.5:
            warnings.warn(IgniterWarning(IgniterWarning.velocity_warning))

        self.velocity = velocity
        self.gap_length = gap_length
        self.dash_length = dash_length

    @classmethod
    def from_json(cls, json_string: str) -> Igniter:
        """
        Create an igniter from a JSON string

        Parameters
        ----------
        json_string : str
            JSON string of an igniter

        Returns
        -------
        Igniter
            Igniter object
        """

        return cls(**json.loads(json_string))

    def to_json(self) -> str:
        """
        Convert an igniter to a JSON string

        Returns
        -------
        str
            JSON string of an igniter
        """

        return json.dumps(self.__dict__)

    def copy(self) -> Igniter:
        """Sometimes we need to copy a particular Igniter because they're so good
        at what they do.

        Returns
        -------
        Igniter
            A copy of the igniter
        """

        return copy.copy(self)


class IgnitionCrew:
    """
    An ignition crew is a collection of igniters.

    Parameters
    ----------
    same_velocity : bool, optional
        Whether all igniters in the crew must have the same velocity. Defaults to True.
    """

    def __init__(self, same_velocity: bool = True):

        self._same_velocity = same_velocity
        self._velocity_req = None

        self._igniters = []

    @classmethod
    def from_list(cls, igniters: list[Igniter], **kwargs) -> IgnitionCrew:
        """Alternate constructor for building an ignition crew from a list of igniters

        Parameters
        ----------
        igniters : list[Igniter]
            List of igniters to add to the crew
        **kwargs
            Keyword arguments to pass to the IgnitionCrew constructor

        Returns
        -------
        IgnitionCrew
            IgnitionCrew object
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

        Parameters
        ----------
        igniter : Igniter
            Igniter to clone
        clones : int
            Number of clones to create
        **kwargs
            Keyword arguments to pass to the IgnitionCrew constructor

        Returns
        -------
        IgnitionCrew
            IgnitionCrew object
        """

        igniters = [igniter.copy() for _ in range(clones)]

        return cls.from_list(igniters, **kwargs)

    @classmethod
    def from_json(cls, json_str: str) -> IgnitionCrew:
        """Create an IgnitionCrew from a JSON string.

        Parameters
        ----------
        json_str : str
            JSON string of an IgnitionCrew

        Returns
        -------
        IgnitionCrew
            IgnitionCrew object
        """

        # Load the JSON string into a dictionary
        crew_dict = json.loads(json_str)

        # Create an ignition crew object
        return IgnitionCrew.from_list([Igniter(**igniter) for igniter in crew_dict['igniters']],
                                      same_velocity=crew_dict['same_velocity'])

    def add_igniter(self, igniter: Igniter):
        """Add an igniter to the crew

        Parameters
        ----------
        igniter : Igniter
            Igniter to add to the crew

        Raises
        ------
        IgniterVelocityError
            If the igniter's velocity does not match the crew's velocity requirement
        """

        # Check the igniter's velocity
        self._validate_velocity(igniter.velocity)

        # If the validator didn't raise an exception, then add the igniter to the crew
        self._igniters.append(igniter)

    def to_json(self) -> str:
        """Convert the IgnitionCrew to a JSON string.

        Returns
        -------
        str
            JSON string of an IgnitionCrew
        """

        # Create a dictionary to hold the crew's attributes and encode to JSON
        return json.dumps({'same_velocity': self._same_velocity,
                           'igniters': [igniter.__dict__ for igniter in self._igniters]})

    def _validate_velocity(self, velocity: float):
        """Private helper method to validate the velcity of the candidate igniter
        against the velocity requirement of the crew.

        Parameters
        ----------
        velocity : float
            Velocity of the candidate igniter

        Raises
        ------
        IgniterVelocityError
            If the candidate igniter's velocity does not match the crew's velocity requirement
        """

        if self._same_velocity:
            if self._velocity_req:
                if velocity != self._velocity_req:
                    raise IgniterError(IgniterError.unequal_velocities)
            else:
                self._velocity_req = velocity

    def __getitem__(self, index):

        return self._igniters[index]

    def __len__(self):

        return len(self._igniters)

    def __iter__(self):

        for i in range(self.__len__()):
            yield self._igniters[i]
