#!/usr/bin/env python3

# Imports {{{
# builtins
import asyncio
from datetime import datetime, timedelta
import logging
import pathlib
import sys
from textwrap import dedent
from typing import List, Optional, Tuple

# 3rd party
import click
from aiohttp import ClientSession
import aiohttp

# local modules
from notifeed.db import NotifeedDatabase
from notifeed.feeds import FeedAsync, Post
from notifeed.notifications import NotificationChannel, NotificationChannelAsync
from notifeed.utils import get_traceback, partition

# }}}


# root of the repo
DB_LOCATION = pathlib.Path(__file__).resolve().parent.parent / "notifeed.db"
db = NotifeedDatabase(DB_LOCATION)
settings = db.get_settings()
db.close()


# setup logging
log = logging.getLogger("notifeed")
sh = logging.StreamHandler(sys.stdout)
sh.setLevel(logging.DEBUG)
log.addHandler(sh)


@click.group(context_settings=dict(help_option_names=["-h", "--help"]))
@click.option('--debug', is_flag=True)
def cli(debug):
    log.setLevel(logging.DEBUG if debug else logging.INFO)


@cli.command()
def run():
    main()


def main():
    async def check_feed(feed: FeedAsync, session: aiohttp.ClientSession):
        """
        Check a feed and fire all relevant notifications if a new post is found.
        """
        log.debug(f"Checking {feed}.")
        db = NotifeedDatabase(DB_LOCATION)
        try:
            found = await db.check_latest_post(feed)
            log.debug(f"{feed.name} was successfully fetched.")
        except Exception as e:
            log.error(f"Error encountered on {feed.name}: {e}")
            return None

        if found is not None:
            log.debug(f"New post found: {found}")
            log.info(f'There\'s a new {found.feed.name} post: "{found.title}"!')

            notifications_query = """
                SELECT * FROM notifications
                    LEFT JOIN feeds ON feeds.url = notifications.feed
                WHERE feeds.url = :feed
            """
            notifications = [dict(**n) for n in db.query(notifications_query, feed=found.feed.url)]
            channels = db.get_notification_channels(session)
            log.debug(f"Registered notifications found: {notifications}")

            for notification in notifications:
                channel = channels[notification["channel"]]
                log.debug(f"Attempting notification on {channel.name}...")
                resp = await channel.notify(found)
                log.debug(f"Notification sent to {channel.name}.")
                log.debug(f"Response recieved: {int(resp.status)}")

        log.debug(f"Done checking {feed.name}.")
        return found


    async def poll():
        log.info(f"=== Check initiated at {datetime.now()} ===")
        db = NotifeedDatabase(DB_LOCATION)
        poll_interval = db.get_poll_interval()

        async with ClientSession() as session:
            feeds = db.get_feeds(session)
            tasks = [check_feed(feed, session) for feed in feeds]
            found = await asyncio.gather(*tasks, return_exceptions=True)

        partitioned = partition(zip(feeds, found), lambda item: isinstance(item[1], Exception))
        exceptions: List[Tuple[FeedAsync, Exception]] = partitioned.get(True, [])
        results: List[Post] = [result for _, result in partitioned.get(False, []) if result is not None]

        for feed, exception in exceptions:
            traceback = get_traceback(exception)
            log.error(f"Encountered exception for {feed.name}:\n{traceback}")

        if not results:
            log.info("No new posts found.")
        else:
            log.info("Finished checking all feeds.")

        log.debug(f"Entering sleep for {poll_interval} seconds.")
        next_check = datetime.now() + timedelta(seconds=poll_interval)
        log.debug(f"Next check occurs at {next_check}.")
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

    preamble = dedent(f"""
    =========== Notifeed ===========
     * Feeds configured: {len(feeds)}
     * Notifications configured: {len(notifications)}
     * Poll Interval: {int(settings.get('poll_interval') / 60)} minutes
    ================================

    Polling started!
    """)
    log.info(preamble)

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


@cli.group()
def set():
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
        NotificationChannelAsync.get_subclasses().keys(), case_sensitive=False
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
        db.add_notification(feed, channel)


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


@delete.command(name="notification")
@click.argument("feed")
@click.argument("channel")
def delete_notification(feed, channel):
    db = NotifeedDatabase(DB_LOCATION)
    with Reporter(f"Deleted notification on {channel} for {feed}!", "Failed to delete notification: {exception}"):
        db.delete_notification(feed, channel)


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


@cli.command(name="set")
@click.argument("key", type=click.Choice(settings.keys()))
@click.argument("value")
def set_settings(key, value):
    db = NotifeedDatabase(DB_LOCATION)
    with Reporter(f"Set {key} to {value}!", f"Failed to set {key}: {{exception}}"):
        db.set_setting(key, value)


def list_items(found_msg: str, not_found_msg: str, line_fmt: str, query: str):
    db = NotifeedDatabase(DB_LOCATION)
    results = list(db.query(query))
    if not results:
        log.info(not_found_msg)
        sys.exit(0)

    log.info(found_msg)
    for item in results:
        log.info(line_fmt.format(**item))


def get_channel_name(channel_url: str):
    db = NotifeedDatabase(DB_LOCATION)
    get = "SELECT name FROM notification_channels WHERE url = :url"
    results = db.query(get, url=channel_url)
    return next(results, {}).get('name', None)


class Reporter(object):
    def __init__(self, success: str, failure: str, pre: Optional[str] = None):
        self.pre = pre
        self.success = success
        self.failure = failure

    def __enter__(self):
        if self.pre is not None:
            log.info(self.pre)

    def __exit__(self, exception_cls, exception, traceback):
        if exception is None:
            log.info(self.success)
        else:
            log.error(self.failure.format(exception=exception))
            return True  # suppress traceback
