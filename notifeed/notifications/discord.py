#!/usr/bin/env python3

# Imports {{{
# builtins
import time

from attr import __description__

# local modules
from notifeed.notifications import NotificationChannelAsync
from notifeed.feeds import Post

# }}}


class Discord(NotificationChannelAsync):
    def build(self, post: Post):
        def thumbnail_element(post: Post):
            block = {}
            if post.images:
                block = {
                    "thumbnail": {"url": post.images[0]},
                }

            return block

        def author_element(post: Post):
            author = next(iter(post.authors), None)

            block = {}
            if author:
                block = {
                    "author": {"name": author}
                }

            return block

        def timestamp_element(post: Post):
            pubdate = post.publish_date.isoformat()

            block = {}
            if pubdate:
                block = {
                    "timestamp": pubdate
                }

            return block

        data = {
            "content": f"New post from {post.feed.name}!",
            "embeds": [
                {
                    "title": post.title,
                    "url": post.url,
                    "description": post.summary,
                    **thumbnail_element(post),
                    **author_element(post),
                    **timestamp_element(post),
                },
            ]
        }

        return data
