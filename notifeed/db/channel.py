#!/usr/bin/env python3

# Imports {{{
# builtins
import logging
from functools import singledispatchmethod
from typing import Dict, Optional

# 3rd party
import aiohttp
from peewee import TextField

# local modules
from notifeed.db.base import Database
from notifeed.notifications import NotificationChannel, NotificationChannelAsync

# }}}


log = logging.getLogger(__name__)


class Channel(Database):
    """
    A channel through which a notification can be sent.
    """

    name: str = TextField(primary_key=True)  # type: ignore
    type: str = TextField()  # type: ignore
    endpoint: str = TextField()  # type: ignore
    authentication: str = TextField(null=True)  # type: ignore

    @classmethod
    def get_channels(
        cls, session: aiohttp.ClientSession
    ) -> Dict[str, NotificationChannelAsync]:
        return {channel.name: channel.as_obj(session) for channel in cls.select()}

    def as_obj(self, session: aiohttp.ClientSession):
        classes = {
            name.casefold(): cls
            for name, cls in NotificationChannelAsync.get_subclasses().items()
        }
        obj = classes[self.type.casefold()](
            self.name, self.endpoint, session, self.authentication
        )
        return obj

    @singledispatchmethod
    @classmethod
    def add(cls):
        """
        Add a new notification channel.
        """
        raise NotImplementedError()

    @add.register(NotificationChannel)
    @classmethod
    def _(cls, channel: NotificationChannel):
        return cls.create(
            name=channel.name,
            type=channel.__class__.__name__.casefold(),
            endpoint=channel.endpoint,
            authentication=channel.authentication,
        )

    @add.register(str)
    @classmethod
    def _(
        cls,
        name: str,
        type: str,
        endpoint: str,
        authentication: Optional[str] = None,
    ):
        return cls.create(
            name=name, type=type, endpoint=endpoint, authentication=authentication
        )
