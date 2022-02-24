#!/usr/bin/env python3

# Imports {{{
# builtins
import pathlib
from importlib.util import find_spec

# 3rd party
import appdirs

# }}}


BROTLI_SUPPORTED = find_spec("brotli") is not None
DEFAULT_DB_PATH = pathlib.Path(appdirs.user_config_dir("notifeed")) / "notifeed.db"
DEFAULT_SETTINGS = {
    "poll_interval": 15 * 60,  # 15 minutes, in seconds
    "retry_limit": 5,
}
