#!/usr/bin/env python3

import requests
import atoma
import notifeed

def definePath(path: str):
    if path == None:
        return Path.cwd()
    else:
        return Path(path).expanduser().resolve()


def send_notifications(feed: str, post: atoma.RSSItem):
    endpoints = union(config['config']['global_notifications'],
                      config['feeds'][feed]['notifications'])
    for dest in endpoints:
        notify(dest, feed, post)


def notify(dest: str, feed: str, post: atoma.RSSItem)
    data = {
        "attachments": {
            "fallback":f"New post from {feed}: {post.title}",
            "pretext":f"New post from {feed}:",
            "color":"good",
            "fields": {
                "title":f"<{post.link}|{post.title}>",
                "value":post.description,
                "short":false
            }
        }
    }
    notification = requests.post(url=config['notifications'][dest],
                                 json=data)
    return notification.ok


def main():
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

