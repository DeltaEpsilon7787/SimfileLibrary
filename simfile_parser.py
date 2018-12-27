from collections import deque
from operator import attrgetter
from os import chdir, getcwd, path
from os.path import join
from re import sub
from typing import List, Optional, TextIO, Union, Dict, Callable, Tuple

from attr import Factory, attrs
from lark import Lark, Transformer

from .basic_types import CheaperFraction, LocalPosition, Measure, Time, ensure_simple_return_type, BPM
from .chart_analysis import Notefield
from .complex_types import MeasureBPMPair, MeasureMeasurePair, MeasureValuePair
from .rows import GlobalRow, GlobalTimedRow, LocalRow, PureRow


@attrs(cmp=False, auto_attribs=True)
class PureChart(object):
    """A chart without metadata or timing data."""
    step_artist: Optional[str] = None
    diff_name: str = 'Beginner'
    diff_value: int = 1
    note_field: Notefield[GlobalRow] = Factory(list)

    @classmethod
    def from_tokens(cls, tokens):
        if len(tokens) == 4:
            return cls('',
                       tokens[0].children[0],
                       tokens[1].children[0],
                       Notefield(tokens[3]))
        if len(tokens) == 5:
            return cls(tokens[0].children[0],
                       tokens[1].children[0],
                       tokens[2].children[0],
                       Notefield(tokens[4]))


@attrs(cmp=False, auto_attribs=True)
class AugmentedChart(PureChart):
    """A timed chart with attached metadata and timing data."""
    step_artist: Optional[str] = None
    diff_name: str = 'Beginner'
    diff_value: int = 1
    note_field: Notefield[GlobalTimedRow] = Factory(Notefield)
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
                    delta_time += CheaperFraction(next_stop.value, last_bpm.bpm.measures_per_second)
                    next_stop = stop_segments.popleft() if stop_segments else None
                else:
                    break

            elapsed_time += delta_time
            last_measure += delta_measure

            self.note_field.append(
                GlobalTimedRow.from_global_row(last_object, Time(elapsed_time - self.offset))
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
    display_bpm: Union[str, Tuple[BPM, BPM]] = None
    bpm_segments: List[MeasureBPMPair] = Factory(list)
    stop_segments: List[MeasureMeasurePair] = Factory(list)
    offset: Time = 0
    meta: Dict[str, str] = Factory(dict)
    charts: List[AugmentedChart] = Factory(list)

    _file_context: str = None

    @property
    def music_file(self):
        return self.music_path and open(join(self._file_context, self.music_path), 'rb')

    @property
    def banner_file(self):
        return self.banner_path and open(join(self._file_context, self.banner_path), 'rb')

    @property
    def bg_file(self):
        return self.bg_path and open(join(self._file_context, self.bg_path), 'rb')

    @property
    def cdtitle_file(self):
        return self.cdtitle_path and open(join(self._file_context, self.cdtitle_path), 'rb')


class ChartTransformer(Transformer):
    file_handles = set()

    @staticmethod
    def row(tokens) -> PureRow:
        return PureRow.from_str_row(''.join(tokens))

    @staticmethod
    def measure(tokens) -> List[LocalRow]:
        return [
            LocalRow(token, LocalPosition(pos, len(tokens)))
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
        return PureChart.from_tokens(tokens)

    @staticmethod
    def simfile(tokens) -> Simfile:
        result = Simfile()

        result._file_context = getcwd()
        for token in tokens:
            if not token:
                continue
            elif isinstance(token, PureChart):
                new_chart = AugmentedChart(**token.__dict__,
                                           bpm_segments=result.bpm_segments,
                                           stop_segments=result.stop_segments,
                                           offset=Time(result.offset))
                result.charts.append(new_chart)
            elif isinstance(token, tuple):
                result.meta[token[0]] = token[1]
            elif not token.children:
                continue
            elif token.data == 'bpms':
                result.bpm_segments += token.children[0]
            elif token.data == 'stops':
                result.stop_segments += token.children[0]
            else:
                setattr(result, token.data, token.children[0])

        if result.display_bpm is None:
            min_bpm = min(bpm_segment.bpm for bpm_segment in result.bpm_segments)
            max_bpm = max(bpm_segment.bpm for bpm_segment in result.bpm_segments)

            result.display_bpm = (min_bpm, max_bpm)

        return result

    @staticmethod
    def real_meta_creator(token_context) -> Callable[[List[str]], Tuple[str, str]]:
        def meta(tokens):
            return (token_context, tokens and tokens[0] or '')

        return meta

    def __getattribute__(self, item):
        if item.startswith('meta_'):
            return self.real_meta_creator(item[5:].upper())
        return super().__getattribute__(item)

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
    def display_bpm_string(tokens) -> Union[str, Tuple[BPM, BPM]]:
        value = tokens[0]
        if value == '*':
            return value

        try:
            return BPM(value), BPM(value)
        except ValueError:
            from_, to = value.split(':')
            pair = BPM(from_), BPM(to)
            return min(pair), max(pair)

    @staticmethod
    @ensure_simple_return_type
    def phrase(tokens) -> str:
        return tokens[0]

    @staticmethod
    @ensure_simple_return_type
    def float(tokens) -> CheaperFraction:
        return tokens[0]

    @staticmethod
    @ensure_simple_return_type
    def int(tokens) -> int:
        return tokens[0]

    @staticmethod
    @ensure_simple_return_type
    def time(tokens) -> Time:
        return tokens[0]

    beat_value_pair = staticmethod(MeasureValuePair.from_string_list)
    beat_beat_pair = staticmethod(MeasureMeasurePair.from_string_list)
    beat_bpm_pair = staticmethod(MeasureBPMPair.from_string_list)

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
