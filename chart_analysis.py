from copy import deepcopy

from attr import evolve

from .basic_types import NoteObject
from .rows import PureRow
from .simfile_parser import AugmentedChart


def filter_out_empty_rows(chart: AugmentedChart) -> AugmentedChart:
    """Filter empty rows from a `chart`"""
    new_chart = deepcopy(chart)

    new_chart.note_field = [
        row
        for row in new_chart.note_field
        if not row.row.is_empty
    ]

    return new_chart


def make_hold_roll_bodies_distinct(chart: AugmentedChart) -> AugmentedChart:
    new_chart = deepcopy(chart)

    new_note_field = []
    active_holds = set()
    active_rolls = set()

    for row in new_chart.note_field:
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

    new_chart.note_field = new_note_field
    return new_chart
