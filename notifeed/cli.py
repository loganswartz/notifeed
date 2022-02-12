#!/usr/bin/env python3

# Imports {{{
# builtins
import asyncio
from datetime import datetime, timedelta
import logging
import pathlib
import sys
from textwrap import dedent
from typing import Collection, List, Optional, Tuple
import aiohttp

# 3rd party
import click

# local modules
from notifeed.db import Channel, Database, Setting, db, Feed, Notification
from notifeed.feeds import RemoteFeedAsync, RemotePost
from notifeed.notifications import NotificationChannel, NotificationChannelAsync
from notifeed.utils import get_traceback, partition
from notifeed.constants import DEFAULT_DB_PATH

# }}}


# setup logging
log = logging.getLogger("notifeed")
log.setLevel(logging.INFO)
sh = logging.StreamHandler(sys.stdout)
sh.setLevel(logging.DEBUG)
log.addHandler(sh)


@click.group(context_settings=dict(help_option_names=["-h", "--help"]))
@click.option("--debug", is_flag=True, help="Show debug logging messages")
@click.option("--db", "db_path", type=click.Path(), help="Path to an SQLite database, or where to save a new one")
def cli(debug, db_path):
    if debug:
        log.setLevel(logging.DEBUG)
        formatter = logging.Formatter("%(levelname)s: %(message)s")
        sh.setFormatter(formatter)
    if db_path is None:
        DEFAULT_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        path = DEFAULT_DB_PATH
    else:
        path = db_path
    db.init(path)
    Database.seed()
    db.close()


@cli.command()
def run():
    main()


def main():
    poll_interval = int(Setting.get("poll_interval"))

    async def check_feed(feed: RemoteFeedAsync, session: aiohttp.ClientSession):
        """
        Check a feed and fire all relevant notifications if a new post is found.
        """
        log.debug(f"Checking {feed}.")
        try:
            found = await Feed.get(Feed.url == feed.url).check_latest_post(session)
            log.debug(f"{feed.name} was successfully fetched.")
        except Exception as e:
            log.error(f"Error encountered on {feed.name}: {e}")
            return None

        if found is not None:
            log.debug(f"New post found: {found}")
            log.info(f'There\'s a new {found.feed.name} post: "{found.title}"!')

            notifications = list(
                Notification.select().where(Notification.feed == found.feed.url)
            )
            channels = Channel.get_channels(session)
            log.debug(f"Found notifications: {notifications}")
            log.debug(f"Found channels: {channels}")

            for notification in notifications:
                channel = channels[notification.channel.name]
                log.debug(f"Attempting notification on {channel.name}...")
                resp = await channel.notify(found)
                log.debug(f"Notification sent to {channel.name}.")
                log.debug(f"Response received: {int(resp.status)}")

        log.debug(f"Done checking {feed.name}.")
        return found

    async def poll():
        log.info(f"=== Check initiated at {datetime.now()} ===")
        session = aiohttp.ClientSession()

        feeds = Feed.get_feeds(session)
        tasks = [check_feed(feed, session) for feed in feeds]
        found = await asyncio.gather(*tasks, return_exceptions=True)

        partitioned = partition(
            zip(feeds, found), lambda item: isinstance(item[1], Exception)
        )
        exceptions: List[Tuple[RemoteFeedAsync, Exception]] = partitioned.get(True, [])
        results: List[RemotePost] = [
            result for _, result in partitioned.get(False, []) if result is not None
        ]

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

        await session.close()
        await asyncio.sleep(poll_interval)

    feeds = list(Feed.select())
    notifications = list(Notification.select())

    preamble = dedent(
        f"""
    =========== Notifeed ===========
     * Feeds configured: {len(feeds)}
     * Notifications configured: {len(notifications)}
     * Poll Interval: {poll_interval / 60} minutes
    ================================

    Polling started!
    """
    )
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
    with Reporter(f"Added {name}!", "Failed to add feed: {exception}"):
        Feed.create(name=name, url=url)


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
    with Reporter(f"Added {name}!", "Failed to add channel: {exception}"):
        subclass = NotificationChannel.get_subclasses()[type]
        channel = subclass(name, endpoint, auth_token)
        Channel.add(channel)


@add.command(name="notification")
@click.argument("channel")
@click.argument("feeds", nargs=-1)
@click.option(
    "-a",
    "--all",
    "add_all",
    is_flag=True,
    help="Add a notification for all existing feeds",
)
def add_notification(channel, feeds, add_all):
    registered = "all feeds" if add_all else ", ".join(feeds)
    plural = len(feeds) > 1 or (len(Feed.select()) > 1 and add_all)
    with Reporter(
        f"Added notification{'s' if plural else ''} for new posts to {registered}!",
        f"Failed to add notification{'s' if plural else ''}: {{exception}}",
    ):
        Notification.add_feeds_to_channel(
            channel, [feed.name for feed in Feed.select()] if add_all else feeds
        )


@delete.command(name="feed")
@click.argument("name")
def delete_feed(name):
    feed = Feed.get(Feed.name == name)
    with Reporter(f"Deleted {name}!", "Failed to delete feed: {exception}"):
        if feed is not None:
            Feed.delete().execute()


@delete.command(name="channel")
@click.argument("name")
def delete_channel(name):
    with Reporter(f"Deleted {name}!", "Failed to delete channel: {exception}"):
        Channel.delete(Channel.name == name).execute()


@delete.command(name="notification")
@click.argument("channel")
@click.argument("feeds", nargs=-1)
def delete_notification(channel, feeds):
    targets = f"{len(feeds)} feeds{'s' if len(feeds) > 1 else ''}"
    with Reporter(
        f"Disabled notifications on {channel} for {targets}!",
        "Failed to delete notification: {exception}",
    ):
        Notification.delete_feeds_from_channel(channel, feeds)


@show.command(name="feeds")
def list_feeds():
    list_items(
        items=Feed.select(),
        not_found_msg="No feeds found.",
        found_msg="Currently watching:",
        line_fmt="  {name} ({url})",
    )


@show.command(name="channels")
def list_channels():
    list_items(
        items=Channel.select(),
        not_found_msg="No channels configured.",
        found_msg="Available notification channels:",
        line_fmt="  {name} ({type}, {endpoint})",
    )


@show.command(name="notifications")
def list_notifications():
    list_items(
        items=Notification.select(),
        not_found_msg="No notifications configured.",
        found_msg="Configured notifications:",
        line_fmt="  New posts to {feed} --> {channel}",
    )


@cli.command(name="set")
@click.argument("key", type=click.Choice(["poll_interval"]))
@click.argument("value")
def set_settings(key, value):
    with Reporter(f"Set {key} to {value}!", f"Failed to set {key}: {{exception}}"):
        Setting.set(key, value)


def list_items(items: Collection, found_msg: str, not_found_msg: str, line_fmt: str):
    if not items:
        log.info(not_found_msg)
        sys.exit(0)

    log.info(found_msg)
    for item in items:
        log.info(line_fmt.format(**item.__data__))


def save_post(
    found: RemotePost, location: pathlib.Path = pathlib.Path("~/notifeed_posts")
):
    saved = location.expanduser().resolve()
    filename = f"{found.feed.name}-{datetime.today().isoformat()}.xml"

    with open(saved / filename, "w") as fp:
        fp.write(found.raw_content or "")

    return filename


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
