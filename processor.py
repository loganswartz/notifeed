#!/usr/bin/env python3

# builtins
import json
from pathlib import Path
from time import struct_time as Time
from argparse import Namespace

# 3rd party modules
from atoma import parse_rss_bytes, parse_atom_bytes
from atoma.rss import RSSItem
import requests

# my modules
from notifeed.utils import definePath


class Memory(object):

    def __init__(self):
        self.config = {"update_interval": 15, "global_notifications": []}
        self.feeds = {}
        self.notifications = {}


    def load_config(self, path: Path):
        if not path.exists():
            self.save_config(path)
            print(f"Config not found, new config file was created at '{path}'")
        else:
            with open(path) as file:
                configJSON = json.load(file)

            self.config = configJSON['config']
            self.feeds = configJSON['feeds']
            self.notifications = configJSON['notifications']

            # reconvert latest_post_time time data back to struct_time object
            for entry in self.feeds.values():
                entry['latest_post_time'] = Time(entry['latest_post_time'])


    def save_config(self, path: Path):
        configJSON = {"config": self.config, "feeds": self.feeds,
                      "notifications": self.notifications}
        with open(path, 'w') as file:
            json.dump(configJSON, file, indent=4)


class FeedProcessor(object):


    def __init__(self):
        self.memory = Memory()


    def load(self, path: Path = definePath('~/.notifeed')):
        self.memory.load_config(path)


    def save(self, path: Path = definePath('~/.notifeed')):
        self.memory.save_config(path)


    def fetch_feed(self, url: str):
        """
        Fetch a new copy of a remote RSS/Atom feed for parsing by check_feed()
        """
        try:
            feed = parse_atom_bytes(requests.get(url).content)
        except:
            feed = parse_rss_bytes(requests.get(url).content)
        return feed


    def check_feed(self, name: str):
        """
        Fetch a feed from its source, compare it to the local data from the
        last fetch request, and determine if the feed has changed. Returns the
        latest feed item if a new one is found, otherwise returns none.
        """
        # fetch newer version of feed
        feedUrl = self.memory.feeds['source']
        freshfeed = fetch_feed(feedUrl)

        fetchedTitle = freshFeed.items[0].title
        fetchedTime = freshFeed.items[0].pub_date.timetuple()
        storedTitle = self.memory.feeds[name]['latest_post_name']
        storedTime = self.memory.feeds[name]['latest_post_time']

        # following line for eventually comparing latest post dates
        if fetchedTime > storedTime and fetchedTitle != storedTitle:
            update_stored_feed(name, freshFeed.items[0])
            return freshFeed.items[0]
        else:
            return None


    def update_stored_feed(self, name: str, feed: RSSItem):
        """
        Update the 'latest post' data of a feed.
        """
        self.memory.feeds[name]['latest_post_name'] = feed.title
        self.memory.feeds[name]['latest_post_time'] = feed.pub_date.timetuple()


    def create_feed(self, name: str, url: str):
        """
        Create a new feed to be monitored. Name is a nickname for the feed 
        (only for use by the user), and url is the URL of the actual RSS/Atom
        feed.
        """
        feed = self.fetch_feed(url)
        self.memory.feeds[name] = {'source': url,
                        'latest_post_time': feed.items[0].pub_date.timetuple(),
                        'latest_post_name': feed.items[0].title,
                        'notifications': []}


    def destroy_feed(self, name: str):
        """
        Destroy a previously-added feed.
        """
        del self.memory.feeds[name]


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
        post = self.fetch_feed(self.memory.feeds[feed]['source']).items[0]
        self.notify(noti, feed, post)


    def create_feed_wrapper(self, args: Namespace):
        self.create_feed(args.name, args.url)

    def destroy_feed_wrapper(self, args: Namespace):
        self.destroy_feed(args.name)

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


    def send_notifications(self, feed: str, post: RSSItem):
        endpoints = union(self.memory.config['global_notifications'],
                          self.memory.feeds[feed]['notifications'])
        for dest in endpoints:
            self.notify(dest, feed, post)


    def notify(self, dest: str, feed: str, post: RSSItem):
        data = self.build_payload(dest, feed, post)
        post = requests.post(url=self.memory.notifications[dest]['data'],
                                     json=data)
        return post.ok


    def build_payload(self, dest: str, feed: str, post: RSSItem):
        if self.memory.notifications[dest]['type'] == 'slack':
            data = {
                "attachments": [{
                    "fallback":f"New post from {feed}: {post.title}",
                    "pretext":f"New post from <{post.link}|{feed}>:",
                    "color":"good",
                    "fields": [{
                        "title":post.title,
                        "value":post.description[0:250] + '...',
                        "short":False
                    }]
                }]
            }

        return data

