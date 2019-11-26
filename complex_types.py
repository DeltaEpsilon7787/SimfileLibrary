import operator

from attr import attrs

from .basic_types import BPM, Beat, CheaperFraction, Measure


@attrs(auto_attribs=True)
class MeasureValuePair(object):
    """A duplet, usually used for scripting a chart with freeform data."""
    measure: Measure
    value: CheaperFraction

    @classmethod
    def from_string_list(cls, string_pairs: str):
        result = (
            value.split('=')[:2]
            for value in string_pairs
        )

        return [
            cls(Beat(beat).as_measure, value)
            for beat, value in result
        ]


@attrs(auto_attribs=True)
class MeasureMeasurePair(object):
    """A duplet, usually used for define timing sections"""
    measure: Measure
    value: Measure

    @classmethod
    def from_string_list(cls, string_pairs: str):
        result = (
            map(operator.attrgetter('as_measure'), map(Beat, value.split('=')[:2]))
            for value in string_pairs
        )

        return [
            cls(*pair)
            for pair in result
        ]


@attrs(auto_attribs=True)
class MeasureBPMPair(object):
    """A duplet, used specifically for BPM sections"""
    measure: Measure
    bpm: BPM

    @classmethod
    def from_string_list(cls, string_pairs: str):
        result = (
            value.split('=')[:2]
            for value in string_pairs
        )

        return [
            cls(Beat(beat).as_measure, BPM(value))
            for beat, value in result
        ]
