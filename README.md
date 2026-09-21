# Wikipedia death-notice monitor

This small Python service watches the English Wikipedia article for Donald
Trump and sends an [ntfy](https://ntfy.sh/) notification if the visible
infobox or opening paragraph begins reporting that he has died.

The message deliberately says **possible Wikipedia update**. Wikipedia can be
vandalized, so the notification links to the exact revision and should not be
treated as independent confirmation.

## What it does

- Polls only the latest revision ID every 20 seconds.
- Downloads the rendered lead section only when the revision changes.
- Detects a visible `Died` infobox row or a death-date range plus past tense in
  the opening paragraph.
- Checks Wikidata `P570` for extra context, without requiring it before
  alerting.
- Sends one alert when the notice appears and another if it is removed.
- Persists its state and retries failed API or ntfy requests.
- Uses only the Python standard library.

## 1. Prepare the iPhone

1. Install the **ntfy** app from the App Store.
2. Allow notifications for it in iOS Settings.
3. Complete the server installation below.
4. Subscribe in the app to the random topic printed by the installer, using
   `https://ntfy.sh` as the server.
5. Run the test-notification command printed by the installer.

Treat the topic name like a password. Anyone who knows an unprotected ntfy
topic can publish to it.

## 2. Install on Ubuntu or Debian

The installer creates a locked-down system user, installs the script under
`/opt`, creates a private configuration file, and starts a hardened systemd
service.

```bash
git clone https://github.com/Alden5/Alden5.git
cd Alden5
sudo WIKIMEDIA_CONTACT="your-email@example.com" ./install.sh
```

Use a real contact email, website, or Wikimedia user page. Wikimedia requires
automated API clients to identify their operator. The address is sent only in
the HTTP `User-Agent`.

To select your own ntfy topic:

```bash
sudo \
  WIKIMEDIA_CONTACT="your-email@example.com" \
  NTFY_TOPIC="trump-watch-use-at-least-24-random-characters" \
  ./install.sh
```

Useful commands:

```bash
# Follow logs
sudo journalctl -u wiki-death-watch -f

# Check service health
systemctl status wiki-death-watch

# Send a test notification using the installed configuration
sudo sh -c 'set -a; . /etc/wiki-death-watch.env; exec \
  /opt/wiki-death-watch/wiki_death_watch.py --test-notification'

# Restart after changing /etc/wiki-death-watch.env
sudo systemctl restart wiki-death-watch
```

## Manual operation

Python 3.9 or newer is sufficient:

```bash
export NTFY_TOPIC="your-long-random-topic"
export WIKIMEDIA_CONTACT="your-email@example.com"
python3 wiki_death_watch.py --state-file ./state.json
```

Check once without leaving a process running:

```bash
python3 wiki_death_watch.py --state-file ./state.json --once
```

Supported environment variables:

| Variable | Required | Default | Purpose |
|---|---:|---|---|
| `NTFY_TOPIC` | Yes | — | ntfy topic subscribed to by the phone |
| `WIKIMEDIA_CONTACT` | Yes | — | Contact included in the Wikimedia User-Agent |
| `NTFY_SERVER` | No | `https://ntfy.sh` | ntfy server URL |
| `NTFY_TOKEN` | No | — | Bearer token for a protected ntfy topic |
| `POLL_SECONDS` | No | `20` | Revision check interval; minimum 10 |
| `HTTP_TIMEOUT_SECONDS` | No | `20` | Per-request timeout |
| `STATE_FILE` | No | `/var/lib/wiki-death-watch/state.json` | Persistent state path |
| `LOG_LEVEL` | No | `INFO` | Python logging level |

## Verify changes

```bash
python3 -m unittest -v
sh -n install.sh
python3 -m py_compile wiki_death_watch.py
```

No notification system, including Apple Push Notification service, can
guarantee delivery within exactly one minute. Under normal conditions, the
20-second polling interval leaves substantial time for ntfy and iOS delivery.

