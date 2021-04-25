#!/usr/bin/env python3

# Imports {{{
# builtins
import inspect
from typing import Dict, Optional, Literal, Type
import pathlib

# 3rd party
import requests

# local modules
from notifeed.feeds import Post
from notifeed.utils import import_subclasses

# }}}


class NotificationChannel(object):
    def __init__(
        self,
        name: str,
        endpoint: str,
        authentication: Optional[str] = None,
    ):
        self.endpoint = endpoint
        self.authentication = authentication
        self.name = name

    def notify(self, post: Post):
        """
        Notify the channel of a new Post.

        Default behavior is sending a webhook, but this method can be overridden
        to implement any notification behavior. If you're subclassing this class
        to implement a notification channel that uses webhooks, override the
        build() method on the class instead.
        """
        return self.send_webhook(
            self.endpoint, json=self.build(post), auth_bearer=self.authentication
        )

    def send_webhook(
        self,
        url: str,
        json: dict,
        headers: dict = {},
        auth_bearer: Optional[str] = None,
        method: Literal["GET", "POST", "PUT", "PATCH", "DELETE"] = "POST",
    ):
        """
        Simple helper for sending webhooks.

        If you pass in an auth_bearer parameter, that token will be automatically
        added as a header on the request.
        """
        base = {}
        if auth_bearer is not None:
            base = {"Authorization": f"Bearer: {auth_bearer}"}

        headers = {**base, **headers}

        resp = requests.request(method, url, json=json, headers=headers)
        return resp.ok

    def build(self, post: Post):

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
