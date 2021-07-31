#!/usr/bin/env python3

# Imports {{{
# builtins
from importlib.util import find_spec
import pathlib

# 3rd party
import aiohttp

# }}}


BROTLI_SUPPORTED = find_spec('brotli') is not None
DEFAULT_DB_PATH = pathlib.Path(__file__).resolve().parent.parent / "notifeed.db"
AIOHTTP_SESSION = aiohttp.ClientSession()
