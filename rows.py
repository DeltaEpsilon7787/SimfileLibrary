from typing import Union

from attr import attrs

from .basic_types import GlobalPosition, LocalPosition, Measure, NoteObject, Time

__all__ = ['PureRow', 'LocalRow', 'GlobalRow', 'GlobalTimedRow', 'Snap']


class PureRow(tuple):
    """A basic pseudo-class representing a row, equivalent to tuples with additional methods."""

    @classmethod
    def from_str_row(cls, row: str) -> 'PureRow':
        return cls(
            NoteObject.get_from_character(char)
            for char in row
        )

    def replace_objects(self, from_note: NoteObject, to_note: NoteObject) -> 'PureRow':
        return PureRow(
            obj is from_note and to_note or obj
            for obj in self
        )

    @property
    def str_row(self):
        return ''.join(
            obj.value
            for obj in self
        )

    @property
    def is_empty(self):
        return {*self} == {NoteObject.EMPTY_LANE}

    def find_object_lanes(self, needle_object: NoteObject):
        return {
            lane
            for lane, obj in enumerate(self)
            if obj is needle_object
        }


@attrs(frozen=True, slots=True, auto_attribs=True)
class LocalRow(object):
    """A basic object representing a row within a measure."""
    row: PureRow
    pos: LocalPosition

    @property
    def snap(self):
        return Snap.from_row(self)


@attrs(frozen=True, slots=True, auto_attribs=True)
class GlobalRow(LocalRow):
    """A basic object representing a row within a chart."""
    row: PureRow
    pos: GlobalPosition

    @classmethod
    def from_local_row(cls, local_row: LocalRow, global_pos: Measure):
        return cls(local_row.row, global_pos + local_row.pos)


@attrs(frozen=True, slots=True, auto_attribs=True)
class GlobalTimedRow(GlobalRow):
    """An augmented version of GlobalRow, with timing data attached to it."""
    row: PureRow
    pos: GlobalPosition
    time: Time

    @classmethod
    def from_global_row(cls, global_row: GlobalRow, time: Time):
        return cls(global_row.row, global_row.pos, time)


@attrs(frozen=True, slots=True, auto_attribs=True)
class GlobalDeltaRow(GlobalTimedRow):
    """A contextually dependent version of GlobalTimedRow, where `time` is the difference in time between this and next row"""
    row: PureRow
    pos: GlobalPosition
    time: Time


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
    def from_row(cls, row: Union[LocalRow, GlobalRow]):
        return cls(row.pos.denominator)
