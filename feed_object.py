#!/usr/bin/env python3

import atoma
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse, urlunparse
from pathlib import Path
from notifeed.utils import strip_html
from calendar import timegm


class Feed(object):
    """
    A (really) simple, protocol-agnostic, Feed class. I use this I don't
    have to worry about handling RSS and Atom feeds separately. I convert any
    RSS or Atom feeds to a Feed object as soon as I fetch them so that all
    feeds appear identical in other parts of the program.
    """

    def __init__(self, url: str, feed):

        if isinstance(feed, dict):
            """
            Allow us to initialize from JSON, url is a misnomer in this case
            but fits the other method better, which should be the only init
            method used by users, JSON should only be for restoring from config
            """
            self.type = feed['type']
            self.source = feed['source']
            self.domain = feed['domain']
            self.favicon = feed['favicon']
            self.entries = [FeedEntry(entry) for entry in feed['entries']]
            self.notifications = feed['notifications']
        else:
            self.entries = []
            self.notifications = []

            if isinstance(feed, atoma.atom.AtomFeed):
                self.type = 'atom'
                entries = feed.entries
            elif isinstance(feed, atoma.rss.RSSChannel):
                self.type = 'rss'
                entries = feed.items
            else:
                raise('Feed format not supported.')

            self.source = url

            metadata = self.fetch_metadata(self.source)
            self.domain = metadata['domain']
            self.favicon = metadata['favicon']

            # convert to FeedEntry object
            for entry in entries:
                self.entries.append(FeedEntry(entry))


    def fetch_metadata(self, url: str):
        """
        Fetch metadata on the feed's origin based on the feed url
        """
        uri = urlparse(url)
        uri._replace(path=Path(uri.path).parent.name)
        new_url = urlunparse(uri)
        html = BeautifulSoup(requests.get(new_url).content, 'html.parser')

        results = {}

        # add all wanted metadata to the dict
        results['domain'] = urlparse(url).netloc

        try:
            favicon = html.find(rel='icon').attrs.get('href', '')
            if favicon.scheme != 'https' or favicon.scheme != 'http':
                favicon.scheme = 'http'
            results['favicon'] = urlunparse(favicon)
        except:
            results['favicon'] = ""   # favicon not found

        return results


    def to_JSON(self):
        data = {
            'type': self.type,
            'source': self.source,
            'domain': self.domain,
            'favicon': self.favicon,
            'entries': [entry.to_JSON() for entry in self.entries],
            'notifications': self.notifications
        }

        return data



class FeedEntry(object):
    """
    A (really) simple, protocol-agnostic, Feed Entry class. In the same vein as
    the Feed object, this is meant to simplify working with RSS and Atom feeds
    so that there doesn't need to be any special handling based on the type of
    feed you are working with.

    Publish time is stored as Unix seconds (UTC).
    """

    def __init__(self, entry = None):

        if entry is None:
            raise "Entry cannot be empty"
        elif isinstance(entry, dict):
            self.title = entry['title']
            self.link = entry['link']
            self.publish_date = entry['publish_date']
            self.summary = ''
            self.author = {
                "name": entry['author']['name'] or "",
                "link": entry['author']['link'] or ""
            }
            self.thumbnail = entry.get('thumbnail', '')
        elif isinstance(entry, atoma.atom.AtomEntry):
            self.title = entry.title.value
            self.link = entry.id_
            self.publish_date = timegm(entry.updated.utctimetuple())

            # try to get description, if that fails, try content_encoded, if
            # even that fails, default to empty string
            try:
                self.summary = (strip_html(entry.summary.value) or
                                strip_html(entry.content.value) or "")

                self.author = {
                    "name": entry.authors[0].name or "",
                    "link": entry.authors[0].uri or ""
                }
            except Exception:
                pass

            for link in entry.links:
                if link.type_ is not None and "image" in link.type_:
                    self.thumbnail = link.href
                    break
        elif isinstance(entry, atoma.rss.RSSItem):
            self.title = entry.title
            self.link = entry.link
            self.publish_date = timegm(entry.pub_date.utctimetuple())

            # try to get description, if that fails, try content_encoded, if
            # even that fails, default to empty string
            try:
                self.summary = (strip_html(entry.description) or
                                strip_html(entry.content_encoded) or "")
            except Exception:
                pass

            self.author = {
                "name": entry.author or "",
                "link": ""
            }

            self.thumbnail = ''
        else:
            raise('Feed type not supported')


    def to_JSON(self):
        data = {
            'title': self.title,
            'link': self.link,
            'publish_date': self.publish_date,
        }
        try:
            data['summary'] = self.summary or ""
            data['author'] = self.author or {"name":"", "link":""}
            data['thumbnail'] = self.thumbnail or ""
        except Exception:
            pass

        return data

