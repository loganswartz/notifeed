#!/usr/bin/env python3

"""
Notifeed.py: A simple daemon to regularly parse RSS/Atom feeds and send push
notifications/webhooks when new content is detected.
"""

__version__ = "1.0"

__author__ = "Logan Swartzendruber"
__status__ = "Production"

# builtin modules
import argparse
import logging

# my modules
from notifeed.utils import definePath
from notifeed.processor import FeedProcessor


def main():

    logging.basicConfig(level=logging.WARNING)
    logging.getLogger("requests").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logger = logging.getLogger(__name__)

    # create file logging handler
    #fh = logging.FileHandler('notifeed.log')
    #fh.setLevel(logging.DEBUG)
    # create console logging handler
    console = logging.StreamHandler()
    console.setLevel(logging.INFO)

    #fhformat = logging.Formatter('%(name)s:%(levelname)s: %(message)s')
    console_format = logging.Formatter('%(message)s')
    #fh.setFormatter(fhformat)
    console.setFormatter(console_format)
    #logger.addHandler(fh)
    logger.addHandler(console)
    logger.setLevel(logging.INFO)

    # create feed processor and initialize config
    feedProcessor = FeedProcessor()
    feedProcessor.load()


    # set up main argparse parser and subparser
    cmdparser = argparse.ArgumentParser(
        description=("A simple daemon to regularly parse RSS/Atom feeds and "
            "send push notifications/webhooks when new content is detected"),
        conflict_handler="resolve")
    subparsers = cmdparser.add_subparsers(help="Subcommands",dest="command")

    # feed subparsers
    feedparse = subparsers.add_parser("feed", help="Modify feeds")
    feedsubparse = feedparse.add_subparsers(help="Feed commands",
                   dest="subcommand")
    # create_feed
    fcreate = feedsubparse.add_parser("create", help="Add feed")
    fcreate.add_argument("-n", "--name", help="Name of feed to be created")
    fcreate.add_argument("-u", "--url", help="URL for the feed")
    fcreate.set_defaults(func=feedProcessor.create_feed_wrapper)
    # destroy_feed
    fdestroy = feedsubparse.add_parser("destroy", help="Remove feed")
    fdestroy.add_argument("-n", "--name", help="Name of feed")
    fdestroy.set_defaults(func=feedProcessor.destroy_feed_wrapper)
    # list_feed
    flist = feedsubparse.add_parser("list", help="List feeds")
    flist.add_argument("-n", "--name", help="Name of feed")
    flist.set_defaults(func=feedProcessor.list_feed_wrapper)

    # notification subparsers
    notiparse = subparsers.add_parser("notification", help="Set notifications")
    notisubparse = notiparse.add_subparsers(help="Notification commands",
                                            dest="subcommand")
    # create_noti
    ncreate = notisubparse.add_parser("create", help="Create notification")
    ncreate.add_argument("-n", "--name", help="Name of notification",
            required=True)
    ncreate.add_argument("-t", "--type", help="Type of notification")
    ncreate.add_argument("-d", "--data", help="Additional data")
    ncreate.set_defaults(func=feedProcessor.create_noti_wrapper)
    # destroy_noti
    ndestroy = notisubparse.add_parser("destroy", help="Destroy notification")
    ndestroy.add_argument("-n", "--name", help="Name of notification")
    ndestroy.set_defaults(func=feedProcessor.destroy_noti_wrapper)
    # add_noti
    nadd = notisubparse.add_parser("add", help="Add notification to feed")
    nadd.add_argument("-n", "--name", help="Name of notification")
    nadd.add_argument("-f", "--feed", help="Name of feed")
    nadd.set_defaults(func=feedProcessor.add_noti_wrapper)
    # rm_noti
    nrm = notisubparse.add_parser("rm", help="Remove notification from feed")
    nrm.add_argument("-n", "--name", help="Name of notification")
    nrm.add_argument("-f", "--feed", help="Name of feed")
    nrm.set_defaults(func=feedProcessor.rm_noti_wrapper)
    # test_noti
    ntest = notisubparse.add_parser("test", help="Send a test notification")
    ntest.add_argument("-n", "--name", help="Name of notification")
    ntest.add_argument("-f", "--feed", help="Name of feed")
    ntest.set_defaults(func=feedProcessor.test_noti_wrapper)
    # list_feed
    nlist = notisubparse.add_parser("list", help="List notifications")
    nlist.add_argument("-n", "--name", help="Name of notification")
    nlist.set_defaults(func=feedProcessor.list_noti_wrapper)


    """
    Parse arguments and invoke the chosen function; if no arguments are given,
    no config function is called, and all the feeds are checked/parsed instead.
    """
    args = cmdparser.parse_args()
    if args.command != None:
        # call appropriate function
        args.func(args)
        feedProcessor.save()
        exit(0)


    # main loop (parse feeds)
    posts = 0
    logger.info('Searching for feed updates...')
    for feed in feedProcessor.memory.feeds.keys():
        logger.info(f"Checking {feed}...")
        newPost = feedProcessor.check_feed(feed)
        if newPost is None:
            continue
            logger.info('No updates found.')
        else:
            feedProcessor.send_notifications(feed, newPost)
            logger.info(f"Updates found on \"{feed}\", notification sent.")
            posts += 1

    if posts == 0:
        logger.info('No new posts found.')
    else:
        logger.info(f"{posts} new posts found.")

    feedProcessor.save()
    exit(0)


if __name__ == '__main__':
    main()

