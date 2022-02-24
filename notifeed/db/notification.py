#!/usr/bin/env python3

# Imports {{{
from __future__ import annotations

# builtins
import asyncio
import logging
from typing import TYPE_CHECKING, Collection

# 3rd party
import aiohttp
from peewee import AutoField, BooleanField, ForeignKeyField

# local modules
from notifeed.db.base import Database
from notifeed.db.channel import Channel
from notifeed.db.feed import Feed
from notifeed.db.setting import Setting
from notifeed.enums import FeedEvent

if TYPE_CHECKING:
    # local modules
    from notifeed.structs import PostUpdate

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

    async def send(self, update: PostUpdate, session: aiohttp.ClientSession):
        channels = Channel.get_channels(session)
        channel = channels[self.channel.name]

        if update.event_type is FeedEvent.Updated and not self.notify_on_update:
            return

        log.debug(f"Attempting notification on {channel.name}...")

        resp = None
        tries: int = Setting["retry_limit"]
        for _ in range(max(tries, 1)):
            resp = await channel.notify(update.post)
            # retry if rate limited
            if resp.status != 429:
                break
            await asyncio.sleep(5)

        if resp:
            log.debug(
                f"Notification sent to {channel.name},\n"
                f"Response received: {int(resp.status)}"
            )
        else:
            log.debug(f"Failed to send notification to {channel.name}.")

        return resp
