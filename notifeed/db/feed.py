#!/usr/bin/env python3

# Imports {{{
# builtins
import logging
from typing import List, Type, TypeVar, overload

# 3rd party
import aiohttp
from atoma.exceptions import FeedXMLError
from peewee import TextField

# local modules
from notifeed.db.base import Database
from notifeed.remote import RemoteFeed, RemoteFeedAsync

# }}}


log = logging.getLogger(__name__)


ObjCls = TypeVar("ObjCls", bound=RemoteFeed)


class Feed(Database):
    """
    An Atom or RSS feed to monitor.
    """

    url = TextField(primary_key=True)
    name = TextField()

    @classmethod
    def get_feeds(cls, session: aiohttp.ClientSession) -> List[RemoteFeedAsync]:
        feeds = []
        configured: List[Feed] = cls.select()
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
