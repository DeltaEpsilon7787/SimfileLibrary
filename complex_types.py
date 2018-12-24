from fractions import Fraction

from attr import attrib, attrs

from . import basic_types

__all__ = ['MeasureMeasurePair', 'MeasureValuePair', 'MeasureBPMPair']


@attrs()
class MeasureValuePair(object):
    """A duplet, usually used for scripting a chart with freeform data."""
    measure: basic_types.Measure = attrib()
    value: Fraction = attrib()

    @classmethod
    def from_string_list(cls, string_pairs: str):
        result = (
            value.split('=')[:2]
            for value in string_pairs
        )

        return [
            cls(basic_types.Beat(beat).as_measure(), value)
            for beat, value in result
        ]


@attrs()
class MeasureMeasurePair(object):
    """A duplet, usually used for define timing sections"""
    measure: basic_types.Measure = attrib()
    value: basic_types.Measure = attrib()

    @classmethod
    def from_string_list(cls, string_pairs: str):
        result = (
            map(basic_types.Beat.as_measure, map(basic_types.Beat, value.split('=')[:2]))
            for value in string_pairs
        )

        return [
            cls(*pair)
            for pair in result
        ]


@attrs()
class MeasureBPMPair(object):
    """A duplet, used specifically for BPM sections"""
    measure: basic_types.Measure = attrib()
    bpm: basic_types.BPM = attrib()

    @classmethod
    def from_string_list(cls, string_pairs: str):
        result = (
            value.split('=')[:2]
            for value in string_pairs
        )

        return [
            cls(basic_types.Beat(beat).as_measure(), basic_types.BPM(value))
            for beat, value in result
        ]
