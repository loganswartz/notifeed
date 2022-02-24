#!/usr/bin/env python3

# Imports {{{
# builtins
import logging
from enum import IntFlag

# }}}


log = logging.getLogger(__name__)


class FeedEvent(IntFlag):
    NoChange = 1
    New = 2
    Updated = 4
    FirstPost = 8
