#!/usr/bin/env python3

__version__ = "0.2"

__author__ = "Logan Swartzendruber"
__status__ = "Development"

# builtin modules
import argparse

# 3rd party modules
import atoma
import requests

# my modules
import notifeed
from notifeed.utils import definePath


def main():
    # parse arguments
    cmdparser = argparse.ArgumentParser(
        description=("A simple daemon to regularly parse RSS/Atom feeds and "
            "send push notifications/webhooks when new content is detected"),
        conflict_handler="resolve")
    subparsers = cmdparser.add_subparsers(help="Subcommands",dest="subcommand")

    # feed subparsers
    feedparse = subparsers.add_parser("feed", help="Modify feeds")
    feedsubparse = feedparse.add_subparsers(help="Feed commands", dest="farg")

    feedrmparse = feedsubparse.add_parser("rm", help="Remove feed")
    feedrmparse.add_argument("-n", "--name", help="Name of feed")

    feedaddparse = feedsubparse.add_parser("add", help="Add feed")
    feedaddparse.add_argument("-n", "--name", help="Name of feed to be added")
    feedaddparse.add_argument("-u", "--url", help="URL for the feed")

    # notification subparsers
    notiparse = subparsers.add_parser("notification", help="Set notifications")
    notisubparse = notiparse.add_subparsers(help="Notification commands",
                                            dest="narg")
    notiaddparse = notisubparse.add_parser("add", help="Add notification type")
    notiaddparse.add_argument("-n", "--name", help="Name of notification")
    notiaddparse.add_argument("-t", "--type", help="Name of notification type")
    notiaddparse.add_argument("-d", "--data", help="Additional data")

    notirmparse = feedsubparse.add_parser("rm", help="Remove notification")
    notirmparse.add_argument("-n", "--name", help="Name of notification")



    configPath = definePath('~/.notifeed')
    fetchFlag = threading.Event()

    # check for config file, init if doesn't exist
    if not configPath.exists():
        notifeed.config.init_config(configPath)
        print(f"Config not found, new config file created at {configPath}")

    config = notifeed.config.load_config(configPath)

    # main loop, sleep and then parse feeds
    while not fetchFlag.wait(timeout=config['config']['update_interval']):
        for feed in config['feeds'].keys():
            newPost = notifeed.feed.check_feed(feed)
            if newPost is None:
                continue
            else:
                send_notifications(feed, newPost)


if __name__ == '__main__':
    main()

