from fractions import Fraction
from typing import List, TypeVar, FrozenSet, Tuple, Dict

from attr import attrib, attrs, evolve

from rows import GlobalRow, GlobalTimedRow, PureRow, GlobalDeltaRow
from .basic_types import BPM, Beat, Measure, Time, NoteObject

__all__ = ['MeasureMeasurePair', 'MeasureValuePair', 'MeasureBPMPair']


@attrs()
class MeasureValuePair(object):
    """A duplet, usually used for scripting a chart with freeform data."""
    measure: Measure = attrib()
    value: Fraction = attrib()

    @classmethod
    def from_string_list(cls, string_pairs: str):
        result = (
            value.split('=')[:2]
            for value in string_pairs
        )

        return [
            cls(Beat(beat).as_measure(), value)
            for beat, value in result
        ]


@attrs()
class MeasureMeasurePair(object):
    """A duplet, usually used for define timing sections"""
    measure: Measure = attrib()
    value: Measure = attrib()

    @classmethod
    def from_string_list(cls, string_pairs: str):
        result = (
            map(Beat.as_measure, map(Beat, value.split('=')[:2]))
            for value in string_pairs
        )

        return [
            cls(*pair)
            for pair in result
        ]


@attrs()
class MeasureBPMPair(object):
    """A duplet, used specifically for BPM sections"""
    measure: Measure = attrib()
    bpm: BPM = attrib()

    @classmethod
    def from_string_list(cls, string_pairs: str):
        result = (
            value.split('=')[:2]
            for value in string_pairs
        )

        return [
            cls(Beat(beat).as_measure(), BPM(value))
            for beat, value in result
        ]


T = TypeVar('T', bound=GlobalRow)


class NRowSequence(List[Tuple[T, ...]]):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._order = len(self[0])

    @property
    def hashed_flat(self) -> List[int]:
        return [
            hash(alpha)
            for alpha in self
        ]

    @property
    def alphabet_size(self) -> int:
        """How many unique row sequences are there?"""
        return len({*self})

    @property
    def sparse_sequence(self) -> 'NRowSequence':
        return NRowSequence(self[::self._order])

    @property
    def uniformity_map(self) -> Dict[Tuple[PureRow, ...], float]:
        pass


class Notefield(List[T]):
    @property
    def duration(self: 'Notefield[GlobalTimedRow]') -> Time:
        return max(row.time for row in self)

    @property
    def measures(self) -> Measure:
        return Measure(max(row.pos.measure for row in self) + 1)

    @property
    def unique_rows(self) -> FrozenSet[PureRow]:
        return frozenset(
            row.row
            for row in self
        )

    @property
    def delta_sequence(self: 'Notefield[GlobalTimedRow]') -> 'Notefield[GlobalDeltaRow]':
        return Notefield[GlobalDeltaRow]([
            *(
                GlobalDeltaRow(alpha.row, alpha.pos, beta.time - alpha.time)
                for alpha, beta in zip(self[:-1:2], self[1::2])
            ),
            GlobalDeltaRow(self[-1].row, self[-1].pos, Time(0))
        ])

    def get_row_sequence_of_n(self: 'Notefield[T]', order: int) -> NRowSequence[T]:
        """Get an n-row sequence.

        This returns all sub-sequences from the note field where the sliding window is of size `order`
        So for a note field [A, B, C, D, E] this is the row sequence of order 2: [(A, B), (B, C), (C, D), (D, E)]"""
        return NRowSequence(
            tuple(beta for beta in alpha)
            for alpha in zip(
                *(self[i:-order + i] for i in range(order - 1)),
                self[order:]
            )
        )

    def filter_out_empty_rows(self) -> 'Notefield[T]':
        return Notefield(
            row
            for row in self
            if not row.row.is_empty
        )

    def make_hold_roll_bodies_distinct(self) -> 'Notefield[T]':
        """This inserts HOLD_START and ROLL_START between hold/roll starts and ends respectively.

        Ends are preserved.
        It's guaranteed that f(c) == f(f(c)) == f(f(f(c)) ..."""
        new_note_field = []
        active_holds = set()
        active_rolls = set()

        for row in self:
            active_holds |= row.row.find_object_lanes(NoteObject.HOLD_START)
            active_rolls |= row.row.find_object_lanes(NoteObject.ROLL_START)
            active_holds -= row.row.find_object_lanes(NoteObject.HOLD_END)
            active_rolls -= row.row.find_object_lanes(NoteObject.ROLL_END)

            new_pure_row = [
                lane in active_holds and NoteObject.HOLD_START or
                lane in active_rolls and NoteObject.ROLL_START or
                obj
                for lane, obj in enumerate(row.row)
            ]

            new_note_field.append(
                evolve(row, row=PureRow(new_pure_row))
            )

        return Notefield(new_note_field)
