#!/usr/bin/env python3

# Imports {{{
# builtins
import hashlib
import logging
import operator
import textwrap
from typing import Union

# 3rd party
import aiohttp
import requests
from atoma import parse_atom_bytes, parse_rss_bytes
from atoma.atom import AtomEntry, AtomFeed
from atoma.rss import RSSChannel, RSSItem
from peewee import DoesNotExist

# local modules
from notifeed.enums import FeedEvent
from notifeed.utils import condense, find, generate_headers, strip_html

# }}}


log = logging.getLogger(__name__)


class RemoteFeed(object):
    """
    Simple interface to either an Atom or RSS feed.

    Some resources:
    https://validator.w3.org/feed/docs/atom.html
    https://validator.w3.org/feed/docs/rss2.html
    https://kavasmlikon.wordpress.com/2012/11/08/how-to-manually-set-up-pubsubhubbub-for-your-rssatom-feeds/
    """

    def __init__(self, url: str, name: str, session=None):
        """
        Fetch a new copy of a remote RSS/Atom feed for parsing by check_feed()
        """
        self.url = url
        self.name = name
        self._raw = None
        self.session = session

    @property
    def _feed(self):
        """
        Lazy load the actual feed.
        """
        if not self._raw:
            raise RuntimeError(
                "You need to call the load() method first to actually fetch the feed."
            )
        return self._raw

    def load(self):
        self._raw = self.fetch()

    refresh = load

    def fetch(self):
        get = self.session.get if self.session is not None else requests.get
        resp = get(self.url, headers=generate_headers(self.url))
        try:
            return parse_atom_bytes(resp.content)
        except:
            return parse_rss_bytes(resp.content)

    @property
    def type(self):
        return "atom" if isinstance(self._feed, AtomFeed) else "rss"

    @property
    def posts(self):
        """
        Posts found on the feed.

        Sorted in descending order, so the first element of the list is the
        latest post.
        """
        raw = (
            self._feed.entries if isinstance(self._feed, AtomFeed) else self._feed.items
        )
        return [RemotePost(self, entry) for entry in raw]

    entries = posts

    def _check(self):
        # local modules
        from notifeed.db.feed import Feed
        from notifeed.db.post import Post
        from notifeed.structs import FeedUpdate, PostUpdate

        # fetch fresh version of feed before
        log.debug(f"Checking {self}.")

        db_feed: Feed = Feed.get_by_id(self.url)
        db_latest = next(iter(db_feed.posts), None)

        if not self.posts:
            log.debug(f"No remote posts were found.")

            return FeedUpdate(self, [])

        # where in the fetched feed is the latest post we remember?
        # all posts after that must be new or updated
        idx = find(
            self.posts,
            lambda item: item.id == db_latest.id if db_latest is not None else None,
        )
        log.debug(f"Found index: {idx}")
        log.debug(f"Posts on remote feed: {self.posts}")
        # if we can't find the post, assume only the latest is new
        # (this way we avoid blitzing people with a million notifications)
        slice = 1 if idx is None else idx
        new = self.posts[:slice]

        posts = []
        for i, post in enumerate(new):
            log.debug(f"Determining status of {post} (ID: {repr(post.id)})")

            try:
                in_db = Post.get_by_id(post.id)
            except DoesNotExist:
                in_db = False

            if in_db:
                hashes_match = post.content_hash == in_db.content_hash
                if hashes_match:  # nothing new
                    event = FeedEvent.NoChange
                    log.debug(
                        f"Hash for {repr(post.title)} matches stored hash (post is unchanged)."
                    )
                else:  # latest post was updated since we last saw it
                    event = FeedEvent.Updated
                    log.debug(f"Latest post has been updated (content hash changed)")
            elif i == len(new):
                # no post previously saved (aka, a new DB, or the feed had no posts previously)
                event = FeedEvent.New | FeedEvent.FirstPost
            else:  # new post
                event = FeedEvent.New
                log.debug(f"The latest post has a different ID than the stored post.")

            posts.append(PostUpdate(post, event))

        return FeedUpdate(self, posts)

    def check(self):
        """
        Check for updates to the feed.
        """
        self.load()

        return self._check()

    def __repr__(self):
        return (
            f"{self.__class__.__name__}(name={repr(self.name)}, url={repr(self.url)})"
        )


class RemoteFeedAutoload(RemoteFeed):
    @property
    def _feed(self):
        """
        Lazy load the actual feed.
        """
        if self._raw is None:
            self.load()
        return self._raw


class RemoteFeedAsync(RemoteFeed):
    session: aiohttp.ClientSession

    def __init__(
        self,
        url: str,
        name: str,
        session: aiohttp.ClientSession,
    ):
        super().__init__(url, name, session)

    async def fetch(self):
        async with self.session.get(
            self.url, headers=generate_headers(self.url)
        ) as response:
            content = await response.read()
            try:
                return parse_atom_bytes(content)
            except:
                return parse_rss_bytes(content)

    async def load(self):
        self._raw = await self.fetch()

    async def check(self):
        """
        Check for updates to the feed.
        """
        await self.load()

        return self._check()


class RemotePost(object):
    """
    Abstraction of a post from a feed.
    """

    _mappings = {
        "url": {AtomEntry: "id_", RSSItem: "link"},
        "publish_date": {AtomEntry: "updated", RSSItem: "pub_date"},
        "title": {AtomEntry: "title.value", RSSItem: "title"},
        "id": {AtomEntry: "id_", RSSItem: "guid"},
    }

    def __init__(self, feed: RemoteFeed, entry: Union[AtomEntry, RSSItem]):
        self.feed = feed
        self.raw = entry
        if not isinstance(entry, (AtomEntry, RSSItem)):
            raise ValueError("Feed type not supported")

    def _get(self, name):
        getter = operator.attrgetter(self._mappings[name][self.raw.__class__])
        return getter(self.raw)

    @property
    def url(self):
        return self._get("url")

    link = url

    @property
    def title(self):
        return self._get("title")

    @property
    def publish_date(self):
        return self._get("publish_date")

    @property
    def id(self):
        return self._get("id")

    @property
    def raw_content(self):
        content = ""

        if isinstance(self.raw, AtomEntry):
            item = self.raw.content if self.raw.content else self.raw.summary
            content = item.value
        elif isinstance(self.raw, RSSItem):
            content = self.raw.description

        return content

    @property
    def content(self):
        return condense(strip_html(self.raw_content or ""))

    @property
    def summary(self):
        summary = ""

        if isinstance(self.raw, AtomEntry):
            item = (
                self.raw.summary
                if getattr(self.raw.summary, "value", None)
                else self.raw.content
            )
            summary = item.value
        elif isinstance(self.raw, RSSItem):
            summary = self.raw.description

        return textwrap.shorten(
            condense(strip_html(summary or "")), width=150, placeholder="..."
        )

    @property
    def authors(self):
        if self.feed.type == "atom":
            return [author.name for author in getattr(self.raw, "authors", [])]
        else:
            author = getattr(self.raw, "author", None)
            return [author] if author else []

    @property
    def images(self):
        try:
            links = self.raw.links or []
        except AttributeError:
            return []

        return [link.href for link in links if link.type_ and "image" in link.type_]

    def __repr__(self):
        return f"{self.__class__.__name__}({repr(self.title)})"

    @property
    def content_hash(self):
        return hashlib.sha256(self.content.encode()).hexdigest()
