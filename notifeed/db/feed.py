#!/usr/bin/env python3

# Imports {{{
from __future__ import annotations

# builtins
import logging
from typing import TYPE_CHECKING, List, Type, TypeVar, overload

# 3rd party
import aiohttp
from atoma.exceptions import FeedXMLError
from peewee import TextField

# local modules
from notifeed.db.base import Database
from notifeed.remote import RemoteFeed, RemoteFeedAsync

if TYPE_CHECKING:
    # local modules
    from notifeed.db.post import Post

# }}}


log = logging.getLogger(__name__)


ObjCls = TypeVar("ObjCls", bound=RemoteFeed)


class Feed(Database):
    """
    An Atom or RSS feed to monitor.
    """

    url: str = TextField(primary_key=True)  # type: ignore
    name: str = TextField()  # type: ignore
    posts: List[Post]

    @classmethod
    def get_feeds(cls, session: aiohttp.ClientSession) -> List[RemoteFeedAsync]:
        feeds = []
        configured: List[Feed] = list(cls.select())
        for feed in configured:
            try:
                obj = feed.as_obj(session)
                feeds.append(obj)
            except FeedXMLError:
                log.error(f"Failed to parse feed for {feed.name}.")
                continue
        return feeds

    @overload
    def as_obj(self, session: aiohttp.ClientSession) -> RemoteFeedAsync:
        ...

    @overload
    def as_obj(self, session: aiohttp.ClientSession, cls: Type[ObjCls]) -> ObjCls:
        ...

    def as_obj(
        self, session: aiohttp.ClientSession, cls: Type[ObjCls] = RemoteFeedAsync
    ) -> ObjCls:
        return cls(self.url, self.name, session)
