from typing import TypeVar

from attr import asdict

from .simfile_parser import AugmentedChart, PureChart

T = TypeVar('T', PureChart, AugmentedChart)


def filter_out_empty_rows(chart: T) -> T:
    """Filter empty rows from a `chart`"""
    return type(chart)(**{
        **asdict(chart, recurse=False),
        'note_field': [
            Q
            for Q in chart.note_field
            if not Q.row.is_empty
        ]})


def inject_hold_bodies(chart: T) -> T:
    """"""
