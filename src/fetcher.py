"""RSS feed fetching and article extraction."""

import json
import os
from html.parser import HTMLParser
from typing import Any

import feedparser


class _HTMLStripper(HTMLParser):
    def __init__(self):
        super().__init__()
        self._parts: list[str] = []

    def handle_data(self, data: str) -> None:
        self._parts.append(data)

    def get_text(self) -> str:
        return " ".join(self._parts)


def strip_html(raw: str) -> str:
    s = _HTMLStripper()
    s.feed(raw)
    return s.get_text().strip()


def _best_content(entry: Any) -> str:
    """Return the richest text content available in a feed entry."""
    if hasattr(entry, "content") and entry.content:
        return strip_html(entry.content[0].value)
    if hasattr(entry, "summary") and entry.summary:
        return strip_html(entry.summary)
    if hasattr(entry, "description") and entry.description:
        return strip_html(entry.description)
    return ""


def load_seen_ids(data_dir: str) -> set[str]:
    path = os.path.join(data_dir, "seen.json")
    if not os.path.exists(path):
        return set()
    with open(path) as f:
        return set(json.load(f))


def save_seen_ids(data_dir: str, seen: set[str], max_size: int = 2000) -> None:
    os.makedirs(data_dir, exist_ok=True)
    # Keep only the most recent max_size IDs (we can't guarantee order, so just trim)
    ids = list(seen)
    if len(ids) > max_size:
        ids = ids[-max_size:]
    path = os.path.join(data_dir, "seen.json")
    with open(path, "w") as f:
        json.dump(ids, f)


def fetch_category(category: dict, seen_ids: set[str]) -> list[dict]:
    """Fetch new articles for a category from all RSS sources."""
    articles: list[dict] = []
    for source in category.get("sources", []):
        if source.get("type") != "rss":
            continue
        url = source["url"]
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries:
                article_id = (
                    entry.get("id") or entry.get("link") or entry.get("title", "")
                )
                if not article_id or article_id in seen_ids:
                    continue
                articles.append(
                    {
                        "id": article_id,
                        "title": entry.get("title", "Untitled"),
                        "link": entry.get("link", ""),
                        "content": _best_content(entry),
                        "published": entry.get("published", ""),
                        "source_url": url,
                    }
                )
        except Exception as exc:
            print(f"[fetcher] Warning: could not fetch {url}: {exc}")
    return articles
