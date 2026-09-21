#!/usr/bin/env python3
"""Watch a Wikipedia biography for a visible death notice and notify ntfy."""

from __future__ import annotations

import argparse
import gzip
import json
import logging
import os
import re
import signal
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
from typing import Any


LOG = logging.getLogger("wiki-death-watch")
WIKIPEDIA_API = "https://en.wikipedia.org/w/api.php"
WIKIDATA_API = "https://www.wikidata.org/w/api.php"
ARTICLE_TITLE = "Donald Trump"
WIKIDATA_ITEM = "Q22686"
DEFAULT_STATE_FILE = "/var/lib/wiki-death-watch/state.json"
VERSION = "1.0.0"


class RequestError(RuntimeError):
    def __init__(self, message: str, retry_after: float | None = None) -> None:
        super().__init__(message)
        self.retry_after = retry_after


@dataclass(frozen=True)
class Config:
    ntfy_topic: str
    ntfy_server: str
    ntfy_token: str | None
    contact: str
    poll_seconds: float
    state_file: Path
    timeout_seconds: float

    @property
    def user_agent(self) -> str:
        return f"WikiDeathWatch/{VERSION} ({self.contact}) Python/{sys.version_info.major}.{sys.version_info.minor}"


class LeadHTMLParser(HTMLParser):
    """Extract the infobox Died field and visible lead paragraphs."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._capture_label = False
        self._label_parts: list[str] = []
        self._awaiting_died_value = False
        self._capture_died_value = False
        self._died_parts: list[str] = []
        self._paragraph_depth = 0
        self._paragraph_parts: list[str] = []
        self.died_value: str | None = None
        self.paragraphs: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        classes = set((attributes.get("class") or "").split())
        if tag == "th" and "infobox-label" in classes:
            self._capture_label = True
            self._label_parts = []
        elif tag == "td" and self._awaiting_died_value:
            self._capture_died_value = True
            self._died_parts = []
            self._awaiting_died_value = False

        if tag == "p":
            if self._paragraph_depth == 0:
                self._paragraph_parts = []
            self._paragraph_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag == "th" and self._capture_label:
            label = normalize_text("".join(self._label_parts)).casefold()
            self._capture_label = False
            self._awaiting_died_value = label == "died"
        elif tag == "td" and self._capture_died_value:
            value = normalize_text("".join(self._died_parts))
            if value and value not in {"—", "-", "N/A"}:
                self.died_value = value
            self._capture_died_value = False

        if tag == "p" and self._paragraph_depth:
            self._paragraph_depth -= 1
            if self._paragraph_depth == 0:
                paragraph = normalize_text("".join(self._paragraph_parts))
                if paragraph:
                    self.paragraphs.append(paragraph)

    def handle_data(self, data: str) -> None:
        if self._capture_label:
            self._label_parts.append(data)
        if self._capture_died_value:
            self._died_parts.append(data)
        if self._paragraph_depth:
            self._paragraph_parts.append(data)


def normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def detect_death_notice(html: str) -> tuple[bool, list[str], str | None]:
    parser = LeadHTMLParser()
    parser.feed(html)
    reasons: list[str] = []

    if parser.died_value:
        reasons.append(f'infobox shows "Died: {parser.died_value}"')

    lead = next(
        (p for p in parser.paragraphs if "Donald" in p and "Trump" in p),
        parser.paragraphs[0] if parser.paragraphs else None,
    )
    if lead:
        match = re.search(
            r"\bDonald\s+John\s+Trump\s*\(([^)]{1,180})\)\s+was\b",
            lead,
            flags=re.IGNORECASE,
        )
        if match:
            dates = match.group(1).strip()
            has_range = bool(re.search(r"\d{4}\s*[–—-]\s*(?:\w+\s+\d{1,2},\s+)?\d{4}", dates))
            if has_range and not dates.casefold().startswith("born "):
                reasons.append(f'lead uses a death-date range and past tense: "{dates}"')

    return bool(reasons), reasons, lead


def _retry_after(headers: Any) -> float | None:
    value = headers.get("Retry-After") if headers else None
    if not value:
        return None
    try:
        return max(0.0, float(value))
    except ValueError:
        return None


def request_json(
    url: str,
    *,
    user_agent: str,
    timeout: float,
    method: str = "GET",
    payload: dict[str, Any] | None = None,
    token: str | None = None,
) -> dict[str, Any]:
    body = None
    headers = {
        "Accept": "application/json",
        "Accept-Encoding": "gzip",
        "User-Agent": user_agent,
    }
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = f"Bearer {token}"

    request = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read()
            if response.headers.get("Content-Encoding") == "gzip":
                raw = gzip.decompress(raw)
            result = json.loads(raw.decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise RequestError(
            f"{method} {url} returned HTTP {exc.code}",
            retry_after=_retry_after(exc.headers),
        ) from exc
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise RequestError(f"{method} {url} failed: {exc}") from exc

    if isinstance(result, dict) and "error" in result:
        error = result["error"]
        raise RequestError(f"API error {error.get('code', 'unknown')}: {error.get('info', error)}")
    if not isinstance(result, dict):
        raise RequestError(f"{method} {url} returned an unexpected response")
    return result


def wikipedia_query(config: Config, params: dict[str, str]) -> dict[str, Any]:
    common = {
        "format": "json",
        "formatversion": "2",
        "maxlag": "5",
    }
    url = f"{WIKIPEDIA_API}?{urllib.parse.urlencode(common | params)}"
    return request_json(url, user_agent=config.user_agent, timeout=config.timeout_seconds)


def latest_revision(config: Config) -> tuple[int, str]:
    result = wikipedia_query(
        config,
        {
            "action": "query",
            "prop": "revisions",
            "titles": ARTICLE_TITLE,
            "rvprop": "ids|timestamp",
            "rvlimit": "1",
        },
    )
    try:
        revision = result["query"]["pages"][0]["revisions"][0]
        return int(revision["revid"]), str(revision["timestamp"])
    except (KeyError, IndexError, TypeError, ValueError) as exc:
        raise RequestError("Wikipedia returned no usable revision") from exc


def rendered_lead(config: Config, revision_id: int) -> str:
    result = wikipedia_query(
        config,
        {
            "action": "parse",
            "oldid": str(revision_id),
            "prop": "text",
            "section": "0",
        },
    )
    try:
        return str(result["parse"]["text"])
    except (KeyError, TypeError) as exc:
        raise RequestError(f"Wikipedia returned no rendered lead for revision {revision_id}") from exc


def wikidata_death_date(config: Config) -> str | None:
    params = {
        "action": "wbgetentities",
        "format": "json",
        "ids": WIKIDATA_ITEM,
        "props": "claims",
        "maxlag": "5",
    }
    url = f"{WIKIDATA_API}?{urllib.parse.urlencode(params)}"
    result = request_json(url, user_agent=config.user_agent, timeout=config.timeout_seconds)
    try:
        claims = result["entities"][WIKIDATA_ITEM]["claims"].get("P570", [])
        for claim in claims:
            snak = claim["mainsnak"]
            if snak.get("snaktype") == "value":
                return str(snak["datavalue"]["value"]["time"]).lstrip("+")
    except (KeyError, TypeError):
        return None
    return None


def publish_ntfy(
    config: Config,
    *,
    title: str,
    message: str,
    click: str,
    priority: int = 5,
    tags: list[str] | None = None,
) -> None:
    payload = {
        "topic": config.ntfy_topic,
        "title": title,
        "message": message,
        "priority": priority,
        "tags": tags or ["warning"],
        "click": click,
    }
    result = request_json(
        config.ntfy_server,
        user_agent=config.user_agent,
        timeout=config.timeout_seconds,
        method="POST",
        payload=payload,
        token=config.ntfy_token,
    )
    if not result.get("id"):
        raise RequestError("ntfy accepted the request but returned no message ID")


def load_state(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return data
    except FileNotFoundError:
        pass
    except (OSError, json.JSONDecodeError) as exc:
        LOG.warning("Ignoring unreadable state file %s: %s", path, exc)
    return {}


def save_state(path: Path, state: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(state, stream, sort_keys=True)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary_path, 0o600)
        os.replace(temporary_path, path)
    finally:
        temporary_path.unlink(missing_ok=True)


def revision_url(revision_id: int) -> str:
    return f"https://en.wikipedia.org/w/index.php?title=Donald_Trump&oldid={revision_id}"


def diff_url(previous_revision: int | None, revision_id: int) -> str:
    if previous_revision:
        return f"https://en.wikipedia.org/wiki/Special:Diff/{previous_revision}/{revision_id}"
    return revision_url(revision_id)


def check_once(config: Config, state: dict[str, Any]) -> dict[str, Any]:
    revision_id, timestamp = latest_revision(config)
    previous_revision = state.get("revision_id")
    if previous_revision == revision_id:
        return state

    LOG.info("Checking Wikipedia revision %s (%s)", revision_id, timestamp)
    html = rendered_lead(config, revision_id)
    detected, reasons, _lead = detect_death_notice(html)
    alert_active = bool(state.get("alert_active", False))
    link = diff_url(previous_revision if isinstance(previous_revision, int) else None, revision_id)

    if detected and not alert_active:
        corroboration = None
        try:
            corroboration = wikidata_death_date(config)
        except RequestError as exc:
            LOG.warning("Could not check Wikidata corroboration: %s", exc)

        details = "; ".join(reasons)
        if corroboration:
            details += f". Wikidata P570 is {corroboration}"
        else:
            details += ". Wikidata did not corroborate this when checked"
        publish_ntfy(
            config,
            title="Possible Wikipedia death update",
            message=(
                f"Wikipedia revision {revision_id} appears to report that Donald Trump has died: "
                f"{details}. This may be vandalism; open the revision and verify with reliable news."
            ),
            click=link,
            priority=5,
            tags=["warning", "rotating_light"],
        )
        LOG.warning("Sent death-update notification for revision %s", revision_id)
        alert_active = True
    elif not detected and alert_active:
        publish_ntfy(
            config,
            title="Wikipedia death notice removed",
            message=(
                f"Wikipedia revision {revision_id} no longer contains the detected death notice. "
                "The earlier edit may have been reverted or corrected."
            ),
            click=link,
            priority=4,
            tags=["information_source"],
        )
        LOG.info("Sent removal notification for revision %s", revision_id)
        alert_active = False

    new_state = {
        "revision_id": revision_id,
        "revision_timestamp": timestamp,
        "alert_active": alert_active,
        "checked_at": int(time.time()),
    }
    save_state(config.state_file, new_state)
    return new_state


def parse_config() -> tuple[Config, argparse.Namespace]:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--once", action="store_true", help="check once, then exit")
    parser.add_argument(
        "--test-notification",
        action="store_true",
        help="send a test ntfy message, then exit",
    )
    parser.add_argument(
        "--state-file",
        default=os.environ.get("STATE_FILE", DEFAULT_STATE_FILE),
        help=f"persistent state path (default: {DEFAULT_STATE_FILE})",
    )
    args = parser.parse_args()

    topic = os.environ.get("NTFY_TOPIC", "").strip()
    contact = os.environ.get("WIKIMEDIA_CONTACT", "").strip()
    if not topic:
        parser.error("NTFY_TOPIC must be set")
    if not contact:
        parser.error("WIKIMEDIA_CONTACT must be set to an email, URL, or Wikimedia user page")

    server = os.environ.get("NTFY_SERVER", "https://ntfy.sh").strip().rstrip("/")
    if not server.startswith(("https://", "http://")):
        parser.error("NTFY_SERVER must start with https:// or http://")
    try:
        poll_seconds = float(os.environ.get("POLL_SECONDS", "20"))
        timeout_seconds = float(os.environ.get("HTTP_TIMEOUT_SECONDS", "20"))
    except ValueError:
        parser.error("POLL_SECONDS and HTTP_TIMEOUT_SECONDS must be numbers")
    if poll_seconds < 10:
        parser.error("POLL_SECONDS must be at least 10 seconds")
    if timeout_seconds <= 0:
        parser.error("HTTP_TIMEOUT_SECONDS must be greater than zero")

    config = Config(
        ntfy_topic=topic,
        ntfy_server=server,
        ntfy_token=os.environ.get("NTFY_TOKEN") or None,
        contact=contact,
        poll_seconds=poll_seconds,
        state_file=Path(args.state_file),
        timeout_seconds=timeout_seconds,
    )
    return config, args


def main() -> int:
    logging.basicConfig(
        level=os.environ.get("LOG_LEVEL", "INFO").upper(),
        format="%(asctime)s %(levelname)s %(message)s",
    )
    config, args = parse_config()

    if len(config.ntfy_topic) < 24 and not config.ntfy_token:
        LOG.warning("Use a random topic of at least 24 characters; public ntfy topic names act as passwords")

    if args.test_notification:
        publish_ntfy(
            config,
            title="Wikipedia monitor test",
            message="The Wikipedia death-watch server can reach ntfy successfully.",
            click="https://en.wikipedia.org/wiki/Donald_Trump",
            priority=4,
            tags=["white_check_mark"],
        )
        LOG.info("Test notification sent")
        return 0

    stopping = False

    def stop(_signum: int, _frame: Any) -> None:
        nonlocal stopping
        stopping = True

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)

    state = load_state(config.state_file)
    backoff = config.poll_seconds
    while not stopping:
        try:
            state = check_once(config, state)
            backoff = config.poll_seconds
            if args.once:
                return 0
            sleep_for = config.poll_seconds
        except RequestError as exc:
            if args.once:
                LOG.error("%s", exc)
                return 1
            sleep_for = exc.retry_after if exc.retry_after is not None else backoff
            sleep_for = max(config.poll_seconds, min(sleep_for, 600.0))
            backoff = min(max(backoff * 2, config.poll_seconds), 600.0)
            LOG.error("%s; retrying in %.0f seconds", exc, sleep_for)

        deadline = time.monotonic() + sleep_for
        while not stopping and time.monotonic() < deadline:
            time.sleep(min(1.0, deadline - time.monotonic()))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
