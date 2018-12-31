import collections
from operator import attrgetter
from typing import Counter, Dict, FrozenSet, Generic, List, Tuple, TypeVar, Union, cast

from attr import attrs, evolve

from .basic_types import CheaperFraction, Measure, NoteObject, Time
from .complex_types import MeasureBPMPair, MeasureMeasurePair
from .rows import GlobalDeltaRow, GlobalRow, GlobalTimedRow, HasPosition, HasRow, HasTime, JUDGE_IMPORTANT_SET, PureRow, \
    RowFlags

# PureNotefield - PureRow --> HasRow
# UntimedNotefield - GlobalRow --> HasRow, HasPosition
# TimedNotefield - GlobalTimedRow --> HasRow, HasPosition, HasTime
# DeltaNotefield - GlobalDeltaRow --> HasRow, HasPosition, HasTime, GlobalDeltaRow
# MetaNotefield - MetaRow
# SequentialNotefield - RowSequence

# T = TypeVar('T', bound=Union[HasRow, HasPosition, HasTime])
T = TypeVar('T', HasRow, HasPosition, HasTime)


@attrs(auto_attribs=True)
class MetaRow(Generic[T]):
    """Final evolutionary stage of rows, with attached metadata."""
    _row: T
    _kind: RowFlags
    _previous_rows: 'List[T]' = None

    _timing_window_context: Time = None

    @property
    def row(self) -> T:
        return self._row

    @property
    def kind(self) -> 'RowFlags':
        return self._kind

    @property
    def previous_rows(self):
        if self._previous_rows is None:
            raise ValueError
        return self._previous_rows

    @property
    def timing_window(self) -> 'Time':
        if self._timing_window_context is None:
            raise ValueError
        return self._timing_window_context

    @property
    def full_nps_by_rows(self):
        prev = self.previous_rows
        result = 0 if self.row.is_judge_non_important else 1
        for row in prev:
            result += 0 if row.row.is_judge_non_important else 1

        return result

    @property
    def full_nps_by_keys(self):
        prev = self.previous_rows

        result = 0
        if not self.row.is_judge_non_important:
            result += self.row.replace_objects(JUDGE_IMPORTANT_SET,
                                               NoteObject.TAP_OBJECT).row.count(NoteObject.TAP_OBJECT)
        for row in prev:
            if not row.row.is_judge_non_important:
                result += self.row.replace_objects(JUDGE_IMPORTANT_SET,
                                                   NoteObject.TAP_OBJECT).row.count(NoteObject.TAP_OBJECT)

        return result

    @classmethod
    def from_row(cls, row):
        return cls(row, RowFlags.classify_row(row))

    def evolve_previous_rows(self, previous_rows, timing_context):
        return evolve(self, previous_rows=previous_rows, timing_window_context=timing_context)


class AbstractNotefield(Generic[T], List[T]):
    def get_row_sequence_of_n(self, order: int) -> 'SequentialNotefield[Tuple[T, ...]]':
        """Get an n-row sequence.

        This returns all sub-sequences from the note field where the sliding window is of size `order`
        So for a note field [A, B, C, D, E] this is the row sequence of order 2: [(A, B), (B, C), (C, D), (D, E)]"""
        return SequentialNotefield(
            tuple(beta for beta in alpha)
            for alpha in zip(
                *(self[i:(-order + i) or None] for i in range(order))
            )
        ).attach_order(order)

    @property
    def row_sequence_2(self) -> 'SequentialNotefield[Tuple[T, T]]':
        return cast(SequentialNotefield[Tuple[T, T]], self.get_row_sequence_of_n(2))

    @property
    def row_sequence_3(self) -> 'SequentialNotefield[Tuple[T, T, T]]':
        return cast(SequentialNotefield[Tuple[T, T, T]], self.get_row_sequence_of_n(3))

    @property
    def alphabet_size(self) -> int:
        return len({*self})

    @property
    def hashed_flat(self) -> List[int]:
        return [
            hash(obj)
            for obj in self
        ]

    @property
    def unique_elements(self):
        return frozenset(self)

    @property
    def occurrence_counter(self) -> Counter[T]:
        return collections.Counter(self)


class PureNotefield(Generic[T], AbstractNotefield[Union[T, PureRow]], List[PureRow]):
    @property
    def hold_roll_bodies_distinct(self) -> 'PureNotefield[HasRow]':
        """This inserts HOLD_BODY and ROLL_BODY between hold/roll starts and ends respectively.

        Ends are preserved.
        It's guaranteed that f(c) == f(f(c)) == f(f(f(c)) ..."""
        new_note_field = []
        active_holds = set()
        active_rolls = set()

        for row in self:
            active_holds |= row.row.find_object_lanes(NoteObject.HOLD_START)
            active_rolls |= row.row.find_object_lanes(NoteObject.ROLL_START)
            active_holds -= row.row.find_object_lanes(NoteObject.HOLD_ROLL_END)
            active_rolls -= row.row.find_object_lanes(NoteObject.HOLD_ROLL_END)

            new_pure_row = [
                (lane in active_holds and NoteObject.HOLD_BODY) or
                (lane in active_rolls and NoteObject.ROLL_BODY) or
                obj
                for lane, obj in enumerate(row.row)
            ]

            new_note_field.append(
                evolve(row, row=PureRow(new_pure_row))
            )

        return self.__class__(new_note_field)

    @property
    def no_empty_rows(self) -> 'PureNotefield[T]':
        return self.__class__(
            row
            for row in self
            if not row.row.is_empty
        )

    @property
    def no_decorative_elements(self) -> 'PureNotefield[T]':
        return self.__class__(
            row.row.replace_objects({NoteObject.MINE, NoteObject.FAKE}, NoteObject.EMPTY_LANE)
            for row in self
        )

    @property
    def unique_pure_rows(self) -> FrozenSet[PureRow]:
        return frozenset(
            row.row
            for row in self
        )


class UntimedNotefield(Generic[T], PureNotefield[GlobalRow], List[GlobalRow]):
    def calculate_timings(self,
                          bpm_segments: List[MeasureBPMPair],
                          stop_segments: List[MeasureMeasurePair],
                          offset: Time) -> 'TimedNotefield':
        bpm_segments = collections.deque(sorted(bpm_segments, key=attrgetter('measure')))
        stop_segments = collections.deque(sorted(stop_segments, key=attrgetter('measure')))
        note_field_deque = collections.deque(sorted(self, key=attrgetter('pos')))

        elapsed_time = 0
        last_measure = 0
        last_bpm = bpm_segments.popleft()
        next_stop = stop_segments.popleft() if stop_segments else None

        new_note_field = []
        while note_field_deque:
            last_object = note_field_deque.popleft()
            delta_measure = last_object.pos - last_measure

            delta_time = 0
            while True:
                next_bpm = bpm_segments[0] if bpm_segments else None

                if next_bpm and next_bpm.measure < last_object.pos:
                    delta_timing = next_bpm.measure - last_measure
                    delta_time += last_bpm.bpm.measures_per_second * delta_timing
                    delta_measure -= delta_timing
                    last_bpm = bpm_segments.popleft()
                    last_measure = last_bpm.measure
                else:
                    break

            delta_time += last_bpm.bpm.measures_per_second * delta_measure

            while True:
                if next_stop and next_stop.measure < last_measure + delta_measure:
                    delta_time += CheaperFraction(next_stop.value, last_bpm.bpm.measures_per_second)
                    next_stop = stop_segments.popleft() if stop_segments else None
                else:
                    break

            elapsed_time += delta_time
            last_measure += delta_measure

            new_note_field.append(
                last_object.evolve(Time(elapsed_time - offset))
            )

        return TimedNotefield(new_note_field)

    @property
    def position_invariant(self) -> 'UntimedNotefield[T]':
        return self.__class__(
            obj.position_invariant
            for obj in self
        )

    @property
    def measures(self) -> Measure:
        return Measure(max(row.pos.measure for row in self) + 1)

    @property
    def no_decorative_elements(self) -> 'UntimedNotefield[T]':
        return self.__class__(
            evolve(row, row=row.row.replace_objects({NoteObject.MINE, NoteObject.FAKE},
                                                    NoteObject.EMPTY_LANE))
            for row in self
        )


class TimedNotefield(Generic[T], UntimedNotefield[GlobalTimedRow], List[GlobalTimedRow]):
    @property
    def time_invariant(self):
        return self.__class__(
            obj.time_invariant
            for obj in self
        )

    @property
    def duration(self) -> Time:
        return Time(max(row.time for row in self))

    @property
    def discrete_time(self) -> 'TimedNotefield':
        return self.__class__(
            evolve(row, time=row.time.limited_precision)
            for row in self
        )

    @property
    def delta_field(self) -> 'DeltaNotefield':
        delta_rows = [a.evolve(b) for a, b in self.row_sequence_2]
        delta_rows.append(self[-1].evolve(self[-1]))

        return DeltaNotefield(delta_rows)

    def get_timing_window_rows(self: List[GlobalTimedRow], timing_window=Time(180, 1000)) -> 'MetaNotefield':
        new_field = []

        for index, row in enumerate(self):
            this_time = row.time
            result = MetaRow.from_row(row)
            previous = []
            index = index - 1
            while index >= 0 and this_time - self[index].time < timing_window:
                previous.append(self[index])
                index -= 1
            new_field.append(result.evolve_previous_rows(previous, timing_window))

        return MetaNotefield(new_field)

    def get_fuzzy_nps_sequence(self, timing_window=1000) -> Dict[Time, CheaperFraction]:
        delta_step = Time(1, 1000)

        source = self.discrete_time

        result = {}
        for row in source:
            if row.is_judge_non_important:
                continue

            for delta_mul in range(-timing_window, timing_window + 1):
                time_point = Time(row.time + delta_step * delta_mul)
                result[time_point] = result.get(time_point, 0) + timing_window - abs(delta_mul)

        return {
            time_point: value / timing_window
            for time_point, value in result.items()
        }


class DeltaNotefield(Generic[T], TimedNotefield[GlobalDeltaRow], List[GlobalDeltaRow]):
    @property
    def delta_invariant(self):
        return self.__class__(
            obj.delta_invariant
            for obj in self
        )


class SequentialNotefield(Generic[T], AbstractNotefield[T], List[T]):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._order = None

    def attach_order(self, order):
        result = SequentialNotefield(self)
        result._order = order

        return result

    @property
    def sparse_sequence(self) -> 'SequentialNotefield[T]':
        return SequentialNotefield(self[::self._order])


class MetaNotefield(Generic[T], AbstractNotefield[MetaRow], List[MetaRow]):
    pass
