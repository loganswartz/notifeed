#!/usr/bin/env python3

# Imports {{{
# builtins
import asyncio
import logging
import sys
from datetime import datetime, timedelta
from textwrap import dedent

# 3rd party
import aiohttp
import click
from peewee import SqliteDatabase

# local modules
from notifeed.constants import DEFAULT_DB_PATH, DEFAULT_SETTINGS
from notifeed.db import Channel, Database, Feed, Notification, Setting, db_proxy
from notifeed.notifications import NotificationChannel, NotificationChannelAsync
from notifeed.remote import RemoteFeedAsync
from notifeed.utils import Reporter, get_traceback, list_items, pool

# }}}


# setup logging
log = logging.getLogger("notifeed")
log.setLevel(logging.INFO)
sh = logging.StreamHandler(sys.stdout)
sh.setLevel(logging.DEBUG)
log.addHandler(sh)


@click.group(context_settings=dict(help_option_names=["-h", "--help"]))
@click.option("--debug", is_flag=True, help="Show debug logging messages")
@click.option(
    "--db",
    "db_path",
    type=click.Path(),
    help="Path to an SQLite database, or where to save a new one",
)
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

    init_db(path)


def init_db(path):
    # TODO: allow more DB connection types
    db = SqliteDatabase(
        path,
        pragmas={
            "journal_mode": "wal",
            "cache_size": -1 * 64000,  # 64MB
            "foreign_keys": 1,
            "ignore_check_constraints": 0,
            "synchronous": 0,
        },
    )

    db_proxy.initialize(db)
    Setting.model.seed()
    Database.seed()
    db_proxy.close()


@cli.command()
def run():
    main()


async def check_and_notify(feed: RemoteFeedAsync):
    updates = await feed.check()
    await updates.notify(feed.session)
    return updates


async def poll():
    log.info(f"=== Check initiated at {datetime.now()} ===")
    session = aiohttp.ClientSession()
    interval: int = Setting["poll_interval"]

    feeds = Feed.get_feeds(session)
    tasks = [check_and_notify(feed) for feed in feeds]
    results, exceptions = await pool(*tasks, keys=feeds)

    for feed, exception in exceptions:
        traceback = get_traceback(exception)
        log.error(f"Encountered exception for {feed.name}:\n{traceback}")

    updates = [tpl[1] for tpl in results]
    if not any(updates):
        log.info("No new posts found.")
    else:
        log.info("Finished checking all feeds.")

    log.debug(f"Entering sleep for {interval} seconds.")
    next_check = datetime.now() + timedelta(seconds=interval)
    log.debug(f"Next check occurs at {next_check}.")

    await session.close()
    await asyncio.sleep(interval)


async def poll_forever():
    while True:
        await poll()


def main():
    interval: int = Setting["poll_interval"]

    feeds = list(Feed.select())
    notifications = list(Notification.select())

    preamble = dedent(
        f"""
    =========== Notifeed ===========
     * Feeds configured: {len(feeds)}
     * Notifications configured: {len(notifications)}
     * Poll Interval: {interval / 60} minutes
    ================================

    Polling started!
    """
    )
    log.info(preamble)

    asyncio.run(poll_forever())


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
        list(NotificationChannelAsync.get_subclasses().keys()), case_sensitive=False
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
    help="Add the notification for all existing feeds",
)
@click.option(
    "-u",
    "--notify-on-update",
    is_flag=True,
    help="Send a notification when a feed's latest post is edited, instead of only when a new post is found.",
)
def add_notification(channel, feeds, add_all, notify_on_update):
    registered = "all feeds" if add_all else ", ".join(feeds)
    plural = len(feeds) > 1 or (add_all and len(Feed.select()) > 1)
    with Reporter(
        f"Added notification{'s' if plural else ''} for new posts to {registered}!",
        f"Failed to add notification{'s' if plural else ''}: {{exception}}",
    ):
        Notification.add_feeds_to_channel(
            channel,
            [feed.name for feed in Feed.select()] if add_all else feeds,
            notify_on_update,
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
@click.argument("key", type=click.Choice(list(DEFAULT_SETTINGS.keys())))
@click.argument("value")
def set_settings(key, value):
    with Reporter(f"Set {key} to {value}!", f"Failed to set {key}: {{exception}}"):
        Setting[key] = value
