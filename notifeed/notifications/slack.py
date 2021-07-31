#!/usr/bin/env python3

# Imports {{{
# local modules
from notifeed.notifications import NotificationChannelAsync
from notifeed.feeds import RemotePost

# }}}


class Slack(NotificationChannelAsync):
    def build(self, post: RemotePost):
        def thumbnail_element(post: RemotePost):
            thumbnail = {}
            if post.images:
                thumbnail = {
                    "accessory": {
                        "type": "image",
                        "image_url": post.images[0],
                        "alt_text": post.title,
                    }
                }

            return thumbnail

        def context_element(post: RemotePost):
            author = next(iter(post.authors), None)
            pubdate = post.publish_date.strftime("%B %d %Y")

            element = {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": f"By {author} — {pubdate}" if author else pubdate,
                    }
                ],
            }

            return [element] if post.publish_date else []

        data = {
            "text": f"New post from {post.feed.name}: {post.title}",
            "blocks": [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"New post from {post.feed.name}!",
                    },
                },
                {"type": "divider"},
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*<{post.link}|{post.title}>*\n{post.summary}",
                    },
                    **thumbnail_element(post),
                },
                *context_element(post),
            ],
        }

        return data
