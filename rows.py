from enum import IntFlag, unique
from functools import lru_cache
from itertools import permutations, product
from typing import Container, Optional, Union

from attr import attrs, evolve

from .basic_types import DeltaInvariant, GlobalPosition, LocalPosition, Measure, NoteObject, PositionInvariant, Time, \
    TimeInvariant, make_ordered_set

FULL_SET = {*NoteObject.__members__.values()}

EMPTY_LANE_SET = {NoteObject.EMPTY_LANE}
DECORATIVE_SET = EMPTY_LANE_SET | {NoteObject.FAKE, NoteObject.MINE}
LONG_NOTE_BODY_SET = {NoteObject.HOLD_BODY, NoteObject.ROLL_BODY}
LONG_NOTE_ENDS_SET = {NoteObject.HOLD_START, NoteObject.ROLL_START, NoteObject.HOLD_ROLL_END}
LONG_NOTE_SET = LONG_NOTE_ENDS_SET | LONG_NOTE_BODY_SET
JUDGE_NON_IMPORTANT_SET = DECORATIVE_SET | LONG_NOTE_BODY_SET | {NoteObject.HOLD_ROLL_END}
JUDGE_IMPORTANT_SET = FULL_SET - JUDGE_NON_IMPORTANT_SET
NON_DECORATIVE_SET = FULL_SET - DECORATIVE_SET


@attrs(frozen=True, auto_attribs=True)
class HasRow(object):
    _row: Optional['PureRow'] = None

    @staticmethod
    def _typed_evolve(target, **kwargs):
        if isinstance(target, PureRow):
            return kwargs['row']
        return evolve(target, **kwargs)

    @property
    def row(self):
        return self._row

    @property
    def row_invariant(self):
        return self._typed_evolve(self, row=RowInvariant)

    @property
    def is_empty(self) -> bool:
        return not {*self.row} - EMPTY_LANE_SET

    @property
    def is_decorative(self) -> bool:
        return not {*self.row} - DECORATIVE_SET

    @property
    def is_judge_non_important(self) -> bool:
        return not {*self.row} - JUDGE_NON_IMPORTANT_SET

    @property
    def is_pure_hold_roll_body(self):
        return not {*self.row} - (EMPTY_LANE_SET | LONG_NOTE_BODY_SET)

    @property
    def mirror(self):
        return self._typed_evolve(self, row=self.row.mirror)

    @property
    def permutative_group(self):
        return make_ordered_set(
            self._typed_evolve(self, row=PureRow(group))
            for group in permutations(self.row)
        )

    @property
    @lru_cache(None)
    def permutative_set(self):
        return frozenset(self.permutative_group)

    def switch_lanes(self, lane_map):
        return self._typed_evolve(self, row=PureRow(
            self.row[lane_map.get(lane, lane)]
            for lane, _ in enumerate(self.row)
        ))

    def find_object_lanes(self, needle_object: NoteObject):
        return {
            lane
            for lane, obj in enumerate(self.row)
            if obj is needle_object
        }

    def replace_objects(self, from_note: Union[NoteObject, Container[NoteObject]], to_note: NoteObject):
        if not isinstance(from_note, Container):
            from_note = {from_note}

        new_row = PureRow(
            obj in from_note and to_note or obj
            for obj in self.row
        )
        return self._typed_evolve(self, row=new_row)


@attrs(frozen=True, auto_attribs=True)
class HasTime(object):
    _time: Optional[Time] = None

    @property
    def time(self):
        return self._time

    @property
    def time_invariant(self):
        return evolve(self, time=TimeInvariant)

    @classmethod
    def from_two_rows(cls, from_: 'HasTime', to: 'HasTime'):
        return cls(time=to.time - from_.time)


@attrs(frozen=True, auto_attribs=True)
class HasPosition(object):
    _pos: Optional[Union[GlobalPosition, LocalPosition]] = None

    @property
    def snap(self):
        return Snap.from_row(self)

    @property
    def measure(self):
        return self.pos.measure

    @property
    def pos(self):
        return self._pos

    @property
    def position_invariant(self):
        return evolve(self, pos=PositionInvariant)

    def localize(self, window_factor=1):
        return evolve(self, pos=LocalPosition(self.pos % window_factor / window_factor))


@attrs(frozen=True, auto_attribs=True)
class HasDelta(object):
    _delta: Optional[Time] = None

    @property
    def delta(self):
        return self._delta

    @property
    def delta_invariant(self):
        return evolve(self, delta=DeltaInvariant)


class HasEvolution(object):
    def evolve(self, *args):
        return NotImplemented


class PureRow(tuple, HasRow, HasEvolution):
    """A basic class representing a row, equivalent to tuples with additional methods."""

    @classmethod
    def from_str_row(cls, row: str) -> 'PureRow':
        return PureRow(
            NoteObject.get_from_character(char)
            for char in row
        )

    @property
    def str_row(self) -> str:
        return ''.join(
            obj.value
            for obj in self.row
        )

    def __repr__(self):
        return ''.join(
            obj.value
            for obj in self.row
        )

    __str__ = __repr__

    @property
    def row(self):
        return self

    @property
    def mirror(self) -> 'PureRow':
        return PureRow(self[::-1])

    def evolve(self, local_position: LocalPosition) -> 'LocalRow':
        return LocalRow(self, local_position)


RowInvariant = PureRow([])


@attrs(frozen=True, auto_attribs=True)
class LocalRow(HasRow, HasPosition, HasEvolution):
    """A basic object representing a row within a measure."""
    _row: Optional[PureRow] = None
    _pos: Optional[LocalPosition] = None

    def evolve(self, global_measure: Measure) -> 'GlobalRow':
        return GlobalRow(self.row, GlobalPosition(self.pos + global_measure))


class TimedRow(HasRow, HasTime, HasEvolution):
    _row: Optional[PureRow] = None
    _time: Optional[Time] = None

    def evolve(self, position: GlobalPosition) -> 'GlobalTimedRow':
        return GlobalTimedRow(self.row, position, self.time)


@attrs(frozen=True, auto_attribs=True)
class GlobalRow(HasRow, HasPosition, HasEvolution):
    """A basic object representing a row within a chart."""
    _row: Optional[PureRow] = None
    _pos: Optional[GlobalPosition] = None

    def evolve(self, time: Time) -> 'GlobalTimedRow':
        return GlobalTimedRow(self.row, self.pos, time)


@attrs(frozen=True, auto_attribs=True)
class GlobalTimedRow(HasRow, HasPosition, HasTime, HasEvolution):
    """An augmented version of GlobalRow, with timing data attached to it."""
    _row: Optional[PureRow] = None
    _pos: Optional[GlobalPosition] = None
    _time: Optional[Time] = None

    def evolve(self, next_row: HasTime) -> 'GlobalDeltaRow':
        return GlobalDeltaRow(self.row, self.pos, self.time, Time(next_row.time - self.time))


@attrs(frozen=True, auto_attribs=True)
class GlobalDeltaRow(HasRow, HasPosition, HasTime, HasDelta):
    """A contextually dependent version of GlobalTimedRow,
    where `delta` is the difference in time between this and next row"""
    _row: Optional[PureRow] = None
    _pos: Optional[GlobalPosition] = None
    _time: Optional[Time] = None
    _delta: Optional[Time] = None


class Snap(int):
    @property
    def snap_value(self):
        return (
                self in (1, 2, 4) and 4 or
                self is 3 and 12 or
                self is 8 and 8 or
                self is 12 and 12 or
                self is 16 and 16 or
                self is 24 and 24 or
                self is 32 and 32 or
                self is 48 and 48 or
                self is 64 and 64 or
                192
        )

    @classmethod
    def from_row(cls, row: HasPosition):
        return cls(row.pos.denominator)


@unique
class RowFlags(IntFlag):
    NONE = 0
    SINGLE = 1 << 0
    OHT_JUMP = 1 << 1
    THT_JUMP = 1 << 2
    HAND = 1 << 3
    QUAD = 1 << 4
    HOLD = 1 << 5
    ROLL = 1 << 6
    OHT_HOLD = 1 << 7
    OHT_ROLL = 1 << 8
    THT_HOLD = 1 << 9
    THT_ROLL = 1 << 10
    RELEASE = 1 << 11

    @classmethod
    def calculate_maximum_combinations(cls):
        if not hasattr(cls, '_cached'):
            s = set()
            for potential_row in product(*(NoteObject.__members__.values(),) * 4):
                s.add(cls.from_row(PureRow(potential_row)))

            cls._cached = len(s)
        return cls._cached

    @classmethod
    def classify_row(cls, row) -> 'RowFlags':
        if len(row.row) != 4:
            print('Rows beyond 4K are not supported yet.')
            raise NotImplemented

        if row.row.count(NoteObject.EMPTY_LANE) == 4:
            return cls.NONE

        taps = row.row.count(NoteObject.TAP_OBJECT)
        holds = row.row.count(NoteObject.HOLD_START)
        rolls = row.row.count(NoteObject.ROLL_START)

        klass = RowFlags.NONE

        oht_jump = (NoteObject.TAP_OBJECT,) * 2
        oht_hold = (NoteObject.HOLD_START,) * 2
        oht_roll = (NoteObject.ROLL_START,) * 2

        if taps == 1:
            klass |= cls.SINGLE

        elif taps == 2:
            oht = row.row[:2] == oht_jump or row.row.mirror[:2] == oht_jump
            if oht:
                klass |= cls.OHT_JUMP
            else:
                klass |= cls.THT_JUMP

        elif taps == 3:
            klass |= cls.HAND

        elif taps == 4:
            klass |= cls.QUAD

        if holds == 0:
            pass

        elif holds == 1:
            klass |= cls.HOLD

        elif holds == 2:
            oht = row.row[:2] == oht_hold or row.row.mirror[:2] == oht_hold
            if oht:
                klass |= cls.OHT_HOLD
            else:
                klass |= cls.THT_HOLD
        else:
            klass |= cls.THT_HOLD

        if rolls == 0:
            pass
        elif rolls == 1:
            klass |= cls.ROLL
        elif rolls == 2:
            oht = row.row[:2] == oht_roll or row.row.mirror[:2] == oht_roll
            if oht:
                klass |= cls.OHT_ROLL
            else:
                klass |= cls.THT_ROLL
        else:
            klass |= cls.THT_ROLL

        if row.row.count(NoteObject.HOLD_ROLL_END):
            klass |= cls.RELEASE

        return klass
