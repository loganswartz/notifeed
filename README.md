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
```
Notifeed has 3 main things that need to be configured:
* Feeds to watch
* Available notification channels
* The actual configured notifications (i.e. on a new post to X, send a notification to Y)

To configure these values, you can use `notifeed add <feed|channel|notification> ...`.
Here are some examples on how to use them:

### Add a new feed
```bash
$ notifeed add feed Dolphin https://dolphin-emu.org/blog/feeds/
$ notifeed add feed MelonDS http://melonds.kuribo64.net/rss.php
```

### Add a new channel
```bash
$ notifeed add channel --type slack MySlackWorkspace <Slack Webhook URL>
```

### Add a new notification
```bash
$ notifeed add notification Dolphin MySlackWorkspace
```

Notifeed will start listening for new posts when you start it via `notifeed run`.
The best way to deploy this is setting it up as a systemctl service, using the
provided template service file.

# Misc
Configuration data is stored in an SQLite database file in the root of the project
folder. The default polling interval is 15 minutes, although this can be changed by
changing the value in the DB.

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
