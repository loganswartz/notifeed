# notifeed
Simple daemon to regularly parse RSS/Atom feeds and send push notifications/webhooks when new content is detected.

## How to Use
* Clone the repo locally to your machine
* Add the repo to your python path (or move it into your path)
* (Optional) Change the default config location by changing the `config_path` variable in \_\_init\_\_.py (currently defaults to `~/.notifeed`)
* Use the helper functions to configure notifeed:

Function Call | Purpose
--------------|--------------
`python3 notifeed -h` or `python3 notifeed <feed\|notification> -h` or etc | See help messages and cmdline arguments on all the available commands. Help message changes depending on the options specified in conjunction with the `-h` flag.
`python3 notifeed feed <create\|destroy> -n NAME (-u URL)` | Create or remove feeds from notifeed
`python3 notifeed notification <create\|destroy> -n NAME (-t TYPE -d DATA)` | Create or destroy notifications from notifeed. `create` requires the 2 additional arguments in parentheses whereas destroy only needs the name. `-t TYPE` is the type of the notification endpoint (currently only 'slack' is supported), and `-d DATA` is data associated with that notification type (for slack, it's your [webhook](https://api.slack.com/incoming-webhooks) URL)
`python3 notifeed notification <add\|rm> -n NOTIFICATION -f FEED` | assign or remove a notification endpoint to/from a feed. Use `-f 'global'` to assign/remove a notification from all feeds.
`python3 notifeed notification test -n NOTIFICATION -f FEED` | Test a notification source, using the most recent post from the given feed.
`python3 notifeed` | Parse all configured feeds, check for new posts, and send the appropriate notifications.

* Configure a cronjob to run `python3 notifeed` at your desired refresh interval (~15 or 30 minutes would probably be the lowest I'd go)
