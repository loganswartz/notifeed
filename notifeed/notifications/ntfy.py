#!/usr/bin/env python3

# Imports {{{
# local modules
from notifeed.notifications import NotificationChannelAsync
from notifeed.remote import RemotePost

# }}}


class Ntfy(NotificationChannelAsync):
    def notify(self, post: RemotePost):
        headers = {
            "Title": f"{post.feed.name} - {post.title}",
            "Click": post.link,
            "Actions": ", ".join(['view', 'Go to post', post.link]),
        }
        return self.send_webhook(self.endpoint, headers=headers, data=post.summary)
