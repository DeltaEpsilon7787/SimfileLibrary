from os import chdir, getcwd, path
from os.path import join
from re import sub
from typing import Dict, List, Optional, TextIO, Tuple, Union

from attr import Factory, attrs
from lark import Lark, Transformer

from .basic_types import BPM, CheaperFraction, LocalPosition, Measure, Time
from .chart_analysis import TimedNotefield, UntimedNotefield
from .complex_types import MeasureBPMPair, MeasureMeasurePair, MeasureValuePair
from .rows import GlobalRow, LocalRow, PureRow


@attrs(cmp=False, auto_attribs=True)
class PureChart(object):
    """A chart without metadata or timing data."""
    step_artist: Optional[str] = None
    diff_name: str = 'Beginner'
    diff_value: int = 1
    note_field: UntimedNotefield = Factory(UntimedNotefield)

    @classmethod
    def from_tokens(cls, tokens):
        if len(tokens) == 4:
            return cls('',
                       tokens[0].children[0],
                       tokens[1].children[0],
                       UntimedNotefield(tokens[3]))
        if len(tokens) == 5:
            return cls(tokens[0].children[0],
                       tokens[1].children[0],
                       tokens[2].children[0],
                       UntimedNotefield(tokens[4]))

    def evolve(self, context: 'Simfile') -> 'AugmentedChart':
        return AugmentedChart(
            self.step_artist,
            self.diff_name,
            self.diff_value,
            self.note_field.calculate_timings(context.bpm_segments,
                                              context.stop_segments,
                                              context.offset),
            context.bpm_segments,
            context.stop_segments,
            context.offset
        )


@attrs(cmp=False, auto_attribs=True)
class AugmentedChart(PureChart):
    """A timed chart with attached metadata and timing data."""
    step_artist: Optional[str] = None
    diff_name: str = 'Beginner'
    diff_value: int = 1
    note_field: TimedNotefield = Factory(TimedNotefield)
    bpm_segments: List[MeasureBPMPair] = Factory(list)
    stop_segments: List[MeasureMeasurePair] = Factory(list)
    offset: Time = 0


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
    def measure(tokens: List[PureRow]) -> List[LocalRow]:
        return [
            token.evolve(LocalPosition(pos, len(tokens)))
            for pos, token in enumerate(tokens)
        ]

    @staticmethod
    def measures(tokens: List[List[LocalRow]]) -> List[GlobalRow]:
        return [
            local_row.evolve(Measure(global_pos))
            for global_pos, measure in enumerate(tokens)
            for local_row in measure
        ]

    @staticmethod
    def notes(tokens: List[GlobalRow]) -> PureChart:
        return PureChart.from_tokens(tokens)

    @staticmethod
    def simfile(tokens) -> Simfile:
        result = Simfile()

        result._file_context = getcwd()
        for token in tokens:
            if not token:
                continue
            elif isinstance(token, PureChart):
                result.charts.append(token.evolve(result))
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

    def __getattribute__(self, item):
        if item.startswith('meta_'):
            def meta(tokens):
                return item[5:].upper(), tokens and tokens[0] or ''

            return meta
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
    def phrase(tokens) -> str:
        return str(tokens[0])

    @staticmethod
    def float(tokens) -> CheaperFraction:
        return CheaperFraction(tokens[0])

    @staticmethod
    def int(tokens) -> int:
        return int(tokens[0])

    @staticmethod
    def time(tokens) -> Time:
        return Time(tokens[0])

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
