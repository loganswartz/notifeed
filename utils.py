#!/usr/bin/env python3

"""
Miscellaneous functions that aren't big/important enough to be contained in
their own file.
"""

# 3rd party modules
from bs4 import BeautifulSoup

# builtin modules
from pathlib import Path


def definePath(path: str):
    """
    Create absolute and expanded pathlib.Path objects from path strings.
    """
    if path == None:
        return Path.cwd()
    else:
        return Path(path).expanduser().resolve()


def strip_html(string: str):
    """
    Use BeautifulSoup to strip out any HTML tags from strings.
    """
    return BeautifulSoup(string, 'html.parser').get_text()


def truncate(string: str, length: int):
    """
    Truncate a string to some length and append ellipsis to show content was
    truncated. Will always return a string less than or equal to (never more)
    the specified length.
    """
    if len(string) <= length:
        return string
    else:
        # compensate for ellipsis added at the end
        trimmed = string[0:length-3]

        # trim off trailing half-words
        trimmed = trimmed.rsplit(' ', 1)[0]

        return trimmed+'...'


def union(a, b):
    """
    Return logical union of 2 lists
    """
    return list(set(a).union(b))

