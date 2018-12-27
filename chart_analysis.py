import collections
from typing import Counter, Dict, FrozenSet, List, Tuple, TypeVar, Union

from attr import evolve

from .basic_types import CheaperFraction, Measure, NoteObject, Time, ensure_simple_return_type
from .rows import GlobalDeltaRow, GlobalRow, PureRow, TimedRow, TimedRows

T = TypeVar('T', bound=Union[GlobalRow, TimedRows])
RowWindow = Tuple[T, ...]


class _SequentialAnalysisAbstract(List[T]):
    @property
    def alphabet_size(self) -> int:
        return len({*self})

    @property
    def hashed_flat(self) -> List[int]:
        return [
            hash(alpha)
            for alpha in self
        ]

    @property
    def unique_elements(self) -> FrozenSet[T]:
        return frozenset(self)

    @property
    def occurrence_counter(self) -> Counter[T]:
        return collections.Counter(self)


class NRowWindow(_SequentialAnalysisAbstract[Tuple[T, ...]]):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._order = len(self[0])

    @property
    def sparse_sequence(self: 'NRowWindow[RowWindow]') -> 'NRowWindow[RowWindow]':
        return NRowWindow(self[::self._order])


class Notefield(_SequentialAnalysisAbstract[T]):
    @property
    @ensure_simple_return_type
    def duration(self) -> Time:
        return max(row.time for row in self)

    @property
    @ensure_simple_return_type
    def measures(self) -> Measure:
        return max(row.pos.measure for row in self) + 1

    @property
    @ensure_simple_return_type
    def row_complexity(self) -> CheaperFraction:
        unique_characters = set()
        for elmn in self.unique_elements:
            unique_characters |= {*elmn.row}

        full_size = len(unique_characters) ** len(self[0].row)
        return CheaperFraction(len(self.unique_pure_rows), full_size)

    @property
    def unique_pure_rows(self) -> FrozenSet[PureRow]:
        return frozenset(
            row.row
            for row in self
        )

    @property
    def delta_sequence(self) -> 'Notefield[GlobalDeltaRow]':
        delta_rows = [GlobalDeltaRow.from_two_rows(a, b) for a, b in self.row_sequence_2]
        delta_rows.append(GlobalDeltaRow.from_two_rows(self[-1], self[-1]))

        return Notefield(delta_rows)

    @property
    def row_sequence_2(self) -> NRowWindow[T]:
        return self.get_row_sequence_of_n(2)

    @property
    def row_sequence_3(self) -> NRowWindow[T]:
        return self.get_row_sequence_of_n(3)

    @property
    def no_empty_rows(self) -> 'Notefield[T]':
        return Notefield(
            row
            for row in self
            if not row.row.is_empty
        )

    @property
    def no_decorative_elements(self) -> 'Notefield[T]':
        return Notefield(
            evolve(row, row=row.row.replace_objects({NoteObject.MINE, NoteObject.FAKE, NoteObject.LIFT},
                                                    NoteObject.EMPTY_LANE))
            for row in self
        )

    @property
    def position_invariant(self) -> 'Notefield[TimedRow]':
        return Notefield(
            row.as_timed_row
            for row in self
        )

    @property
    def discrete_time(self) -> 'Notefield[T]':
        return Notefield(
            evolve(row, time=row.time.limited_precision)
            for row in self
        )

    @property
    def uniformity_map(self) -> Dict[T, float]:
        keys = self.unique_pure_rows
        result = {}
        for key in keys:
            timings = [row.time for row in self if row.row == key]
            timings.sort()
            deltas = zip(timings[:-1], timings[1:])
            deltas = [beta - alpha for alpha, beta in deltas]
            if len(deltas) <= 6:
                continue
            mean_delta = sum(deltas) / len(deltas)

            variance = sum((time - mean_delta) ** 2 for time in timings)
            std = (variance / (len(timings) - 1)) ** 0.5
            result[key] = (mean_delta, std)

        return result

    @property
    def hold_roll_bodies_distinct(self) -> 'Notefield[T]':
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

    def get_row_sequence_of_n(self, order: int) -> NRowWindow[T]:
        """Get an n-row sequence.

        This returns all sub-sequences from the note field where the sliding window is of size `order`
        So for a note field [A, B, C, D, E] this is the row sequence of order 2: [(A, B), (B, C), (C, D), (D, E)]"""
        return NRowWindow(
            tuple(beta for beta in alpha)
            for alpha in zip(
                *(self[i:(-order + i) or None] for i in range(order))
            )
        )
