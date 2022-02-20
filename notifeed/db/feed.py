#!/usr/bin/env python3

# Imports {{{
# builtins
import logging
from typing import Optional
import aiohttp

# 3rd party
from atoma.exceptions import FeedXMLError
from peewee import (
    TextField,
)

# local modules
from notifeed.feeds import RemoteFeedAsync, RemotePost
from notifeed.db.base import Database

# }}}


log = logging.getLogger(__name__)


class Feed(Database):
    """
    An Atom or RSS feed to monitor.
    """

    url = TextField(primary_key=True)
    name = TextField()

    @classmethod
    def get_feeds(cls, session: aiohttp.ClientSession):
        feeds = []
        for feed in cls.select():
            try:
                feeds.append(feed.as_obj(session))
            except FeedXMLError:
                log.error(f"Failed to parse feed for {feed.name}.")
                continue
        return feeds

    def as_obj(self, session: aiohttp.ClientSession):
        return RemoteFeedAsync(self.url, self.name, session)

    async def check_latest_post(self, session: aiohttp.ClientSession):
        from notifeed.db.post import Post

        feed = self.as_obj(session)
        await feed.load()
        fetched = feed.posts[0]

        stored: Optional[Post] = next(iter(self.posts), None)

        def save_post(post: RemotePost):
            return Post.create(
                id=post.id,
                url=post.url,
                title=post.title,
                content_hash=post.content_hash,
                feed=post.feed.url,
            )

        if stored is not None:
            if fetched.id == stored.id:
                hashes_match = fetched.content_hash == stored.content_hash
                if hashes_match:  # nothing new
                    log.debug(
                        f"Hash for {repr(fetched.title)} matches stored hash (post is unchanged)."
                    )
                    return None
                else:  # latest post was updated since we last saw it
                    log.debug(f"Latest post has been updated (content hash changed)")
                    changes = {
                        "url": fetched.url,
                        "title": fetched.title,
                        "content_hash": fetched.content_hash,
                    }
                    Post.update(changes).where(Post.id == stored.id).execute()
                    return None
            else:  # new post
                log.debug(f"The latest post has a different ID than the stored post.")
                save_post(fetched)
                Post.delete().where(Post.id == stored.id).execute()
                return fetched
        else:  # no post previously saved (aka, a new DB, or the feed had no posts previously)
            log.debug(f"No saved post was found.")
            save_post(fetched)

            return fetched

