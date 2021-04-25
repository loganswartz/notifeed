#!/usr/bin/env python3

# Imports {{{
# builtins
import textwrap
from typing import Union
import operator
from urllib.parse import urlparse
import aiohttp

# 3rd party
from atoma import parse_rss_bytes, parse_atom_bytes
from atoma.atom import AtomFeed, AtomEntry
from atoma.rss import RSSChannel, RSSItem
import requests

# local modules
from notifeed.utils import condense, strip_html

# }}}


class Feed(object):
    """
    Simple interface to either an Atom or RSS feed.
    """

    def __init__(self, url: str, name: str, session=None, brotli_supported=False):
        """
        Fetch a new copy of a remote RSS/Atom feed for parsing by check_feed()
        """
        self.url = url
        self.name = name
        self._raw = None
        self.session = session
        self.brotli_supported = brotli_supported

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

    @property
    def fetch_headers(self):
        """
        A set of headers needed by some sites to actually respond correctly.

        Typically needed to avoid being stopped by anti-scraping measures.
        """
        headers = {
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/67.0.3396.62 Safari/537.36",
            "Upgrade-Insecure-Requests": "1",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8",
            "Accept-Encoding": "gzip, deflate" + ", br"
            if self.brotli_supported
            else "",
            "Accept-Language": "en-US,en;q=0.9",
            "Connection": "keep-alive",
            "Referer": "http://www.google.com/",
            "Host": urlparse(self.url).hostname,
        }
        return headers

    def fetch(self):
        get = self.session.get if self.session is not None else requests.get
        resp = get(self.url, headers=self.fetch_headers)
        try:
            return parse_atom_bytes(resp.content)
        except:
            return parse_rss_bytes(resp.content)

    @property
    def type(self):
        return "atom" if isinstance(self._feed, AtomFeed) else "rss"

    @property
    def posts(self):
        raw = (
            self._feed.entries if isinstance(self._feed, AtomFeed) else self._feed.items
        )
        return [Post(self, entry) for entry in raw]

    entries = posts

    def __repr__(self):
        return (
            f"{self.__class__.__name__}(name={repr(self.name)}, url={repr(self.url)})"
        )


class FeedAutoload(Feed):
    @property
    def _feed(self):
        """
        Lazy load the actual feed.
        """
        if self._raw is None:
            self.load()
        return self._raw


class FeedAsync(Feed):
    session: aiohttp.ClientSession

    def __init__(
        self,
        url: str,
        name: str,
        session: aiohttp.ClientSession,
        brotli_supported=False,
    ):
        super().__init__(url, name, session, brotli_supported)

    async def fetch(self):
        async with self.session.get(self.url, headers=self.fetch_headers) as response:
            content = await response.read()
            try:
                return parse_atom_bytes(content)
            except:
                return parse_rss_bytes(content)

    async def load(self):
        self._raw = await self.fetch()


class Post(object):
    """
    Abstraction of a post from a feed.
    """

    _mapping = {
        "url": {AtomEntry: "id_", RSSItem: "link"},
        "publish_date": {AtomEntry: "updated", RSSItem: "pub_date"},
        "title": {AtomEntry: "title.value", RSSItem: "title"},
    }

    def __init__(self, feed: Feed, entry: Union[AtomEntry, RSSItem]):
        self.feed = feed
        self.raw = entry
        if not isinstance(entry, (AtomEntry, RSSItem)):
            raise ValueError("Feed type not supported")

    def _get(self, name):
        getter = operator.attrgetter(self._mapping[name][self.raw.__class__])
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
        return self._get("publish_date").timetuple()

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
            item = self.raw.summary if self.raw.summary.value else self.raw.content
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
