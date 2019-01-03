from collections import OrderedDict
from enum import Enum, unique
from fractions import Fraction
from functools import wraps
from typing import Union, get_type_hints


def ensure_simple_return_type(func):
    """A function decorator that uses the type annotation of the return value to convert to this type.

    @ensure_simple_return_type
    def test(alpha) -> int:
        return alpha + 1.5

    alpha(1) == int(2.5)"""

    @wraps(func)
    def inner(*args, **kwargs):
        return get_type_hints(func)['return'](func(*args, **kwargs))

    return inner


class CheaperFraction(Fraction):
    """A version of Fraction that has a faster hash function and renewal."""

    def __new__(cls, numerator=0, denominator=None, *, _normalize=True):
        if numerator.__class__ == cls:
            return numerator

        return super().__new__(cls, numerator=numerator, denominator=denominator, _normalize=_normalize)

    def __hash__(self) -> int:
        n = 2 * self._numerator
        if n < 0:
            n = -n + 1
        d = self.denominator
        return ((n + d) * (n + d + 1) + d) // 2


class Invariant(CheaperFraction):
    def __new__(cls, *args, **kwargs):
        result = super().__new__(cls, *args, **kwargs)
        result.__class__.__new__ = None

        return result

    def _identity(self, *_, **__):
        return self

    def hash(self):
        return hash(self.__class__.__name__)

    __add__, __radd__ = _identity, _identity
    __sub__, __rsub__ = _identity, _identity
    __mul__, __rmul__ = _identity, _identity
    __truediv__, __rtruediv__ = _identity, _identity


class BPM(CheaperFraction):
    """Beats-per-Minute, a unit of frequency used to define the rate of row advancement"""

    @property
    def measures_per_second(self) -> CheaperFraction:
        return CheaperFraction(Fraction(240, self))

    @property
    def rows_per_second(self) -> CheaperFraction:
        return CheaperFraction(self.measures_per_second * 192)


class Measure(CheaperFraction):
    """A positional continuous unit of time in charts, it composes a chart.

    Equivalent to Fraction."""
    pass


class Beat(CheaperFraction):
    """A positional continuous unit of time in charts, and is a part of a measure.

    Equivalent to Fraction.

    As time signature changes are not used and don't work in SM in general,
    Beat and Measure are equivalent and it's recommended to stick to Measure for positioning."""

    @property
    def as_measure(self) -> Measure:
        return Measure(self * Fraction(1, 4))


class LocalPosition(CheaperFraction):
    """A discrete position within a measure.

    Equivalent to Fraction.

    For SM and its derivatives the following constraints apply:
    0 <= LocalPosition < 1,
    1 <= LocalPosition.denominator <= 192"""
    pass


class GlobalPosition(CheaperFraction):
    """A discrete position within a chart, in measures.

    Equivalent to Fraction.

    For SM and its derivatives the following constraints apply:
    0 <= GlobalPosition
    1 <= GlobalPosition.denominator <= 192"""

    @property
    def measure(self) -> int:
        return int(self.real)

    @property
    def local_position(self) -> LocalPosition:
        return LocalPosition(self - self.measure)

    @property
    def is_null(self) -> bool:
        return self < 0


class Time(CheaperFraction):
    """A continuous unit of real time, in seconds."""

    @property
    def limited_precision(self) -> 'Time':
        """Time, but the precision is up-to 0.001."""
        return Time(round(self, 3))


class PositionInvariant(GlobalPosition, Invariant):
    pass


PositionInvariant = PositionInvariant()


class TimeInvariant(Time, Invariant):
    pass


TimeInvariant = TimeInvariant()


class DeltaInvariant(Time, Invariant):
    pass


DeltaInvariant = DeltaInvariant()


@unique
class NoteObject(Enum):
    """A possible SM object within a chart, the value being what character is used in SM files for this object,
    except ROLL_END"""
    EMPTY_LANE = '0'
    TAP_OBJECT = '1'
    HOLD_START = '2'
    HOLD_ROLL_END = '3'
    ROLL_START = '4'
    MINE = 'M'
    FAKE = 'F'
    LIFT = 'L'

    HOLD_BODY = 'H'
    ROLL_BODY = 'R'

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


NullGlobalPosition = GlobalPosition(-1)


def make_ordered_set(iterable):
    return tuple(OrderedDict((anything, None) for anything in iterable).keys())
