#!/usr/bin/env python3

# Imports {{{
# builtins
import inspect
import pathlib
from typing import Literal, Optional

# 3rd party
import aiohttp
import requests

# local modules
from notifeed.remote import RemotePost
from notifeed.utils import import_subclasses

# }}}


class NotificationChannel(object):
    def __init__(
        self,
        name: str,
        endpoint: str,
        session: requests.Session = None,
        authentication: Optional[str] = None,
    ):
        self.name = name
        self.endpoint = endpoint
        self.session = session
        self.authentication = authentication

    def notify(self, post: RemotePost):
        """
        Notify the channel of a new Post.

        Default behavior is sending a webhook, but this method can be overridden
        to implement any notification behavior. If you're subclassing this class
        to implement a notification channel that uses webhooks, override the
        build() method on the class instead.
        """
        return self.send_webhook(self.endpoint, json=self.build(post))

    def send_webhook(
        self,
        url: str,
        method: Literal["GET", "POST", "PUT", "PATCH", "DELETE"] = "POST",
        **kwargs,
    ):
        """
        Simple helper for sending webhooks.

        If you pass in an auth_bearer parameter, that token will be automatically
        added as a header on the request.
        """
        headers = kwargs.get("headers", {})
        if self.authentication is not None:
            headers["Authorization"] = f"Bearer: {self.authentication}"

        kwargs["headers"] = headers

        fetch = self.session.request if self.session else requests.request
        resp = fetch(method, url, **kwargs)
        return resp.status_code == 200

    def build(self, post: RemotePost):

        """
        Build a JSON payload for a webhook notification.
        """
        raise NotImplementedError("Subclasses must implement a build() method.")

    @classmethod
    def get_subclasses(cls):
        plugins = (
            pathlib.Path(inspect.getframeinfo(inspect.currentframe()).filename)
            .resolve()
            .parent
        )

        return import_subclasses(cls, __package__, plugins)


class NotificationChannelAsync(NotificationChannel):
    def __init__(
        self,
        name: str,
        endpoint: str,
        session: aiohttp.ClientSession,
        authentication: Optional[str] = None,
    ):
        self.endpoint = endpoint
        self.authentication = authentication
        self.name = name
        self.session = session

    async def notify(self, post: RemotePost):
        return await self.send_webhook(
            self.endpoint, json=self.build(post), auth_bearer=self.authentication
        )

    async def send_webhook(
        self,
        url: str,
        method: Literal["GET", "POST", "PUT", "PATCH", "DELETE"] = "POST",
        **kwargs,
    ):
        headers = kwargs.get("headers", {})
        if self.authentication is not None:
            headers["Authorization"] = f"Bearer: {self.authentication}"

        kwargs["headers"] = headers

        resp = await self.session.request(method, url, **kwargs)
        return resp
