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

    id: str = TextField(primary_key=True)  # type: ignore
    feed: Feed = ForeignKeyField(  # type: ignore
        Feed, on_delete="CASCADE", on_update="CASCADE", backref="posts"
    )
    url: str = TextField()  # type: ignore
    title: str = TextField()  # type: ignore
    content_hash: str = TextField()  # type: ignore
