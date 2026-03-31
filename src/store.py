"""Persistent article store — SQLite-backed, rolling window."""

import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

_DB_PATH = Path(__file__).resolve().parent.parent / "data" / "articles.db"
_CACHE_PATH = Path(__file__).resolve().parent.parent / "data" / "tree_cache.json"
_DEFAULT_WINDOW_DAYS = 15
_MAX_WINDOW_DAYS = 90


# ── Schema ────────────────────────────────────────────────────────────────────

_SCHEMA = """
CREATE TABLE IF NOT EXISTS articles (
    id          TEXT PRIMARY KEY,
    title       TEXT NOT NULL,
    link        TEXT NOT NULL,
    content     TEXT NOT NULL DEFAULT '',
    category    TEXT NOT NULL,
    fetched_at  TEXT NOT NULL,
    embedding   BLOB
);
CREATE INDEX IF NOT EXISTS idx_articles_category ON articles(category);
CREATE INDEX IF NOT EXISTS idx_articles_fetched_at ON articles(fetched_at);
"""


def _connect() -> sqlite3.Connection:
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(_DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.executescript(_SCHEMA)
    return conn


# ── Tree cache helpers ─────────────────────────────────────────────────────────

def _load_cache() -> dict:
    if _CACHE_PATH.exists():
        with open(_CACHE_PATH, encoding="utf-8") as f:
            return json.load(f)
    return {}


def _save_cache(cache: dict) -> None:
    _CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(_CACHE_PATH, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)


def _mark_dirty(category: str) -> None:
    cache = _load_cache()
    if category not in cache:
        cache[category] = {}
    cache[category]["dirty"] = True
    _save_cache(cache)


# ── Public API ────────────────────────────────────────────────────────────────

def save_articles(articles: list[dict], category: str) -> int:
    """Insert new articles into the DB. Returns the number actually inserted."""
    if not articles:
        return 0
    now = datetime.now(timezone.utc).isoformat()
    inserted = 0
    with _connect() as conn:
        for a in articles:
            try:
                conn.execute(
                    """
                    INSERT OR IGNORE INTO articles (id, title, link, content, category, fetched_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (a["id"], a["title"], a.get("link", ""), a.get("content", ""), category, now),
                )
                if conn.execute("SELECT changes()").fetchone()[0]:
                    inserted += 1
            except Exception as exc:
                print(f"[store] Warning: could not insert article {a.get('id')}: {exc}")
        conn.commit()
    if inserted:
        _mark_dirty(category)
    return inserted


def prune(window_days: int = _DEFAULT_WINDOW_DAYS) -> int:
    """Delete articles older than window_days. Returns count of deleted rows."""
    window_days = min(max(1, window_days), _MAX_WINDOW_DAYS)
    cutoff = (datetime.now(timezone.utc) - timedelta(days=window_days)).isoformat()
    with _connect() as conn:
        conn.execute("DELETE FROM articles WHERE fetched_at < ?", (cutoff,))
        deleted = conn.execute("SELECT changes()").fetchone()[0]
        conn.commit()
    return deleted


def get_articles(category: str) -> list[dict]:
    """Return all stored articles for a category, ordered by fetched_at desc."""
    with _connect() as conn:
        rows = conn.execute(
            "SELECT id, title, link, content, fetched_at FROM articles WHERE category = ? ORDER BY fetched_at DESC",
            (category,),
        ).fetchall()
    return [dict(r) for r in rows]


def get_article_count(category: str) -> int:
    with _connect() as conn:
        return conn.execute(
            "SELECT COUNT(*) FROM articles WHERE category = ?", (category,)
        ).fetchone()[0]


def get_embedding(article_id: str) -> list[float] | None:
    """Return stored embedding for an article, or None if not yet computed."""
    import struct
    with _connect() as conn:
        row = conn.execute(
            "SELECT embedding FROM articles WHERE id = ?", (article_id,)
        ).fetchone()
    if row is None or row[0] is None:
        return None
    n = len(row[0]) // 4
    return list(struct.unpack(f"{n}f", row[0]))


def save_embedding(article_id: str, embedding: list[float]) -> None:
    """Persist a float32 embedding blob for an article."""
    import struct
    blob = struct.pack(f"{len(embedding)}f", *embedding)
    with _connect() as conn:
        conn.execute(
            "UPDATE articles SET embedding = ? WHERE id = ?", (blob, article_id)
        )
        conn.commit()


def get_all_embeddings(category: str) -> list[dict]:
    """Return articles that already have embeddings computed, for a category."""
    import struct
    with _connect() as conn:
        rows = conn.execute(
            "SELECT id, title, link, fetched_at, embedding FROM articles WHERE category = ? AND embedding IS NOT NULL",
            (category,),
        ).fetchall()
    result = []
    for r in rows:
        n = len(r["embedding"]) // 4
        vec = list(struct.unpack(f"{n}f", r["embedding"]))
        result.append({"id": r["id"], "title": r["title"], "link": r["link"], "fetched_at": r["fetched_at"], "embedding": vec})
    return result


def get_all_embeddings_all_categories() -> list[dict]:
    """Return all articles with embeddings across all categories."""
    import struct
    with _connect() as conn:
        rows = conn.execute(
            "SELECT id, title, link, category, fetched_at, embedding FROM articles WHERE embedding IS NOT NULL",
        ).fetchall()
    result = []
    for r in rows:
        n = len(r["embedding"]) // 4
        vec = list(struct.unpack(f"{n}f", r["embedding"]))
        result.append({
            "id": r["id"], "title": r["title"], "link": r["link"],
            "category": r["category"], "fetched_at": r["fetched_at"], "embedding": vec,
        })
    return result


def is_tree_dirty(category: str) -> bool:
    cache = _load_cache()
    entry = cache.get(category, {})
    return entry.get("dirty", True)


def get_tree(category: str) -> dict | None:
    cache = _load_cache()
    entry = cache.get(category, {})
    if entry.get("dirty", True) or "tree" not in entry:
        return None
    return entry["tree"]


def save_tree(category: str, tree: dict) -> None:
    cache = _load_cache()
    cache[category] = {
        "dirty": False,
        "built_at": datetime.now(timezone.utc).isoformat(),
        "tree": tree,
    }
    _save_cache(cache)
