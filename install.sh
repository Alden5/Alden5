#!/bin/sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
cd "$SCRIPT_DIR"

if [ "$(id -u)" -ne 0 ]; then
    echo "Run this installer as root (for example: sudo WIKIMEDIA_CONTACT=you@example.com ./install.sh)" >&2
    exit 1
fi

for command in python3 useradd install awk systemctl; do
    if ! command -v "$command" >/dev/null 2>&1; then
        echo "Required command is missing: $command" >&2
        exit 1
    fi
done

if ! python3 -c 'import sys; raise SystemExit(sys.version_info < (3, 10))'; then
    echo "Python 3.10 or newer is required." >&2
    exit 1
fi

CONFIG_FILE=/etc/wiki-death-watch.env

if [ ! -e "$CONFIG_FILE" ]; then
    if [ -z "${WIKIMEDIA_CONTACT:-}" ]; then
        echo "WIKIMEDIA_CONTACT is required by Wikimedia API policy." >&2
        echo "Example: sudo WIKIMEDIA_CONTACT=you@example.com ./install.sh" >&2
        exit 1
    fi

    for value_name in WIKIMEDIA_CONTACT NTFY_SERVER NTFY_TOKEN; do
        eval "value=\${$value_name:-}"
        case "$value" in
            *'
'*)
                echo "$value_name must be a single line." >&2
                exit 1
                ;;
        esac
    done

    case "${NTFY_SERVER:-https://ntfy.sh}" in
        http://*|https://*) ;;
        *)
            echo "NTFY_SERVER must start with https:// or http://." >&2
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
        if [ "${#NTFY_TOPIC}" -lt 24 ] && [ -z "${NTFY_TOKEN:-}" ]; then
            echo "NTFY_TOPIC must have at least 24 characters unless NTFY_TOKEN is set." >&2
            exit 1
        fi
    else
        NTFY_TOPIC="trump-watch-$(python3 -c 'import secrets; print(secrets.token_urlsafe(24))')"
    fi
else
    NTFY_TOPIC=$(awk -F= '$1 == "NTFY_TOPIC" {sub(/^[^=]*=/, ""); gsub(/^"|"$/, ""); print; exit}' "$CONFIG_FILE")
    if [ -z "$NTFY_TOPIC" ]; then
        echo "$CONFIG_FILE exists but contains no NTFY_TOPIC." >&2
        exit 1
    fi
    echo "Keeping the existing $CONFIG_FILE configuration."
fi

if ! id wiki-death-watch >/dev/null 2>&1; then
    useradd --system --no-create-home --home-dir /nonexistent --shell /usr/sbin/nologin wiki-death-watch
fi

install -d -m 0755 /opt/wiki-death-watch
install -m 0755 wiki_death_watch.py /opt/wiki-death-watch/wiki_death_watch.py
install -m 0644 wiki-death-watch.service /etc/systemd/system/wiki-death-watch.service

if [ ! -e "$CONFIG_FILE" ]; then
    escaped_contact=$(printf '%s' "$WIKIMEDIA_CONTACT" | python3 -c 'import sys; print(sys.stdin.read().replace("\\", "\\\\").replace("\"", "\\\""), end="")')
    escaped_server=$(printf '%s' "${NTFY_SERVER:-https://ntfy.sh}" | python3 -c 'import sys; print(sys.stdin.read().replace("\\", "\\\\").replace("\"", "\\\""), end="")')
    {
        printf 'NTFY_TOPIC="%s"\n' "$NTFY_TOPIC"
        printf 'WIKIMEDIA_CONTACT="%s"\n' "$escaped_contact"
        printf 'NTFY_SERVER="%s"\n' "$escaped_server"
        if [ -n "${NTFY_TOKEN:-}" ]; then
            escaped_token=$(printf '%s' "$NTFY_TOKEN" | python3 -c 'import sys; print(sys.stdin.read().replace("\\", "\\\\").replace("\"", "\\\""), end="")')
            printf 'NTFY_TOKEN="%s"\n' "$escaped_token"
        fi
        printf 'POLL_SECONDS="20"\n'
    } > "$CONFIG_FILE"
fi
chmod 0600 "$CONFIG_FILE"

systemctl daemon-reload
systemctl enable --now wiki-death-watch.service
if ! systemctl is-active --quiet wiki-death-watch.service; then
    echo "The service did not stay running. Recent logs:" >&2
    journalctl -u wiki-death-watch.service -n 30 --no-pager >&2 || true
    exit 1
fi

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
