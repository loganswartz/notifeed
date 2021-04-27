# notifeed
Automatically get notifications for new posts on your favorite RSS/Atom feeds.

## Usage
```bash
~/notifeed $ python3 -m notifeed -h  # for brevity, referred to as just `notifeed` from now on
Usage: notifeed [OPTIONS] COMMAND [ARGS]...

Options:
  -h, --help  Show this message and exit.

Commands:
  add
  delete
  list
  run
  set
```
Notifeed has 3 main things that need to be configured:
* Feeds to watch
* Available notification channels
* The actual configured notifications (i.e. on a new post to X, send a notification to Y)

To configure these values, you can use `notifeed add <feed|channel|notification> ...`.
Here are some examples on how to use them:

### Working with Feeds
```bash
$ notifeed add feed Dolphin https://dolphin-emu.org/blog/feeds/

$ notifeed add feed MelonDS http://melonds.kuribo64.net/rss.php

$ notifeed list feeds

$ notifeed delete feed Dolphin

```

### Working with Channels
```bash
$ notifeed add channel --type slack MySlackWorkspace <Slack Webhook URL>
Added MySlackWorkspace!

$ notifeed add channel MyDiscordChannel <Discord Webhook URL>
Added MyDiscordChannel!

$ notifeed delete channel MySlackWorkspace
Deleted MySlackWorkspace!

$ notifeed list channels
Available notification channels:
  MyDiscordChannel (discord, <Discord Webhook URL>)
```

### Working with Notifications
```bash
$ notifeed add notification Dolphin MySlackWorkspace

$ notifeed list notifications

$ notifeed delete notification Dolphin MySlackWorkspace

```

Notifeed will start listening for new posts when you start it via `notifeed run`.
The best way to deploy this is setting it up as a systemctl service, using the
provided template service file.

### Set poll interval
```bash
$ notifeed set poll_interval 1800  # 1800 seconds = 30 minutes
```
The default polling interval is 15 minutes.

# Available Notification Channels
- [X] Slack
- [X] Discord

Currently, Slack and Discord are supported. Other connectors can be added by
implementing a subclass of the `NotificationChannel` class, specifically the
`notify` method. `notify` is called with one argument, `post` (which is of type
`notifeed.Post`), when a new post is found on a feed.  Notifeed will
automatically import any NotificationChannel subclasses found in modules within
the `notifications` folder of this repo, and the `notifications/plugins` path
specifically is gitignore'd to allow symlinking your own modules into an
importable location.

# Misc
Configuration data is stored in an SQLite database file in the root of the project
folder.

## Installation
Install the service file by symbolically linking to it from `/etc/systemd/system/`:
```bash
$ sudo ln -s /path/to/notifeed/notifeed.service /etc/systemd/system/notifeed.service
```
Then, reload the service daemon, and start the service:
```bash
$ sudo systemctl daemon-reload && sudo systemctl start notifeed
```
You'll probably also want to start the service automatically on startup:
```bash
$ sudo systemctl enable notifeed
```
