import collections
from functools import lru_cache
from itertools import groupby, permutations
from operator import attrgetter
from typing import Counter, FrozenSet, Generic, List, Tuple, TypeVar, Union, cast

from attr import attrs, evolve

from .basic_types import Beat, CheaperFraction, NoteObject, Time, make_ordered_set
from .complex_types import MeasureBPMPair, MeasureMeasurePair
from .rows import DECORATIVE_SET, GlobalDeltaRow, GlobalRow, GlobalTimedRow, HasPosition, HasRow, HasTime, \
    LONG_NOTE_SET, PureRow, RowFlags

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

    @property
    def row(self) -> T:
        return self._row

    @property
    def kind(self) -> 'RowFlags':
        return self._kind

    @classmethod
    def from_row(cls, row):
        return cls(row, RowFlags.classify_row(row))


class AbstractNotefield(Generic[T], List[T]):
    @property
    def alphabet_size(self) -> int:
        return len(self.unique_elements)

    @property
    def hashed_flat(self) -> 'AbstractNotefield[int]':
        return AbstractNotefield(
            hash(obj)
            for obj in self
        )

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

        is_pure = self.__class__ == PureNotefield
        for row in self:
            active_holds -= row.row.find_object_lanes(NoteObject.HOLD_ROLL_END)
            active_rolls -= row.row.find_object_lanes(NoteObject.HOLD_ROLL_END)

            new_pure_row = [
                (lane in active_holds and NoteObject.HOLD_BODY) or
                (lane in active_rolls and NoteObject.ROLL_BODY) or
                obj
                for lane, obj in enumerate(row.row)
            ]

            if is_pure:
                new_note_field.append(PureRow(new_pure_row))
            else:
                new_note_field.append(
                    evolve(cast(T, row), row=PureRow(new_pure_row))
                )

            active_holds |= row.row.find_object_lanes(NoteObject.HOLD_START)
            active_rolls |= row.row.find_object_lanes(NoteObject.ROLL_START)

        return self.__class__(new_note_field)

    @property
    def ignore_empty_rows(self) -> 'PureNotefield[T]':
        return self.__class__(
            row
            for row in self
            if not row.row.is_empty
        )

    @property
    def no_decorative_elements(self) -> 'PureNotefield[T]':
        return self.__class__(
            row.row.replace_objects(DECORATIVE_SET, NoteObject.EMPTY_LANE)
            for row in self
        )

    @property
    def ignore_pure_hold_roll_body_rows(self) -> 'PureNotefield[T]':
        return self.__class__(
            row
            for row in self
            if not row.is_pure_hold_roll_body
        )

    @property
    def normalized(self) -> 'PureNotefield[T]':
        return self.hold_roll_bodies_distinct.no_decorative_elements.ignore_empty_rows.ignore_pure_hold_roll_body_rows

    @property
    def permutative_notefield(self) -> 'AbstractNotefield[FrozenSet[T]]':
        return AbstractNotefield(
            row.permutative_set
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
    def no_decorative_elements(self) -> 'UntimedNotefield[T]':
        return self.__class__(
            evolve(row, row=row.row.replace_objects({NoteObject.MINE, NoteObject.FAKE},
                                                    NoteObject.EMPTY_LANE))
            for row in self
        )

    def row_sequence_by_beats(self, beat_window=1) -> 'SequentialNotefield[RowSequence[T, ...]]':
        def group(row):
            return int(row.pos / Beat(beat_window).as_measure)

        result = []
        for _, group in groupby(self, group):
            result.append(
                RowSequence(
                    obj.localize(Beat(beat_window).as_measure)
                    for obj in group
                )
            )

        return SequentialNotefield(result)


class TimedNotefield(Generic[T], UntimedNotefield[GlobalTimedRow], List[GlobalTimedRow]):
    @property
    def time_invariant(self):
        return self.__class__(
            obj.time_invariant
            for obj in self
        )

    @property
    def discrete_time(self) -> 'TimedNotefield':
        return self.__class__(
            evolve(row, time=row.time.limited_precision)
            for row in self
        )

    @property
    def miniholds_minirolls_as_taps(self):
        hold_regrab_window = Time(250, 1000)
        roll_tap_window = Time(500, 1000)

        hold_coords = []
        roll_coords = []
        for index, row in enumerate(self):
            hold_starts = self[index].find_object_lanes(NoteObject.HOLD_START)
            roll_starts = self[index].find_object_lanes(NoteObject.ROLL_START)

            if hold_starts or roll_starts:
                for sub_index, sub_row in enumerate(self[index:], start=index):
                    ends = self[sub_index].find_object_lanes(NoteObject.HOLD_ROLL_END)
                    ended_holds = hold_starts & ends
                    ended_rolls = roll_starts & ends
                    hold_coords.extend((range(index, sub_index + 1), lane) for lane in ended_holds)
                    roll_coords.extend((range(index, sub_index + 1), lane) for lane in ended_rolls)
                    hold_starts -= ended_holds
                    roll_starts -= ended_rolls

                    if not (hold_starts | roll_starts):
                        break

        hold_coords = [
            pair
            for pair in hold_coords
            if self[pair[0].stop - 1].time - self[pair[0].start].time > hold_regrab_window
        ]

        roll_coords = [
            pair
            for pair in hold_coords
            if self[pair[0].stop - 1].time - self[pair[0].start].time > roll_tap_window
        ]

        combined_coords = hold_coords + roll_coords

        def new_object(obj, self_index, lane):
            if obj not in LONG_NOTE_SET:
                return obj

            is_safe = any(self_index in long_note_range and lane == long_note_lane
                          for long_note_range, long_note_lane in combined_coords)
            if is_safe:
                return obj
            return obj == NoteObject.HOLD_START and NoteObject.TAP_OBJECT or NoteObject.EMPTY_LANE

        return self.__class__(
            evolve(row, row=PureRow(new_object(obj, index, lane)
                                    for lane, obj in enumerate(row.row)))
            for index, row in enumerate(self)
        )

    @property
    def delta_field(self) -> 'DeltaNotefield':
        delta_rows = [a.evolve(b) for a, b in zip(self[:-1:], self[1::])]
        delta_rows.append(self[-1].evolve(self[-1]))

        return DeltaNotefield(delta_rows)


class DeltaNotefield(Generic[T], TimedNotefield[GlobalDeltaRow], List[GlobalDeltaRow]):
    @property
    def delta_invariant(self):
        return self.__class__(
            obj.delta_invariant
            for obj in self
        )

    @property
    def pure_delta(self):
        return self.position_invariant.time_invariant


@lru_cache(10)
def generate_permutative_maps(lanes=4):
    return [
        {
            index: permutation[index]
            for index in range(lanes)
        }
        for permutation in permutations(range(lanes))
    ]


class RowSequence(Tuple[T, ...], tuple, Generic[T]):
    __new__ = tuple.__new__

    @property
    def permutative_group(self):
        lanes = len(self[0].row)
        maps = generate_permutative_maps(lanes)

        return frozenset(make_ordered_set(
            tuple(
                obj.switch_lanes(lane_map)
                for obj in self
            )
            for lane_map in maps
        ))

    @property
    def is_empty_sequence(self):
        return all(
            row.is_empty
            for row in self
        )


class SequentialNotefield(Generic[T], AbstractNotefield[RowSequence[T]], List[RowSequence[T]]):
    def broadcast(self, function):
        return self.__class__(
            tuple(
                function(obj)
                for obj in seq
            )
            for seq in self
        )

    @property
    def permutative_field(self):
        return self.__class__(
            seq.permutative_group
            for seq in self
        )


class MetaNotefield(Generic[T], AbstractNotefield[MetaRow], List[MetaRow]):
    pass


# from simfile_parser import AugmentedChart
class BatchOperations(object):
    pass
