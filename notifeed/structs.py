#!/usr/bin/env python3

# Imports {{{
# builtins
import asyncio
import logging
from typing import List, NamedTuple

# 3rd party
import aiohttp

# local modules
from notifeed.db.channel import Channel
from notifeed.db.notification import Notification
from notifeed.db.post import Post
from notifeed.enums import FeedEvent
from notifeed.remote import RemoteFeed, RemotePost
from notifeed.utils import pool

# }}}


log = logging.getLogger(__name__)


class PostUpdate(NamedTuple):
    post: RemotePost
    event_type: FeedEvent

    def __bool__(self):
        return self.event_type is not FeedEvent.NoChange

    def save(self):
        """
        Commit this post update to the DB.
        """
        if FeedEvent.FirstPost in self.event_type:
            return self.create()
        elif self.event_type is FeedEvent.New:
            Post.delete().where(Post.feed == self.post.feed.url).execute()
            return self.create()
        elif self.event_type is FeedEvent.Updated:
            return self.update()

    def create(self):
        return Post.create(
            id=self.post.id,
            url=self.post.url,
            title=self.post.title,
            content_hash=self.post.content_hash,
            feed=self.post.feed.url,
        )

    def update(self):
        changes = {
            "url": self.post.url,
            "title": self.post.title,
            "content_hash": self.post.content_hash,
        }
        Post.update(changes).where(Post.id == self.post.id).execute()
        return Post.get_by_id(self.post.id)

    async def notify(self, session: aiohttp.ClientSession):
        log.debug(f"New post found: {self.post}")
        log.debug(f"Event type: {self.event_type}")
        log.info(f'There\'s a new {self.post.feed.name} post: "{self.post.title}"!')

        notifications: List[Notification] = list(
            Notification.select().where(Notification.feed == self.post.feed.url)
        )
        channels = Channel.get_channels(session)
        log.debug(f"Found notifications: {notifications}")
        log.debug(f"Found channels: {channels}")

        self.save()

        tasks = (notification.send(self, session) for notification in notifications)
        return await pool(
            *tasks,
            keys=notifications,
        )


class FeedUpdate(NamedTuple):
    feed: RemoteFeed
    posts: List[PostUpdate]

    def __bool__(self):
        return any(self.posts)

    async def notify(self, session: aiohttp.ClientSession):
        """
        Fire all necessary notifications for the found feed updates.
        """
        if not self:
            log.debug(f"No updates for {self.feed.name}")
            return

        log.debug(f"Processing updates for {self.feed.name}...")
        log.debug(f"{len(self.posts)} updates found.")

        # ensure notifications for all new posts are sent in correct order
        for update in reversed(self.posts):
            await update.notify(session)

        log.debug(f"Finished sending all notifications for {self.feed.name}.")
