#!/usr/bin/env python3

"""
Miscellaneous functions that aren't big/important enough to be contained in
their own file.
"""

# builtin modules
from pathlib import Path


# Wrapper for making paths from strings
def definePath(path: str):
    if path == None:
        return Path.cwd()
    else:
        return Path(path).expanduser().resolve()

