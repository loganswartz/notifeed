#!/usr/bin/env python3

# Imports {{{
# builtins
import logging
from typing import Collection

# 3rd party
from peewee import (
    BooleanField,
    ForeignKeyField,
    AutoField,
)

# local modules
from notifeed.db.base import Database
from notifeed.db.feed import Feed
from notifeed.db.channel import Channel

# }}}


log = logging.getLogger(__name__)


class Notification(Database):
    """
    A coupling of a notification channel and a feed.
    """

    id = AutoField()
    channel = ForeignKeyField(Channel, on_delete="CASCADE", on_update="CASCADE")
    feed = ForeignKeyField(Feed, on_delete="CASCADE", on_update="CASCADE")
    notify_on_update = BooleanField(default=False)

    @classmethod
    def delete_all_for_channel(cls, name: str):
        query = cls.delete().where(cls.channel == name)
        query.execute()

    @classmethod
    def delete_feeds_from_channel(cls, channel: str, feeds: Collection[str]):
        selected = [feed.url for feed in Feed.select().where(Feed.name.in_(feeds))]
        query = cls.delete().where((cls.channel == channel) & (cls.feed.in_(selected)))
        query.execute()

    @classmethod
    def add_feeds_to_channel(
        cls, channel: str, feeds: Collection[str], notify_on_update: bool = None
    ):
        selected = [feed.url for feed in Feed.select().where(Feed.name.in_(feeds))]
        return [
            cls.create(channel=channel, feed=feed, notify_on_update=notify_on_update)
            for feed in selected
        ]
