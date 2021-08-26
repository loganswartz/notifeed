#!/usr/bin/env python3

# Imports {{{
# builtins
from importlib.util import find_spec
import pathlib

# 3rd party
import aiohttp
import appdirs

# }}}


BROTLI_SUPPORTED = find_spec("brotli") is not None
DEFAULT_DB_PATH = pathlib.Path(appdirs.user_config_dir("notifeed")) / "notifeed.db"
