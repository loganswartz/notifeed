# notifeed
Automatically get notifications for new posts on your favorite RSS/Atom feeds.

# Installation
```bash
pip3 install notifeed
# or
git clone git@github.com:loganswartz/notifeed.git && pip3 install ./notifeed
```

## Usage
```bash
~ $ notifeed -h
Usage: notifeed [OPTIONS] COMMAND [ARGS]...

Options:
  --debug     Show debug logging messages
  --db PATH   Path to an SQLite database, or where to save a new one
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
Added Dolphin!

$ notifeed add feed MelonDS http://melonds.kuribo64.net/rss.php
Added MelonDS!

$ notifeed list feeds
Currently watching:
  Dolphin (https://dolphin-emu.org/blog/feeds/)
  MelonDS (http://melonds.kuribo64.net/rss.php)

$ notifeed delete feed Dolphin
Deleted Dolphin!
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
Added notification for new posts to Dolphin!

$ notifeed list notifications
Configured notifications:
  New posts to Dolphin --> MySlackWorkspace

$ notifeed delete notification Dolphin MySlackWorkspace
Disabled notifications for Dolphin on MySlackWorkspace
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
- [ ] Email

Currently, Slack and Discord are supported. Other connectors can be added by
implementing a subclass of the `NotificationChannelAsync` class, specifically
the `notify` method. `notify` is called with one argument, `post` (which is of
type `notifeed.Post`), when a new post is found on a feed.  Notifeed will
automatically import any NotificationChannel subclasses found in modules within
the `notifications` folder of this repo, and the `notifications/plugins` path
specifically is gitignore'd to allow symlinking your own modules into an
importable location.

# Misc
Configuration data is stored in an SQLite database file. By default, this lives
in the root of the project folder.

## Service Installation
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
Once the service is running, you can setup notifications, feeds, etc as you
would normally with the `notifeed` command.
