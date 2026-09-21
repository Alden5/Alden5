#!/bin/sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
cd "$SCRIPT_DIR"

if [ "$(id -u)" -ne 0 ]; then
    echo "Run this installer as root (for example: sudo WIKIMEDIA_CONTACT=you@example.com ./install.sh)" >&2
    exit 1
fi

if [ -z "${WIKIMEDIA_CONTACT:-}" ]; then
    echo "WIKIMEDIA_CONTACT is required by Wikimedia API policy." >&2
    echo "Example: sudo WIKIMEDIA_CONTACT=you@example.com ./install.sh" >&2
    exit 1
fi

case "$WIKIMEDIA_CONTACT" in
    *'
'*)
        echo "WIKIMEDIA_CONTACT must be a single line." >&2
        exit 1
        ;;
esac

if [ -n "${NTFY_TOPIC:-}" ]; then
    case "$NTFY_TOPIC" in
        *[!A-Za-z0-9_-]*)
            echo "NTFY_TOPIC may contain only letters, numbers, underscores, and hyphens." >&2
            exit 1
            ;;
    esac
else
    NTFY_TOPIC="trump-watch-$(python3 -c 'import secrets; print(secrets.token_urlsafe(24))')"
fi

if ! id wiki-death-watch >/dev/null 2>&1; then
    useradd --system --no-create-home --home-dir /nonexistent --shell /usr/sbin/nologin wiki-death-watch
fi

install -d -m 0755 /opt/wiki-death-watch
install -m 0755 wiki_death_watch.py /opt/wiki-death-watch/wiki_death_watch.py
install -m 0644 wiki-death-watch.service /etc/systemd/system/wiki-death-watch.service

if [ ! -e /etc/wiki-death-watch.env ]; then
    escaped_contact=$(printf '%s' "$WIKIMEDIA_CONTACT" | python3 -c 'import sys; print(sys.stdin.read().replace("\\", "\\\\").replace("\"", "\\\""), end="")')
    {
        printf 'NTFY_TOPIC="%s"\n' "$NTFY_TOPIC"
        printf 'WIKIMEDIA_CONTACT="%s"\n' "$escaped_contact"
        printf 'POLL_SECONDS="20"\n'
    } > /etc/wiki-death-watch.env
    chmod 0600 /etc/wiki-death-watch.env
else
    NTFY_TOPIC=$(awk -F= '$1 == "NTFY_TOPIC" {gsub(/^"|"$/, "", $2); print $2}' /etc/wiki-death-watch.env)
    echo "Keeping the existing /etc/wiki-death-watch.env configuration."
fi

systemctl daemon-reload
systemctl enable --now wiki-death-watch.service

echo
echo "Installed and started wiki-death-watch."
echo "Subscribe to this ntfy.sh topic on your iPhone:"
echo
echo "  $NTFY_TOPIC"
echo
echo "Then test delivery with:"
echo "  sudo sh -c 'set -a; . /etc/wiki-death-watch.env; exec \\"
echo "    /opt/wiki-death-watch/wiki_death_watch.py --test-notification'"
echo
echo "View service logs with:"
echo "  journalctl -u wiki-death-watch -f"
