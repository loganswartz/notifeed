#!/usr/bin/env python3

import atoma


def get_url(url: str):
    return requests.get(url)


def fetch_feed(url: str):
    try:
        feed = atoma.parse_atom_bytes(get_url(url).content)
    except:
        feed = atoma.parse_rss_bytes(get_url(url).content)
    return feed


def add_feed(name: str, url: str):
    feed = fetch_feed(url)
    config['feeds'][name] = {'source': feed.link,
                    'latest_post_time': feed.items[0].pub_date.timetuple(),
                    'latest_post_name': feed.items[0].title}


def check_feed(name: str):
    # fetch newer version of feed
    feedUrl = config['feeds'][name]['source']
    feed = fetch_feed(feedUrl)

    fetchedTitle = feed.items[0].title
    fetchedTime = feed.items[0].pub_date.timetuple()
    storedTitle = config[name]['latest_post_name']
    storedTime = config[name]['latest_post_time']

    # following line for eventually comparing latest post dates
    if fetchedTime > storedTime and fetchedTitle != storedTitle:
        update_stored_feed(name, feed.items[0])
        return feed.items[0]
    else:
        return None


def update_stored_feed(name: str, feed: atoma.RSSItem):
    config['feeds'][name]['source'] = feed.link
    config['feeds'][name]['latest_post_name'] = feed.title
    config['feeds'][name]['latest_post_time'] = feed.pub_date.timetuple()

