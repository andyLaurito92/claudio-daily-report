"""Local web server — serves the latest report and triggers feed updates."""

import glob
import json
import os
import sys
import threading
import urllib.request
from pathlib import Path

# Load .env before anything else
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
except ImportError:
    pass

import yaml
from flask import Flask, jsonify, request  # noqa: E402

sys.path.insert(0, os.path.dirname(__file__))

import re as _re  # noqa: E402

from main import main as run_pipeline  # noqa: E402
from renderer import render_empty_state, _render  # noqa: E402
import store  # noqa: E402
import tree_builder  # noqa: E402

app = Flask(__name__)

_lock = threading.Lock()
_update_running = False
_update_error: str | None = None

_CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "config.yaml"
_ANTHROPIC_MODELS = ["claude-opus-4-6", "claude-sonnet-4-6", "claude-haiku-4-5"]


# ── Helpers ───────────────────────────────────────────────────────────────────

def _load_config() -> dict:
    with open(_CONFIG_PATH) as f:
        return yaml.safe_load(f)


def _save_config(cfg: dict) -> None:
    with open(_CONFIG_PATH, "w") as f:
        yaml.dump(cfg, f, default_flow_style=False, allow_unicode=True, sort_keys=False)


def _get_ollama_models(base_url: str) -> list[str]:
    try:
        url = base_url.rstrip("/") + "/api/tags"
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=2) as resp:
            data = json.loads(resp.read())
            return [m["name"] for m in data.get("models", [])]
    except Exception:
        return []


def _do_update() -> None:
    global _update_running, _update_error
    try:
        run_pipeline()
        _update_error = None
    except Exception as exc:
        _update_error = str(exc)
        print(f"[claudio] update error: {exc}")
    finally:
        _update_running = False


# ── Routes ────────────────────────────────────────────────────────────────────

def _rerender_html(html_content: str) -> str:
    """Re-render an old HTML report with the current UI template."""
    date_m = _re.search(r'Daily Report &middot; ([^&]+) &middot;', html_content)
    date_str = date_m.group(1).strip() if date_m else "Unknown date"
    time_m = _re.search(r'~(\d+)m read', html_content)
    time_str = time_m.group(1) if time_m else "10"
    badges_m = _re.search(r'<div class="badges">(.*?)</div>', html_content, _re.DOTALL)
    badges_html = badges_m.group(1).strip() if badges_m else ""
    sections_m = _re.search(
        r'<div class="categories-grid">(.*?)</div>\s*</div>\s*(?:<div id="manage|<script)',
        html_content, _re.DOTALL
    )
    sections_html = sections_m.group(1).strip() if sections_m else ""

    # Convert legacy "Title (bare-url)" h3 pattern to a proper <a> link
    def _linkify(m):
        url = m.group(2)
        if not url.startswith(("http://", "https://")):
            url = "https://" + url
        return f'<h3><a href="{url}">{m.group(1).strip()}</a></h3>'

    sections_html = _re.sub(
        r'<h3>([^<]+?)\s*\(((?:https?://)?[A-Za-z0-9][-A-Za-z0-9.]+\.[A-Za-z]{2,}[^)]*)\)</h3>',
        _linkify,
        sections_html,
    )

    # Extract URL from h3 <a> tags → move to data-href on card, add ↗ button
    def _clean_title(t: str) -> str:
        t = _re.sub(r'\s*\(URL:\s*https?://[^)]+\)', '', t)
        t = _re.sub(r'\s*\((?:https?://)?[A-Za-z0-9][-A-Za-z0-9.]+\.[A-Za-z]{2,}[^)]*\)', '', t)
        return t.strip()

    def _process_card(m):
        inner = m.group(1)
        lm = _re.search(r'<h3><a href="(https?://[^"]+)"[^>]*>(.*?)</a></h3>', inner, _re.DOTALL)
        if lm:
            url, title = lm.group(1), _clean_title(lm.group(2))
            inner = inner[:lm.start()] + f"<h3>{title}</h3>" + inner[lm.end():]
            btn = '<button class="article-link-btn" title="View source URL">&#8599;</button>'
            return f'<div class="article" data-href="{url}">{inner}{btn}</div>'
        return f'<div class="article">{inner}</div>'

    sections_html = _re.sub(
        r'<div class="article">(.*?)</div>', _process_card, sections_html, flags=_re.DOTALL
    )
    return _render(date_str, time_str, badges_html, sections_html)


@app.route("/")
def index():
    # Prefer JSON summaries (saved by recent pipeline runs) for clean re-render
    json_reports = sorted(glob.glob("output/*.json"))
    if json_reports:
        with open(json_reports[-1], encoding="utf-8") as f:
            data = json.load(f)
        from datetime import date as _date
        from renderer import render_report
        from summarizer import _inject_links
        # Inject article links into summaries that lack them (e.g. non-compliant LLMs)
        for s in data["summaries"]:
            article_links = s.get("article_links", [])
            if article_links:
                s["summary_md"] = _inject_links(s["summary_md"], article_links)
        return render_report(
            _date.fromisoformat(data["date"]),
            data["summaries"],
            data["reading_time_minutes"],
        )
    # Fall back to re-rendering old HTML reports with the current UI template
    html_reports = sorted(glob.glob("output/*.html"))
    if not html_reports:
        return render_empty_state()
    with open(html_reports[-1], encoding="utf-8") as f:
        html = f.read()
    return _rerender_html(html)


@app.route("/update", methods=["POST"])
def update():
    global _update_running
    with _lock:
        if not _update_running:
            _update_running = True
            threading.Thread(target=_do_update, daemon=True).start()
            return jsonify({"status": "started"})
        return jsonify({"status": "already_running"})


@app.route("/status")
def status():
    return jsonify({"running": _update_running, "error": _update_error})


@app.route("/api/config", methods=["GET"])
def api_get_config():
    cfg = _load_config()
    return jsonify(cfg.get("llm", {"provider": "anthropic", "model": "claude-opus-4-6"}))


@app.route("/api/config", methods=["POST"])
def api_set_config():
    data = request.get_json(force=True)
    cfg = _load_config()
    if "llm" not in cfg:
        cfg["llm"] = {}
    cfg["llm"]["provider"] = data.get("provider", "anthropic")
    cfg["llm"]["model"] = data.get("model", "claude-opus-4-6")
    _save_config(cfg)
    return jsonify({"ok": True})


@app.route("/api/models", methods=["GET"])
def api_models():
    cfg = _load_config()
    ollama_url = cfg.get("llm", {}).get("ollama_base_url", "http://localhost:11434")
    return jsonify({
        "anthropic": _ANTHROPIC_MODELS,
        "ollama": _get_ollama_models(ollama_url),
    })


# ── Category management API ───────────────────────────────────────────────────

@app.route("/api/categories", methods=["GET"])
def api_get_categories():
    cfg = _load_config()
    return jsonify(cfg.get("categories", []))


@app.route("/api/categories", methods=["POST"])
def api_add_category():
    data = request.get_json(force=True)
    name = (data.get("name") or "").strip()
    if not name:
        return jsonify({"error": "name required"}), 400
    cfg = _load_config()
    cats = cfg.setdefault("categories", [])
    if any(c["name"] == name for c in cats):
        return jsonify({"error": "category already exists"}), 409
    cats.append({
        "name": name,
        "weight": int(data.get("weight", 1)),
        "description": data.get("description", ""),
        "sources": [],
    })
    _save_config(cfg)
    return jsonify({"ok": True})


@app.route("/api/categories/<int:idx>", methods=["PUT"])
def api_update_category(idx):
    data = request.get_json(force=True)
    cfg = _load_config()
    cats = cfg.get("categories", [])
    if idx < 0 or idx >= len(cats):
        return jsonify({"error": "not found"}), 404
    cats[idx]["name"] = (data.get("name") or cats[idx]["name"]).strip()
    cats[idx]["weight"] = int(data.get("weight", cats[idx].get("weight", 1)))
    cats[idx]["description"] = data.get("description", cats[idx].get("description", ""))
    _save_config(cfg)
    return jsonify({"ok": True})


@app.route("/api/categories/<int:idx>", methods=["DELETE"])
def api_delete_category(idx):
    cfg = _load_config()
    cats = cfg.get("categories", [])
    if idx < 0 or idx >= len(cats):
        return jsonify({"error": "not found"}), 404
    cats.pop(idx)
    _save_config(cfg)
    return jsonify({"ok": True})


@app.route("/api/categories/<int:idx>/sources", methods=["POST"])
def api_add_source(idx):
    data = request.get_json(force=True)
    url = (data.get("url") or "").strip()
    if not url:
        return jsonify({"error": "url required"}), 400
    cfg = _load_config()
    cats = cfg.get("categories", [])
    if idx < 0 or idx >= len(cats):
        return jsonify({"error": "not found"}), 404
    cats[idx].setdefault("sources", []).append({
        "url": url,
        "type": data.get("type", "rss"),
    })
    _save_config(cfg)
    return jsonify({"ok": True})


@app.route("/api/categories/<int:idx>/sources/<int:sidx>", methods=["DELETE"])
def api_delete_source(idx, sidx):
    cfg = _load_config()
    cats = cfg.get("categories", [])
    if idx < 0 or idx >= len(cats):
        return jsonify({"error": "not found"}), 404
    sources = cats[idx].get("sources", [])
    if 0 <= sidx < len(sources):
        sources.pop(sidx)
    _save_config(cfg)
    return jsonify({"ok": True})


# ── Archive / Search API ──────────────────────────────────────────────────────

@app.route("/api/archive/categories", methods=["GET"])
def api_archive_categories():
    """List categories that have archived articles, with counts."""
    cfg = _load_config()
    cats = cfg.get("categories", [])
    result = []
    for cat in cats:
        name = cat["name"]
        count = store.get_article_count(name)
        result.append({"name": name, "count": count, "dirty": store.is_tree_dirty(name)})
    return jsonify(result)


@app.route("/api/archive/tree/<path:category>", methods=["GET"])
def api_archive_tree(category):
    """Return the cluster tree for a category, building it lazily if dirty."""
    if store.is_tree_dirty(category):
        try:
            tree = tree_builder.build_tree(category)
        except Exception as exc:
            return jsonify({"error": str(exc)}), 500
    else:
        tree = store.get_tree(category)
        if tree is None:
            try:
                tree = tree_builder.build_tree(category)
            except Exception as exc:
                return jsonify({"error": str(exc)}), 500
    return jsonify(tree)


@app.route("/api/archive/search", methods=["GET"])
def api_archive_search():
    """Full-text + semantic search over archived articles."""
    q = (request.args.get("q") or "").strip()
    if not q:
        return jsonify([])

    cfg = _load_config()
    provider = cfg.get("llm", {}).get("provider", "anthropic")
    base_url = cfg.get("llm", {}).get("ollama_base_url", "http://localhost:11434")

    # Try semantic search first (requires embeddings)
    try:
        if provider == "ollama":
            query_vec = tree_builder._embed_ollama([q], base_url)[0]
        else:
            query_vec = tree_builder._embed_anthropic([q])[0]

        all_articles = store.get_all_embeddings_all_categories()
        if all_articles:
            import math
            def cosine(a, b):
                dot = sum(x * y for x, y in zip(a, b))
                na = math.sqrt(sum(x * x for x in a)) or 1
                nb = math.sqrt(sum(x * x for x in b)) or 1
                return dot / (na * nb)

            scored = [
                {**a, "score": cosine(query_vec, a["embedding"])}
                for a in all_articles
            ]
            scored.sort(key=lambda x: x["score"], reverse=True)
            top = scored[:10]
            return jsonify([
                {"id": r["id"], "title": r["title"], "link": r["link"],
                 "category": r["category"], "fetched_at": r["fetched_at"], "score": round(r["score"], 4)}
                for r in top
            ])
    except Exception as exc:
        print(f"[search] Semantic search failed, falling back to text search: {exc}")

    # Fallback: simple title/content substring search
    results = []
    with store._connect() as conn:
        rows = conn.execute(
            """SELECT id, title, link, category, fetched_at FROM articles
               WHERE title LIKE ? OR content LIKE ?
               ORDER BY fetched_at DESC LIMIT 20""",
            (f"%{q}%", f"%{q}%"),
        ).fetchall()
    for r in rows:
        results.append({"id": r["id"], "title": r["title"], "link": r["link"],
                        "category": r["category"], "fetched_at": r["fetched_at"], "score": None})
    return jsonify(results)


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    port = int(os.environ.get("PORT", 8765))
    print(f"[claudio] Serving at http://localhost:{port}")
    print("[claudio] Press Ctrl+C to stop")
    app.run(host="127.0.0.1", port=port, debug=False, use_reloader=False)


if __name__ == "__main__":
    main()
