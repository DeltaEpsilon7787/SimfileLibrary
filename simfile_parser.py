from collections import deque
from fractions import Fraction
from operator import attrgetter
from os import chdir, getcwd, path
from re import sub
from typing import List, Optional, TextIO, Union

from attr import Factory, attrs
from lark import Lark, Transformer

from .basic_types import Measure, Time
from .complex_types import MeasureBPMPair, MeasureMeasurePair, MeasureValuePair
from .rows import GlobalRow, GlobalTimedRow, LocalRow, PureRow

__all__ = ['PureChart', 'AugmentedChart', 'Simfile', 'parse']


@attrs(cmp=False, auto_attribs=True)
class PureChart(object):
    """A chart without metadata or timing data."""
    step_artist: Optional[str] = None
    diff_name: str = 'Beginner'
    diff_value: int = 1
    note_field: List[GlobalRow] = Factory(list)


@attrs(cmp=False, auto_attribs=True)
class AugmentedChart(PureChart):
    """A timed chart with attached metadata and timing data."""
    step_artist: Optional[str] = None
    diff_name: str = 'Beginner'
    diff_value: int = 1
    note_field: List[GlobalTimedRow] = Factory(list)
    bpm_segments: List[MeasureBPMPair] = Factory(list)
    stop_segments: List[MeasureMeasurePair] = Factory(list)
    offset: Time = 0

    def __attrs_post_init__(self):
        bpm_segments = deque(sorted(self.bpm_segments, key=attrgetter('measure')))
        stop_segments = deque(sorted(self.stop_segments, key=attrgetter('measure')))
        note_field_deque = deque(sorted(self.note_field, key=attrgetter('pos')))

        elapsed_time = 0
        last_measure = 0
        last_bpm = bpm_segments.popleft()
        next_stop = stop_segments.popleft() if stop_segments else None

        self.note_field.clear()
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
                    delta_time += Fraction(next_stop.value, last_bpm.bpm.measures_per_second)
                    next_stop = stop_segments.popleft() if stop_segments else None
                else:
                    break

            elapsed_time += delta_time
            last_measure += delta_measure

            self.note_field.append(
                GlobalTimedRow.from_global_row(last_object, elapsed_time - self.offset)
            )


@attrs(cmp=False, auto_attribs=True)
class Simfile(object):
    title: str = ""
    subtitle: str = ""
    artist: str = ""
    genre: str = ""
    credit: str = ""
    music_path: Optional[str] = None
    banner_path: Optional[str] = None
    bg_path: Optional[str] = None
    cdtitle_path: Optional[str] = None
    sample_start: Time = 0
    sample_length: Time = 10
    display_bpm: str = '*'
    bpm_segments: List[MeasureBPMPair] = Factory(list)
    stop_segments: List[MeasureMeasurePair] = Factory(list)
    offset: Time = 0
    charts: List[AugmentedChart] = Factory(list)

    @property
    def music_file(self):
        return self.music_path and open(self.music_path, 'r')

    @property
    def banner_file(self):
        return self.banner_path and open(self.banner_path, 'r')

    @property
    def bg_file(self):
        return self.bg_path and open(self.bg_path, 'r')

    @property
    def cdtitle_file(self):
        return self.cdtitle_path and open(self.cdtitle_path, 'r')


class ChartTransformer(Transformer):
    file_handles = set()

    @staticmethod
    def _extract_first(tree):
        return tree.children[0]

    @staticmethod
    def row(tokens) -> PureRow:
        return PureRow.from_str_row(''.join(tokens))

    @staticmethod
    def measure(tokens) -> List[LocalRow]:
        return [
            LocalRow(token, Fraction(pos, len(tokens)))
            for pos, token in enumerate(tokens)
        ]

    @staticmethod
    def measures(tokens) -> List[GlobalRow]:
        return [
            GlobalRow.from_local_row(local_row, Measure(global_pos))
            for global_pos, measure in enumerate(tokens)
            for local_row in measure
        ]

    @staticmethod
    def notes(tokens) -> PureChart:
        try:
            return PureChart(*map(ChartTransformer._extract_first, tokens[:3]), tokens[4])
        except IndexError:
            return PureChart('', *map(ChartTransformer._extract_first, tokens[:2]), tokens[3])

    @staticmethod
    def simfile(tokens) -> Simfile:
        result = Simfile()

        for token in tokens:
            if not token:
                continue
            elif isinstance(token, PureChart):
                new_chart = AugmentedChart(**token.__dict__,
                                           bpm_segments=result.bpm_segments,
                                           stop_segments=result.stop_segments,
                                           offset=Time(result.offset))
                result.charts.append(new_chart)
            elif not token.children:
                continue
            elif token.data == 'bpms':
                result.bpm_segments += token.children[0]
            elif token.data == 'stops':
                result.stop_segments += token.children[0]
            else:
                setattr(result, token.data, token.children[0])

        return result

    @staticmethod
    def dontcare(__) -> None:
        return None

    @staticmethod
    def false(__) -> False:
        return False

    @staticmethod
    def true(__) -> True:
        return True

    @staticmethod
    def phrase(tokens) -> str:
        return str(tokens[0])

    @staticmethod
    def float(tokens) -> Fraction:
        return Fraction(tokens[0])

    @staticmethod
    def int(tokens) -> int:
        return int(tokens[0])

    @staticmethod
    def beat_value_pair(tokens) -> MeasureValuePair:
        return MeasureValuePair.from_string_list(tokens)

    @staticmethod
    def beat_beat_pair(tokens) -> MeasureMeasurePair:
        return MeasureMeasurePair.from_string_list(tokens)

    @staticmethod
    def beat_bpm_pair(tokens) -> MeasureBPMPair:
        return MeasureBPMPair.from_string_list(tokens)

    row4 = row6 = row8 = row
    measure4 = measure6 = measure8 = measure
    measures4 = measures6 = measures8 = measures
    no_comma_phrase = no_colon_phrase = phrase


_PACKAGE_DIR = path.split(__file__)[0]

_SM_TRANSFORMER = ChartTransformer()
_SM_PARSER = sm_parser = Lark.open(
    path.join(_PACKAGE_DIR, 'sm_grammar.lark'),
    parser='lalr',
    transformer=_SM_TRANSFORMER,
    start='simfile'
)


def parse(file: Union[str, TextIO]) -> Simfile:
    this_dir = getcwd()

    try:
        lines = file.readlines()
        file = file.name
    except AttributeError:
        with open(file, 'r', encoding='utf-8', errors='ignore') as simfile:
            lines = simfile.readlines()

    simfile = [
        sub(r'(//.*$)', '', line)
        for line in lines
    ]

    simfile = ''.join(simfile)
    try:
        chdir(path.dirname(file))
        parsed_chart = _SM_PARSER.parse(simfile)
    except Exception:
        raise
    finally:
        chdir(this_dir)

    return parsed_chart
