#!/usr/bin/env python3

# 3rd party modules
import atoma
import requests

def send_notifications(feed: str, post: atoma.RSSItem):
    endpoints = union(config['config']['global_notifications'],
                      config['feeds'][feed]['notifications'])
    for dest in endpoints:
        notify(dest, feed, post)


def notify(dest: str, feed: str, post: atoma.RSSItem)
    data = build_payload(dest, feed, post)
    notification = requests.post(url=config['notifications'][dest],
                                 json=data)
    return notification.ok


def build_payload(dest: str, feed: str, post: atoma.RSSItem):
    if dest['type'] == 'slack':
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

    return data

