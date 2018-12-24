"""A simfile parsing library, intended for SM files."""
from . import simfile_parser

__all__ = ['parse_simfile']

parse_simfile = simfile_parser.parse
