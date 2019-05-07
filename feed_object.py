#!/usr/bin/env python3

import atoma
from notifeed.utils import strip_html


class Feed(object):
    """
    A (really) simple, protocol-agnostic, Feed class. I use this I don't
    have to worry about handling RSS and Atom feeds separately. I convert any
    RSS or Atom feeds to a Feed object as soon as I fetch them so that all
    feeds appear identical in other parts of the program.
    """

    # feed should be either an atoma.rss.RSSFeed or atoma.atom.AtomFeed object
    def __init__(self, feed):

        self.entries = []

        if isinstance(feed, atoma.atom.AtomFeed):
            self.type = 'atom'
            entries = feed.entries
        elif isinstance(feed, atoma.rss.RSSChannel):
            self.type = 'rss'
            entries = feed.items
        else:
            raise('Feed format not supported.')

        """
        I may choose to add every feed entry to the Feed object in the future,
        but for now I'm only importing the newest entry to save on unnecessary
        CPU. In the future, importing every entry would allow for detecting
        more than 1 new post at a time, as currently this only notifies you of
        the *latest* new post, not *all* new posts since the last check.
        """
        # convert to FeedEntry object
        self.entries.append(FeedEntry(entries[0]))
        """
        for entry in entries:
            # convert to FeedEntry object
            self.entries.append(FeedEntry(entry))
        """


class FeedEntry(object):
    """
    A (really) simple, protocol-agnostic, Feed Entry class. In the same vein as
    the Feed object, this is meant to simplify working with RSS and Atom feeds
    so that there doesn't need to be any special handling based on the type of
    feed you are working with.
    """

    def __init__(self, entry):

        if isinstance(entry, atoma.atom.AtomEntry):
            self.link = entry.id_
            self.publish_date = entry.updated.timetuple()
            self.title = entry.title.value
            if entry.summary is not None:
                self.summary = strip_html(entry.summary.value)
            elif entry.content is not None:
                self.summary = strip_html(entry.content.value)
            else:
                self.summary = ''
        elif isinstance(entry, atoma.rss.RSSItem):
            self.link = entry.link
            self.publish_date = entry.pub_date.timetuple()
            self.title = entry.title
            self.summary = strip_html(entry.description)
        else:
            raise('Feed type not supported')

