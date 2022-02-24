#!/usr/bin/env python3

# Imports {{{
# builtins
import logging

# 3rd party
from peewee import ForeignKeyField, TextField

# local modules
from notifeed.db.base import Database
from notifeed.db.feed import Feed

# }}}


log = logging.getLogger(__name__)


class Post(Database):
    """
    An individual post / entry of a feed.
    """

    id = TextField(primary_key=True)
    feed = ForeignKeyField(
        Feed, on_delete="CASCADE", on_update="CASCADE", backref="posts"
    )
    url = TextField()
    title = TextField()
    content_hash = TextField()
