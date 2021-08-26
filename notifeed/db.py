#!/usr/bin/env python3

# Imports {{{
# builtins
from functools import singledispatchmethod
import hashlib
import logging
from typing import Collection, Dict, Optional, overload
import aiohttp

# 3rd party
from atoma.exceptions import FeedXMLError
from peewee import (
    SqliteDatabase,
    Model,
    TextField,
    ForeignKeyField,
    AutoField,
    make_snake_case,
)

# local modules
from notifeed.feeds import RemoteFeedAsync, RemotePost
from notifeed.notifications import NotificationChannel, NotificationChannelAsync

# }}}


log = logging.getLogger(__name__)


def create_table_name(model):
    snake = make_snake_case(model.__name__)
    pluralized = snake + "s"
    return pluralized


db = SqliteDatabase(None, pragmas={"foreign_keys": 1})
# later call db.init(path)


class Database(Model):
    class Meta:
        database = db
        table_function = create_table_name

    @classmethod
    def seed(cls):
        subclasses = cls.__subclasses__()
        nonexistent = [subcls for subcls in subclasses if not subcls.table_exists()]
        db.create_tables(nonexistent)
        for subcls in nonexistent:
            if hasattr(subcls, "seed"):
                subcls.seed()

    def keys(self):
        return self.__data__.keys()

    def __getitem__(self, key):
        return self.__data__[key]


class Feed(Database):
    """
    An Atom or RSS feed to monitor.
    """

    url = TextField(primary_key=True)
    name = TextField()

    @classmethod
    def get_feeds(cls, session: aiohttp.ClientSession):
        feeds = []
        for feed in cls.select():
            try:
                feeds.append(feed.as_obj(session))
            except FeedXMLError:
                log.error(f"Failed to parse feed for {feed.name}.")
                continue
        return feeds

    def as_obj(self, session: aiohttp.ClientSession):
        return RemoteFeedAsync(self.url, self.name, session)

    async def check_latest_post(self, session: aiohttp.ClientSession):
        feed = self.as_obj(session)
        await feed.load()
        fetched = feed.posts[0]

        stored: Optional[Post] = next(iter(self.posts), None)

        def save_post(post: RemotePost):
            return Post.create(
                id=post.id,
                url=post.url,
                title=post.title,
                content_hash=post.content_hash,
                feed=post.feed.url,
            )

        if stored is not None:
            if fetched.id == stored.id:
                hashes_match = fetched.content_hash == stored.content_hash
                if hashes_match:  # nothing new
                    log.debug(f"Hash for {repr(fetched.title)} matches stored hash (post is unchanged).")
                    return None
                else:  # latest post was updated since we last saw it
                    log.debug(f"Latest post has been updated (content hash changed)")
                    changes = {
                        'url': fetched.url,
                        'title': fetched.title,
                        'content_hash': fetched.content_hash,
                    }
                    Post.update(changes).where(Post.id == stored.id).execute()
                    return None
            else:  # new post
                log.debug(f"The latest post has a different ID than the stored post.")
                save_post(fetched)
                Post.delete().where(Post.id == stored.id).execute()
        else:  # no post previously saved (aka, a new DB, or the feed had no posts previously)
            log.debug(f"No saved post was found.")
            save_post(fetched)

            return fetched

        return None


class Post(Database):
    """
    An individual post / entry of a feed.
    """

    id = TextField(primary_key=True)
    feed = ForeignKeyField(
        Feed, on_delete="CASCADE", on_update="CASCADE", backref="posts"
    )
    url = TextField()
    title = TextField()
    content_hash = TextField()


class Setting(Database):
    """
    Settings for Notifeed.
    """

    name = TextField(primary_key=True)
    value = TextField()

    @classmethod
    def seed(cls):
        DEFAULT_POLL_INTERVAL = 15  # minutes
        cls.create(name="poll_interval", value=DEFAULT_POLL_INTERVAL * 60)

    @overload
    @classmethod
    def get(cls, name: str) -> str:
        ...

    @overload
    @classmethod
    def get(cls, name: None) -> Dict[str, str]:
        ...

    @classmethod
    def get(cls, name: Optional[str] = None):
        settings = {setting.name: setting.value for setting in cls.select()}
        if name is not None:
            return settings.get(name, None)

        return settings

    @classmethod
    def set(cls, name, value):
        return cls.create(name, value)


class Channel(Database):
    """
    A channel through which a notification can be sent.
    """

    name = TextField(primary_key=True)
    type = TextField()
    endpoint = TextField()
    authentication = TextField(null=True)

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
    def add(cls, arg):
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
        cls, name: str, type: str, endpoint: str, authentication: Optional[str] = None
    ):
        return cls.create(
            name=name, type=type, endpoint=endpoint, authentication=authentication
        )


class Notification(Database):
    """
    A coupling of a notification channel and a feed.
    """

    id = AutoField()
    channel = ForeignKeyField(Channel, on_delete="CASCADE", on_update="CASCADE")
    feed = ForeignKeyField(Feed, on_delete="CASCADE", on_update="CASCADE")

    @classmethod
    def delete_all_for_channel(cls, name: str):
        query = cls.delete().where(cls.channel == name)
        query.execute()

    @classmethod
    def delete_feeds_from_channel(cls, channel: str, feeds: Collection[str]):
        selected = [feed.url for feed in Feed.select().where(Feed.name.in_(feeds))]
        query = cls.delete().where((cls.channel == channel) & (cls.feed.in_(selected)))
        query.execute()

    @classmethod
    def add_feeds_to_channel(cls, channel: str, feeds: Collection[str]):
        selected = [feed.url for feed in Feed.select().where(Feed.name.in_(feeds))]
        return [cls.create(channel=channel, feed=feed) for feed in selected]
