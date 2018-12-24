from enum import Enum, unique
from fractions import Fraction
from typing import Union

__all__ = ['BPM',
           'Measure', 'Beat',
           'LocalPosition', 'GlobalPosition',
           'NoteObject',
           'Snap']


class BPM(Fraction):
    """Beats-per-Minute, a unit of frequency used to define the rate of row advancement"""

    @property
    def measures_per_second(self):
        return Fraction(240, self)

    @property
    def rows_per_second(self):
        return self.measures_per_second * 192


class Measure(Fraction):
    """A positional continuous unit of time in charts, it composes a chart.

    Equivalent to Fraction."""
    pass


class Beat(Fraction):
    """A positional continuous unit of time in charts, and is a part of a measure.

    Equivalent to Fraction.

    As time signature changes are not used and don't work in SM in general,
    Beat and Measure are equivalent and it's recommended to stick to Measure for positioning."""

    def as_measure(self) -> Measure:
        return Measure(self * Fraction(1, 4))


class LocalPosition(Fraction):
    """A discrete position within a measure.

    Equivalent to Fraction.

    For SM and its derivatives the following constraints apply:
    0 <= LocalPosition < 1,
    1 <= LocalPosition.denominator <= 192"""
    pass


class GlobalPosition(Fraction):
    """A discrete position within a chart, in measures.

    Equivalent to Fraction.

    For SM and its derivatives the following constraints apply:
    0 <= GlobalPosition
    1 <= GlobalPosition.denominator <= 192"""

    @property
    def measure(self):
        return int(self.real)


class Time(Fraction):
    """A continuous unit of real time, in seconds."""
    pass


@unique
class NoteObject(Enum):
    """A possible SM object within a chart, the value being what character is used in SM files for this object."""
    EMPTY_LANE = '0'
    TAP_OBJECT = '1'
    HOLD_START = '2'
    HOLD_END = '3'
    ROLL_START = '4'
    ROLL_END = '5'
    MINE = 'M'
    FAKE = 'F'
    LIFT = 'L'

    @classmethod
    def get_from_character(cls, character: str) -> 'NoteObject':
        return cls._value2member_map_[character]


class Snap(Enum):
    """A utility enumeration for commonly used snaps in SM."""
    RED = 4
    BLUE = 8
    VIOLET = 12
    YELLOW = 16
    PINK = 24
    ORANGE = 32
    CYAN = 48
    GREEN = 64
    GRAY = 192

    @classmethod
    def from_position(cls, position: Union[LocalPosition, GlobalPosition]) -> 'Snap':
        try:
            cls._value2member_map_[1]
        except KeyError:
            cls._value2member_map_[1] = cls.RED
            cls._value2member_map_[2] = cls.RED
            cls._value2member_map_[3] = cls.VIOLET
            cls._value2member_map_[6] = cls.VIOLET

        return cls._lookup.get(position.denominator, cls.GRAY)
