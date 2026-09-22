# Wikipedia death-notice monitor

This Python service watches Donald Trump's English Wikipedia article and sends
an [ntfy](https://ntfy.sh/) notification if the visible infobox or opening
paragraph begins reporting that he has died.

The alert says **possible Wikipedia update** because Wikipedia can be
vandalized. It links to the exact revision and is not independent confirmation.

## What it does

- Checks the latest revision ID every 20 seconds.
- Downloads the rendered lead only when the article changes.
- Detects independent visible signals: a `Died` infobox row, a death-date range
  with past tense, an explicit statement that Trump died, or a `YYYY deaths`
  category.
- Checks Wikidata `P570` for context without delaying the initial alert.
- Sends one alert when the notice appears and another if it is removed.
- Persists an explicit true/false result, timestamps, counters, detection
  reasons, errors, and Wikidata status.
- Logs a heartbeat about every five minutes while the article is unchanged.
- Deduplicates alerts and retries temporary failures.
- Runs without third-party Python packages.

## Cost and server recommendation

Buy a Scaleway **STARDUST1-S** CPU Instance. It is enough for this service:
one shared vCPU, 1 GB RAM, 10 GB local storage, and 100 Mbps networking.

Approximate September 2026 cost before tax:

| Resource | Rate | Approximate monthly cost |
|---|---:|---:|
| STARDUST1-S compute | €0.0006/hour | €0.43 |
| 10 GB local storage | €0.000049/GB/hour | €0.36 |
| Public IPv6 | Included | €0 |
| ntfy.sh free service | Free | €0 |
| **Ongoing total** | | **about €0.79/month** |

Scaleway lists storage separately from the instance price. The estimate shown
in the creation wizard is authoritative, and VAT may apply. A flexible IPv4
costs another €0.004/hour, about €2.92/month. The instructions below use IPv4
for installation and then delete it, so it should add only the one-hour
minimum charge.

If STARDUST1-S has no capacity, try `fr-par-1` or `nl-ams-1` later. The simple
fallback is an AWS Lightsail IPv6-only Nano at $3.50/month.

Official references:
[Scaleway pricing](https://www.scaleway.com/en/pricing/virtual-instances/),
[instance creation](https://www.scaleway.com/en/docs/instances/quickstart/),
and [IP billing](https://www.scaleway.com/en/docs/ipam/reference-content/understanding-ip-billing/).

## Complete setup

### 1. Prepare ntfy on the iPhone

1. Install **ntfy** from the iOS App Store.
2. Open iOS **Settings → Notifications → ntfy** and enable notifications,
   sounds, and banners.
3. Leave the app installed. The installer will generate the private topic to
   subscribe to later.

### 2. Create a Scaleway account

1. Go to [console.scaleway.com](https://console.scaleway.com/) and choose
   **Sign up**.
2. Select **Personal project** unless this is for a business.
3. Verify the account and add a billing address and payment card.
4. Scaleway may place a €1 authorization on the card; its documentation says
   this is normally refunded within two days.
5. Enable multi-factor authentication for the account.

### 3. Create and upload an SSH key

On the computer from which you will administer the server:

```bash
ssh-keygen -t ed25519 -a 100 -f ~/.ssh/scaleway-wiki-monitor
cat ~/.ssh/scaleway-wiki-monitor.pub
```

Keep the private file secret. In Scaleway:

1. Open the correct **Project Dashboard**.
2. Open **Credentials → SSH keys → Add SSH key**.
3. Name it `wiki-monitor`, paste the displayed `.pub` line, and save.

### 4. Create a restrictive security group

Scaleway's generated default group allows all inbound traffic, so do not use it
unchanged:

1. Open **CPU & GPU Instances → Security groups**.
2. Create a group named `wiki-monitor`.
3. Set the inbound default policy to **Drop**.
4. Set the outbound default policy to **Accept**.
5. Add one inbound **Accept / TCP / port 22** rule. Restrict its source to your
   current public IPv4 address with `/32`, such as `203.0.113.10/32`.

The monitor needs no inbound ports. This temporary SSH rule can be removed
after installation.

### 5. Buy the instance

1. Open **CPU & GPU Instances → Create Instance → Create CPU Instance**.
2. Select availability zone **Paris 1 (`fr-par-1`)** or
   **Amsterdam 1 (`nl-ams-1`)**.
3. Choose the **STARDUST1-S** offer.
4. Select **Ubuntu 24.04 LTS**.
5. Keep its fixed **10 GB local storage**.
6. Under networking, enable both:
   - **Public IPv4**, temporarily for SSH and GitHub access.
   - **Public IPv6**, which the running monitor will use.
7. Select the `wiki-monitor` security group and the SSH key created above.
8. Name the instance `wiki-death-watch`, review the estimated price, and
   create it.

GitHub's main host is IPv4-only, and Scaleway does not provide managed NAT64.
That is why IPv4 is enabled during installation. Wikipedia and ntfy.sh both
support IPv6, so the monitor itself does not need IPv4 afterward.

### 6. Connect and install

Copy the instance's public IPv4 from its Overview page, then connect:

```bash
ssh -i ~/.ssh/scaleway-wiki-monitor root@SERVER_IPV4
```

On the server, run:

```bash
apt-get update
apt-get install -y ca-certificates git python3
git clone https://github.com/Alden5/Alden5.git
cd Alden5
sudo WIKIMEDIA_CONTACT="your-email@example.com" ./install.sh
```

Use a real contact email, website, or Wikimedia user page. Wikimedia requires
automated clients to identify their operator; the value is sent only in the
HTTP `User-Agent`.

The installer:

- creates a random ntfy topic;
- installs the script in `/opt/wiki-death-watch`;
- stores configuration in `/etc/wiki-death-watch.env`;
- creates an unprivileged service account;
- enables a hardened systemd service; and
- prints the topic and test command.

### 7. Subscribe and test the iPhone

1. Copy the topic printed by the installer.
2. In the ntfy app, add a subscription using server `https://ntfy.sh`.
3. Paste the topic exactly.
4. Back on the server, send a test:

```bash
sudo sh -c 'set -a; . /etc/wiki-death-watch.env; exec \
  /opt/wiki-death-watch/wiki_death_watch.py --test-notification'
```

Do not continue until the iPhone receives the test. Treat the random topic as a
password: anyone who knows an unprotected topic can publish to it.

Confirm the service and its first Wikipedia check:

```bash
systemctl status wiki-death-watch --no-pager
journalctl -u wiki-death-watch -n 30 --no-pager
```

The log should show `Checking Wikipedia revision ...` followed by an explicit
`death_notice_detected=false` result, without repeated errors.

### 8. Confirm it is checking and currently false

Run:

```bash
sudo /opt/wiki-death-watch/wiki_death_watch.py --status
```

A normal result while the article describes a living person looks like:

```text
Monitor health:            HEALTHY
Death notice detected:     false
Last successful check:     2026-09-22 04:00:20 UTC (8s ago)
Last content evaluation:   2026-09-22 03:55:00 UTC
Latest revision checked:   1234567890
Wikidata death date P570:  not set
Detection signals:         0
  - none; the monitored page still appears to describe a living person
Counters:                  17 successful checks, 1 content evaluations, 0 errors, 0 notifications
```

`Last successful check` should advance every 20 seconds. `Last content
evaluation` advances only when Wikipedia publishes a new revision; it is
normal for that value to be older. As long as health is `HEALTHY`, the latest
revision is unchanged and `Death notice detected` is `false`, the service is
actively checking and has found no death notice.

Watch the status update live:

```bash
sudo watch -n 5 /opt/wiki-death-watch/wiki_death_watch.py --status
```

View only check results and five-minute heartbeats:

```bash
sudo journalctl -u wiki-death-watch --since "30 minutes ago" \
  | grep -E 'Evaluation result|Heartbeat'
```

Status exits with code `0` when healthy, `2` when stale, and `1` if no state
exists yet. Persistent state is stored at
`/var/lib/wiki-death-watch/state.json`.

### 9. Remove the paid IPv4

Only do this after the test notification succeeds:

1. In the Scaleway console, open the instance's **Network** section.
2. Detach its flexible IPv4.
3. Open the project's flexible/public IP list and **delete the IPv4
   reservation**. Detaching alone does not stop billing.
4. Keep the public IPv6.
5. Remove the temporary port 22 rule from the security group, leaving inbound
   default **Drop**.
6. Wait about 30 seconds and rerun `--status`. It should remain `HEALTHY` and
   show a newer successful-check time.

After deleting IPv4, direct `git pull` from GitHub will not work and SSH works
only if your own internet connection has IPv6. Scaleway's web console remains
the recovery path. To update later, temporarily reserve and attach an IPv4,
perform the update, then detach **and delete** that IPv4 again.

## Maintenance

### Check health and recent activity

```bash
sudo /opt/wiki-death-watch/wiki_death_watch.py --status
systemctl status wiki-death-watch --no-pager
sudo journalctl -u wiki-death-watch -n 50 --no-pager
```

If status is `STALE`, inspect the logs and restart:

```bash
sudo journalctl -u wiki-death-watch -n 100 --no-pager
sudo systemctl restart wiki-death-watch
sleep 25
sudo /opt/wiki-death-watch/wiki_death_watch.py --status
```

### Update to a newer version

The installed copy does not update itself. Use this procedure whenever this
repository changes:

1. In Scaleway, temporarily reserve and attach a flexible IPv4 if the instance
   is currently IPv6-only.
2. Temporarily restore the security-group TCP port 22 rule for your own public
   IP `/32`.
3. SSH to the server's temporary IPv4:

   ```bash
   ssh -i ~/.ssh/scaleway-wiki-monitor root@SERVER_IPV4
   ```

4. Check that the source checkout has no local changes, download `main`, and
   review the commits that will be installed:

   ```bash
   cd /root/Alden5
   git status --short
   git fetch origin main
   git log --oneline HEAD..origin/main
   ```

   Stop if `git status` prints unexpected files or edits. Do not discard them
   without understanding why they exist.

5. Fast-forward the checkout and reinstall:

   ```bash
   git pull --ff-only origin main
   sudo ./install.sh
   ```

   The installer preserves `/etc/wiki-death-watch.env`, including the topic
   subscribed on the iPhone.

6. Verify the updated files, service, live check, and notification path:

   ```bash
   python3 -m unittest -v
   systemctl status wiki-death-watch --no-pager
   sleep 25
   sudo /opt/wiki-death-watch/wiki_death_watch.py --status
   sudo sh -c 'set -a; . /etc/wiki-death-watch.env; exec \
     /opt/wiki-death-watch/wiki_death_watch.py --test-notification'
   ```

7. Confirm the iPhone receives the test.
8. Detach **and delete** the temporary flexible IPv4 reservation.
9. Remove the temporary inbound port 22 rule.
10. Wait 30 seconds and confirm `--status` remains `HEALTHY`.

If the GitHub repository is private, the server also needs read access before
`git fetch` works. Add a read-only GitHub deploy key:

```bash
ssh-keygen -t ed25519 -f /root/.ssh/github-wiki-monitor -N ""
cat /root/.ssh/github-wiki-monitor.pub
```

In GitHub, open **Repository Settings → Deploy keys → Add deploy key**, paste
that public key, and leave **Allow write access** unchecked. Then configure the
checkout:

```bash
cat >/root/.ssh/config <<'EOF'
Host github.com
  IdentityFile /root/.ssh/github-wiki-monitor
  IdentitiesOnly yes
EOF
chmod 600 /root/.ssh/config
ssh-keyscan github.com >>/root/.ssh/known_hosts
ssh-keygen -lf /root/.ssh/known_hosts
cd /root/Alden5
git remote set-url origin git@github.com:Alden5/Alden5.git
git fetch origin main
```

Before accepting the first SSH connection, compare the displayed host-key
fingerprint with
[GitHub's published SSH fingerprints](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/githubs-ssh-key-fingerprints).
GitHub access still requires the temporary IPv4 because `github.com` does not
provide the needed IPv6 connectivity.

### Change configuration

Edit configuration:

```bash
sudoedit /etc/wiki-death-watch.env
sudo systemctl restart wiki-death-watch
```

The environment file supports:

| Variable | Required | Default | Purpose |
|---|---:|---|---|
| `NTFY_TOPIC` | Yes | generated | Topic subscribed to by the phone |
| `WIKIMEDIA_CONTACT` | Yes | — | Contact in Wikimedia User-Agent |
| `NTFY_SERVER` | No | `https://ntfy.sh` | ntfy server URL |
| `NTFY_TOKEN` | No | — | Bearer token for a protected topic |
| `POLL_SECONDS` | No | `20` | Revision interval; minimum 10 seconds |
| `HTTP_TIMEOUT_SECONDS` | No | `20` | Per-request timeout |
| `STATE_FILE` | No | systemd state directory | Persistent state path |
| `LOG_LEVEL` | No | `INFO` | Python logging level |

If the iPhone stops receiving ntfy notifications, remove and re-add the topic
in the app, then repeat the test-notification command.

## Manual operation and development

Python **3.10 or newer** is required:

```bash
export NTFY_TOPIC="your-long-random-topic"
export WIKIMEDIA_CONTACT="your-email@example.com"
python3 wiki_death_watch.py --state-file ./state.json
```

Check once:

```bash
python3 wiki_death_watch.py --state-file ./state.json --once
```

Run verification:

```bash
python3 -m unittest -v
python3 -m py_compile wiki_death_watch.py
sh -n install.sh
```

No notification system, including Apple Push Notification service, guarantees
delivery within exactly one minute. Under normal conditions, the 20-second
polling interval leaves time for ntfy and iOS delivery.

