#!/usr/bin/env python3

# Imports {{{
# builtins
import hashlib
from notifeed.notifications import NotificationChannel
import pathlib
import sqlite3
from typing import Optional, Union

# 3rd party
from atoma.exceptions import FeedXMLError

# local modules
from notifeed.feeds import Feed

# }}}


class Database(object):
    def __init__(self, location: Union[pathlib.Path, str]):
        self.location = location
        self._connection = self._create_connection()

    def _create_connection(self):
        try:
            connection = sqlite3.connect(str(self.location))
            connection.row_factory = sqlite3.Row
        except sqlite3.Error as e:
            raise Exception(f"Database connection failed: {e}") from None

        return connection

    def close(self) -> None:
        """Close the underlying connection"""
        try:
            return self._connection.close()
        except AttributeError:
            return None

    def query(self, sql: str, *args, **kwargs):
        cursor = None
        try:
            cursor = self._connection.cursor()
        except sqlite3.OperationalError:
            # try again
            self.close()
            self._connection = self._create_connection()

        if cursor is None:
            raise Exception(f"Couldn't get a cursor from the DB connection.")

        with self._connection:
            results = cursor.execute(sql, kwargs, *args)

        return results


class NotifeedDatabase(Database):
    def __init__(self, location: Union[pathlib.Path, str]):
        super().__init__(location)

        def table_exists(name):
            exists = "SELECT name FROM sqlite_master WHERE type='table' AND name=:name"
            return bool(list(self.query(exists, name=name)))

        if not table_exists("feeds") or not table_exists("posts"):
            schemas = {
                "feeds": """
                    CREATE TABLE feeds(
                        url STRING PRIMARY KEY,
                        name STRING
                    )
                """,
                "posts": """
                    CREATE TABLE posts(
                        feed STRING PRIMARY KEY,
                        url STRING,
                        title STRING,
                        content_hash STRING,
                        FOREIGN KEY (feed) REFERENCES feeds (url)
                            ON DELETE CASCADE
                            ON UPDATE CASCADE
                    )
                """,
                "settings": """
                    CREATE TABLE settings(
                        name STRING PRIMARY KEY,
                        value STRING
                    )
                """,
                "notification_channels": """
                    CREATE TABLE notification_channels(
                        name STRING PRIMARY KEY,
                        endpoint STRING,
                        type STRING,
                        authentication STRING
                    )
                """,
                "notifications": """
                    CREATE TABLE notifications(
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        channel STRING,
                        feed STRING,
                        FOREIGN KEY (channel) REFERENCES notification_channels (name)
                            ON DELETE CASCADE
                            ON UPDATE CASCADE
                        FOREIGN KEY (feed) REFERENCES feeds (url)
                            ON DELETE CASCADE
                            ON UPDATE CASCADE
                    )
                """,
            }

            for schema in schemas.values():
                try:
                    self.query(schema)
                except sqlite3.ProgrammingError:
                    # skip existing tables
                    continue

            # set default
            self.get_poll_interval()

            print(f"DB initialized at {location}.")

    Seconds = int
    def get_poll_interval(self) -> Seconds:
        DEFAULT = 15 * 60  # seconds
        interval = next(
            self.query("SELECT value FROM settings WHERE name = 'poll_interval'"), None
        )
        if interval is None:
            self.query(
                "INSERT INTO settings (name, value) VALUES ('poll_interval', :interval)",
                interval=DEFAULT,
            )
            return DEFAULT
        else:
            return int(interval["value"])

    def get_feeds(self):
        get = "SELECT * FROM feeds"
        feeds = []
        for url, name in self.query(get):
            try:
                feeds.append(Feed(url, name))
            except FeedXMLError:
                print(f"Failed to parse feed for {name}.")
                continue
        return feeds

    def add_feed(self, name: str, url: str):
        add = "INSERT INTO feeds (url, name) VALUES (:url, :name)"
        return self.query(add, url=url, name=name)

    def delete_feed(self, url: str):
        return self.query("DELETE FROM feeds WHERE url = :url", url=url)

    def get_notification_channels(self):
        get = "SELECT * FROM notification_channels"
        channels = {name.casefold(): cls for name, cls in NotificationChannel.get_subclasses().items()}
        return {
            item["name"]: channels[item["type"].casefold()](
                item["name"], item["endpoint"], item["authentication"]
            )
            for item in self.query(get)
        }

    def add_notification_channel(self, channel: NotificationChannel):
        return self._add_notification_channel(
            name=channel.name,
            type=channel.__class__.__name__.casefold(),
            endpoint=channel.endpoint,
            authentication=channel.authentication,
        )

    def _add_notification_channel(
        self, name: str, type: str, endpoint: str, authentication: Optional[str] = None
    ):
        add = """
            INSERT INTO notification_channels (name, type, endpoint, authentication)
            VALUES (:name, :type, :endpoint, :authentication)
        """
        return self.query(
            add, endpoint=endpoint, type=type, authentication=authentication, name=name
        )

    def delete_notification_channel(self, name: str):
        add = "DELETE FROM notification_channels WHERE name = :name"
        return self.query(add, name=name)

    def get_notifications(self):
        get = "SELECT * FROM notifications"
        return self.query(get)

    def add_notification(self, channel: str, feed: str):
        add = "INSERT INTO notifications (channel, feed) VALUES (:channel, :feed)"
        results = self.query("SELECT url FROM feeds WHERE name = :name", name=feed)
        url = next(results)["url"]
        return self.query(add, channel=channel, feed=url)

    def check_latest_post(self, feed: Feed):
        feed.refresh()
        latest = feed.posts[0]

        identifier = hashlib.sha256(latest.content.encode()).hexdigest()
        get_current = "SELECT * FROM posts WHERE feed = :feed"
        current = next(self.query(get_current, feed=feed.url), None)

        if current is not None and current["content_hash"] == identifier:
            # nothing new
            return False

        insert = """
            INSERT OR REPLACE INTO posts (feed, content_hash, url, title)
            VALUES (:feed, :content_hash, :url, :title)
        """
        self.query(
            insert,
            url=latest.url,
            title=latest.title,
            content_hash=identifier,
            feed=feed.url,
        )
        return latest
