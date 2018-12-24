from fractions import Fraction

from attr import attrib, attrs

from .basic_types import BPM, Beat, Measure

__all__ = ['MeasureMeasurePair', 'MeasureValuePair', 'MeasureBPMPair']


@attrs()
class MeasureValuePair(object):
    """A duplet, usually used for scripting a chart with freeform data."""
    measure: Measure = attrib()
    value: Fraction = attrib()

    @classmethod
    def from_string_list(cls, string_pairs: str):
        result = (
            value.split('=')[:2]
            for value in string_pairs
        )

        return [
            cls(Beat(beat).as_measure(), value)
            for beat, value in result
        ]


@attrs()
class MeasureMeasurePair(object):
    """A duplet, usually used for define timing sections"""
    measure: Measure = attrib()
    value: Measure = attrib()

    @classmethod
    def from_string_list(cls, string_pairs: str):
        result = (
            map(Beat.as_measure, map(Beat, value.split('=')[:2]))
            for value in string_pairs
        )

        return [
            cls(*pair)
            for pair in result
        ]


@attrs()
class MeasureBPMPair(object):
    """A duplet, used specifically for BPM sections"""
    measure: Measure = attrib()
    bpm: BPM = attrib()

    @classmethod
    def from_string_list(cls, string_pairs: str):
        result = (
            value.split('=')[:2]
            for value in string_pairs
        )

        return [
            cls(Beat(beat).as_measure(), BPM(value))
            for beat, value in result
        ]
