#!/usr/bin/env python3

# Imports {{{
from __future__ import annotations

# builtins
import asyncio
import logging
from typing import TYPE_CHECKING, Collection

# 3rd party
import aiohttp
from aiohttp.client_reqrep import ClientResponse
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

    id: int = AutoField()  # type: ignore
    channel: Channel = ForeignKeyField(Channel, on_delete="CASCADE", on_update="CASCADE")  # type: ignore
    feed: Feed = ForeignKeyField(Feed, on_delete="CASCADE", on_update="CASCADE")  # type: ignore
    notify_on_update: bool = BooleanField(default=False)  # type: ignore

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

        resp: ClientResponse = None  # type: ignore
        tries: int = Setting["retry_limit"]
        for i in range(max(tries, 1)):
            log.info(f"Attempt #{i}:")
            resp = await channel.notify(update.post)
            log.info(resp)
            log.info(repr(resp.status))
            # retry if rate limited
            if resp.status != 429:
                break
            await asyncio.sleep(5)

        if resp.ok:
            log.debug(f"Notification sent to {channel.name} ({int(resp.status)}).")
        else:
            raw = await resp.text()
            log.debug(f"Failed to send notification to {channel.name}: {repr(raw)}.")

        return resp
