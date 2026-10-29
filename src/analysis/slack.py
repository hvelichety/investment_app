"""
Read the methodology author's recent posts from a Slack channel.

Uses the Slack Web API with a bot token (SLACK_BOT_TOKEN; scopes
channels:history, groups:history, files:read; the bot must be a member of
the channel). Thread replies are included because charts are often posted
in threads. Read-only: nothing here posts to Slack.
"""

import json
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List, Tuple

API = "https://slack.com/api/"
MAX_IMAGES = 6
MAX_IMAGE_BYTES = 3_500_000
IMAGE_TYPES = {"image/png", "image/jpeg", "image/gif", "image/webp"}


@dataclass
class Post:
    ts: str
    text: str
    images: List[Tuple[str, bytes]] = field(default_factory=list)   # (media type, data)

    @property
    def date(self) -> str:
        return datetime.fromtimestamp(float(self.ts), tz=timezone.utc).strftime("%Y-%m-%d")


def _call(method: str, token: str, **params) -> dict:
    url = API + method + "?" + urllib.parse.urlencode(params)
    request = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(request, timeout=30) as resp:
        data = json.loads(resp.read())
    if not data.get("ok"):
        raise RuntimeError(f"Slack {method} failed: {data.get('error')}")
    return data


def _download(url: str, token: str) -> bytes:
    request = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(request, timeout=60) as resp:
        return resp.read(MAX_IMAGE_BYTES + 1)


def _messages(channel: str, token: str, oldest: str) -> List[dict]:
    messages, cursor = [], None
    while True:
        params = {"channel": channel, "oldest": oldest, "limit": 200}
        if cursor:
            params["cursor"] = cursor
        data = _call("conversations.history", token, **params)
        messages += data.get("messages", [])
        cursor = (data.get("response_metadata") or {}).get("next_cursor")
        if not cursor:
            break
    for parent in [m for m in messages if m.get("reply_count")]:
        replies = _call("conversations.replies", token, channel=channel, ts=parent["ts"]).get("messages", [])
        messages += [r for r in replies if r["ts"] != parent["ts"]]
    return sorted(messages, key=lambda m: float(m["ts"]))


def author_posts(channel: str, author: str, token: str, days: int = 8) -> List[Post]:
    """The author's posts (and thread replies) from the last `days` days, oldest first"""
    oldest = str(time.time() - days * 86400)
    posts, image_budget = [], MAX_IMAGES
    for m in _messages(channel, token, oldest):
        if m.get("user") != author or m.get("subtype") not in (None, "file_share", "thread_broadcast"):
            continue
        post = Post(m["ts"], m.get("text", ""))
        for f in m.get("files", []):
            if image_budget and f.get("mimetype") in IMAGE_TYPES and f.get("size", 0) <= MAX_IMAGE_BYTES:
                data = _download(f["url_private"], token)
                if len(data) <= MAX_IMAGE_BYTES:
                    post.images.append((f["mimetype"], data))
                    image_budget -= 1
        if post.text.strip() or post.images:
            posts.append(post)
    return posts
