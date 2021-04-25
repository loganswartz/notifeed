#!/usr/bin/env python3

# Imports {{{
# builtins
import asyncio
from datetime import datetime
from typing import Optional
from notifeed.notifications import NotificationChannel
import pathlib
import sys

# 3rd party
import click

# local modules
from notifeed.db import NotifeedDatabase

# }}}


# root of the repo
DB_LOCATION = pathlib.Path(__file__).resolve().parent.parent / "notifeed.db"


@click.group(context_settings=dict(help_option_names=["-h", "--help"]))
def cli():
    ...


@cli.command()
def run():
    main()


def main():
    async def poll():
        print(f"=== Check initiated at {datetime.now()} ===")
        db = NotifeedDatabase(DB_LOCATION)
        poll_interval = db.get_poll_interval()
        feeds = db.get_feeds()

        found = []
        for feed in feeds:
        # async with ClientSession() as session:
        #     tasks = [db.check_latest_post(feed, session) for feed in feeds]
        #     await asyncio.gather(*tasks)
            new = db.check_latest_post(feed)
            if new:
                found.append(new)
                print(f'There\'s a new {feed.name} post: "{new.title}"!')

        if found:
            for post in found:
                notifications_query = """
                    SELECT * FROM notifications
                        LEFT JOIN feeds ON feeds.url = notifications.feed
                    WHERE feeds.url = :feed
                """
                notifications = db.query(notifications_query, feed=post.feed.url)
                channels = db.get_notification_channels()
                for notification in notifications:
                    channel = channels[notification["channel"]]
                    channel.notify(post)
        else:
            print("No new posts found.")

        await asyncio.sleep(poll_interval)

    db = NotifeedDatabase(DB_LOCATION)
    feeds = list(db.query("SELECT * FROM feeds"))
    notifications = list(db.query("SELECT * FROM notifications"))
    settings = {
        name: value
        for name, value in db.query(
            "SELECT * FROM settings WHERE name = 'poll_interval'"
        )
    }
    db.close()

    print("=========== Notifeed ===========")
    print(f" * Feeds configured: {len(feeds)}")
    print(f" * Notifications configured: {len(notifications)}")
    print(f" * Poll Interval: {int(settings.get('poll_interval') / 60)} minutes")
    print("================================")
    print("\nPolling started!\n")

    while True:
        asyncio.run(poll())


@cli.group(name="list")
def show():
    ...


@cli.group()
def add():
    ...


@cli.group()
def delete():
    ...


@add.command(name="feed")
@click.argument("name")
@click.argument("url")
def add_feed(name, url):
    db = NotifeedDatabase(DB_LOCATION)
    with Reporter(f"Added {name}!", "Failed to add feed: {exception}"):
        db.add_feed(name, url)


@add.command(name="channel")
@click.argument("name")
@click.argument("endpoint")
@click.option("-a", "--auth_token", default=None)
@click.option(
    "-t",
    "--type",
    type=click.Choice(
        NotificationChannel.get_subclasses().keys(), case_sensitive=False
    ),
    prompt=f"What type of channel is this?",
)
def add_channel(name, endpoint, auth_token, type):
    db = NotifeedDatabase(DB_LOCATION)
    with Reporter(f"Added {name}!", "Failed to add channel: {exception}"):
        subclass = NotificationChannel.get_subclasses()[type]
        channel = subclass(name, endpoint, auth_token)
        db.add_notification_channel(channel)


@add.command(name="notification")
@click.argument("feed")
@click.argument("channel")
def add_notification(feed, channel):
    db = NotifeedDatabase(DB_LOCATION)
    with Reporter(
        f"Added notification for new posts to {feed}!",
        "Failed to add notification: {exception}",
    ):
        db.add_notification(channel, feed)


@delete.command(name="feed")
@click.argument("name")
def delete_feed(name):
    db = NotifeedDatabase(DB_LOCATION)
    feed = next(db.query("SELECT url FROM feeds WHERE name = :name", name=name), None)
    with Reporter(f"Deleted {name}!", "Failed to delete feed: {exception}"):
        if feed is not None:
            db.delete_feed(feed["url"])


@delete.command(name="channel")
@click.argument("name")
def delete_channel(name):
    db = NotifeedDatabase(DB_LOCATION)
    with Reporter(f"Deleted {name}!", "Failed to delete channel: {exception}"):
        db.delete_notification_channel(name)


@show.command(name="feeds")
def list_feeds():
    list_items(
        query="SELECT * FROM feeds",
        not_found_msg="No feeds found.",
        found_msg="Currently watching:",
        line_fmt="  {name} ({url})",
    )


@show.command(name="channels")
def list_channels():
    list_items(
        query="SELECT * FROM notification_channels",
        not_found_msg="No channels configured.",
        found_msg="Available notification channels:",
        line_fmt="  {name} ({type}, {endpoint})",
    )


@show.command(name="notifications")
def list_notifications():
    list_items(
        query="""
            SELECT feeds.name AS feed, notifications.channel FROM notifications
            LEFT JOIN feeds ON feeds.url = notifications.feed
        """,
        not_found_msg="No notifications configured.",
        found_msg="Configured notifications:",
        line_fmt="  New posts to {feed} --> {channel}",
    )


def list_items(found_msg: str, not_found_msg: str, line_fmt: str, query: str):
    db = NotifeedDatabase(DB_LOCATION)
    results = list(db.query(query))
    if not results:
        print(not_found_msg)
        sys.exit(0)

    print(found_msg)
    for item in results:
        print(line_fmt.format(**item))


def get_channel_name(channel_url: str):
    db = NotifeedDatabase(DB_LOCATION)
    channels = db.get_notification_channels().values()
    found = next(
        iter(channel for channel in channels if channel.endpoint == channel_url), None
    )
    return found.name


class Reporter(object):
    def __init__(self, success: str, failure: str, pre: Optional[str] = None):
        self.pre = pre
        self.success = success
        self.failure = failure

    def __enter__(self):
        if self.pre is not None:
            print(self.pre)

    def __exit__(self, exception_cls, exception, traceback):
        if exception is None:
            print(self.success)
        else:
            print(self.failure.format(exception=exception))
            return True  # suppress traceback
