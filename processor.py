#!/usr/bin/env python3

# builtins
import json
from pathlib import Path
from time import struct_time as Time
from argparse import Namespace

# 3rd party modules
from atoma import parse_rss_bytes, parse_atom_bytes
import requests

# my modules
from notifeed import config_path
from notifeed.utils import definePath, strip_html, truncate, union
from notifeed.feed_object import Feed, FeedEntry


class Memory(object):
    """
    An object to handle the loading, saving, and interpreting of config files.

    Typically used as a subobject in a FeedProcessor, and holds all the feed
    and notification data when we are working with it.
    """

    def __init__(self):
        self.config = {"update_interval": 15, "global_notifications": []}
        self.feeds = {}
        self.notifications = {}


    def load_config(self, path: Path):
        """
        Read a JSON config file from disk and convert it into a python object.
        """
        if not path.exists():
            self.save_config(path)
            print(f"Config not found, new config file was created at '{path}'")
        else:
            with open(path) as file:
                config_json = json.load(file)

            self.config = config_json['config']
            self.feeds = config_json['feeds']
            self.notifications = config_json['notifications']

            # reconvert latest_post_time time data back to struct_time object
            for entry in self.feeds.values():
                entry['latest_post_time'] = Time(entry['latest_post_time'])


    def save_config(self, path: Path = definePath(config_path)):
        """
        Write data to a JSON config file on disk.
        """
        config_json = {"config": self.config, "feeds": self.feeds,
                      "notifications": self.notifications}
        with open(path, 'w') as file:
            json.dump(config_json, file, indent=4)


class FeedProcessor(object):
    """
    An object to check, fetch, parse, manipulate, and save RSS/Atom feeds.

    Contains a Memory subobject that acts as the store of all the working data.
    All the feed checking and decision-making on whether or not a new post
    exists happens in functions of the FeedProcessor.
    """

    def __init__(self):
        self.memory = Memory()


    def load(self, path: Path = definePath(config_path)):
        """Wrapper for Memory.load_config()"""
        self.memory.load_config(path)


    def save(self, path: Path = definePath(config_path)):
        """Wrapper for Memory.save_config()"""
        self.memory.save_config(path)


    def fetch_feed(self, url: str):
        """
        Fetch a new copy of a remote RSS/Atom feed for parsing by check_feed()
        """
        try:
            feed = Feed(parse_atom_bytes(requests.get(url).content))
        except:
            feed = Feed(parse_rss_bytes(requests.get(url).content))
        return feed


    def check_feed(self, name: str):
        """
        Fetch a feed from its source, compare it to the local data from the
        last fetch request, and determine if the feed has changed. Returns the
        latest feed item if a new one is found, otherwise returns none.
        """
        # fetch newer version of feed
        feed_url = self.memory.feeds[name]['source']
        fresh_feed = self.fetch_feed(feed_url)

        fetched_title = fresh_feed.entries[0].title
        fetched_time = fresh_feed.entries[0].publish_date
        stored_title = self.memory.feeds[name]['latest_post_name']
        stored_time = self.memory.feeds[name]['latest_post_time']

        # following line for eventually comparing latest post dates
        if fetched_time > stored_time or fetched_title != stored_title:
            self.update_stored_feed(name, fresh_feed.entries[0])
            return fresh_feed.entries[0]
        else:
            return None


    def update_stored_feed(self, name: str, feed: FeedEntry):
        """
        Update the 'latest post' data of a feed.
        """
        self.memory.feeds[name]['latest_post_name'] = feed.title
        self.memory.feeds[name]['latest_post_time'] = feed.publish_date


    def create_feed(self, name: str, url: str):
        """
        Create a new feed to be monitored. Name is a nickname for the feed
        (only for use by the user), and url is the URL of the actual RSS/Atom
        feed.
        """
        feed = self.fetch_feed(url)
        self.memory.feeds[name] = {'source': url,
                        'latest_post_time': feed.entries[0].publish_date,
                        'latest_post_name': feed.entries[0].title,
                        'notifications': []}


    def destroy_feed(self, name: str):
        """
        Destroy a previously-added feed.
        """
        del self.memory.feeds[name]


    def list_feed(self):
        """Print a list of all currently added feeds."""
        string = '\nFeeds:\n\n'
        for name, feed in self.memory.feeds.items():
            string += f"{name} ({feed['source']})\n"
        print(string)


    def create_noti(self, name: str, type: str, data: str):
        """
        Create a notification endpoint which can later be assigned to a feed
        via the 'add_noti' command. Type is the type of service the endpoint is
        (slack, email, text, etc) and data is any data associated with that
        endpoint (email addresses, webhook urls, phone numbers, etc). Name is a
        nickname purely for reference by the user (does not affect processing
        in any way).
        """
        self.memory.notifications[name] = {
                "type": type,
                "data": data
                }


    def destroy_noti(self, name: str):
        """
        Destroy a notification endpoint and remove all instances from any
        existing feeds.
        """
        if name == "global":
            self.memory.config['global_notifications'].remove(name)
        else:
            del self.memory.notifications[name]

        # remove all existing feed assignments from that notification source
        for feed in self.memory.feeds.values():
            feed['notifications'].remove(name)


    def add_noti(self, noti: str, feed: str):
        """
        Assign an existing notification source to an existing feed.
        """
        if feed == "global":
            self.memory.config['global_notifications'].append(noti)
        else:
            self.memory.feeds[feed]['notifications'].append(noti)


    def rm_noti(self, noti: str, feed: str):
        """
        Remove a previously-assigned notification source from a feed.
        """
        if feed == "global":
            self.memory.config['global_notifications'].remove(noti)
        else:
            self.memory.feeds[feed]['notifications'].remove(noti)


    def test_noti(self, noti: str, feed: str):
        """
        Send a test notification using the latest post from the specified feed
        and notification endpoint.
        """
        post = self.fetch_feed(self.memory.feeds[feed]['source']).entries[0]
        self.notify(noti, feed, post)


    def list_noti(self):
        """Lists all currently added notification endpoints."""
        string = '\nNotifications:\n\n'
        for name, noti in self.memory.notifications.items():
            string += f"{name} (type: {noti['type']})\n"
            string += f" --> Data: {noti['data']}\n"
        print(string)


    """
    A bunch of wrapper functions to allow for them to be called through
    argparse. If I didn't do this, I'd have to make all my functions have
    a single parameter and run everything through argparse, which would make
    calling them very difficult in basically every other situation.
    """
    def create_feed_wrapper(self, args: Namespace):
        self.create_feed(args.name, args.url)

    def destroy_feed_wrapper(self, args: Namespace):
        self.destroy_feed(args.name)

    def list_feed_wrapper(self, args: Namespace):
        self.list_feed()

    def create_noti_wrapper(self, args: Namespace):
        self.create_noti(args.name, args.type, args.data)

    def destroy_noti_wrapper(self, args: Namespace):
        self.destroy_noti(args.name)

    def add_noti_wrapper(self, args: Namespace):
        self.add_noti(args.name, args.feed)

    def rm_noti_wrapper(self, args: Namespace):
        self.rm_noti(args.name, args.feed)

    def test_noti_wrapper(self, args: Namespace):
        self.test_noti(args.name, args.feed)

    def list_noti_wrapper(self, args: Namespace):
        self.list_noti()


    def send_notifications(self, feed: str, post: FeedEntry):
        """
        Send all notifications about a new post to all assigned notification
        endpoints.

        Calculated via a union of global notifications and feed-specific
        notifications.
        """
        global_list = self.memory.config['global_notifications']
        local_list = self.memory.feeds[feed]['notifications']

        # combine lists via union
        endpoints = union(global_list, local_list)
        for dest in endpoints:
            self.notify(dest, feed, post)


    def notify(self, dest: str, feed: str, post: FeedEntry):
        """
        Send a single notification for a single post to a single endpoint.
        """
        data = self.build_payload(dest, feed, post)
        post = requests.post(url=self.memory.notifications[dest]['data'],
                                     json=data)
        return post.ok


    def build_payload(self, dest: str, feed: str, post: FeedEntry):
        """
        Builds the JSON (or other) payload for whatever notification type you
        have specified.

        Currently, only Slack webhooks are supported, but adding in support for
        other webhooks and/or endpoints (email, text, etc) could be added later
        on down the line.
        """
        if self.memory.notifications[dest]['type'] == 'slack':
            data = {
                "attachments": [{
                    "fallback":f"New post from {feed}: {post.title}",
                    "pretext":f"New post from <{post.link}|{feed}>:",
                    "color":"good",
                    "fields": [{
                        "title":post.title,
                        "value":truncate(strip_html(post.summary), 250),
                        "short":False
                    }]
                }]
            }

        return data

