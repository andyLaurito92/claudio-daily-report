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
    # Convert "Title (url)" h3 pattern to proper links for old reports.
    # Handles both "https://example.com/path" and bare "example.com/path" forms.
    def _linkify(m):
        url = m.group(2)
        if not url.startswith(("http://", "https://")):
            url = "https://" + url
        return (
            f'<h3><a href="{url}" target="_blank" rel="noopener noreferrer">'
            f'{m.group(1).strip()}</a></h3>'
        )
    sections_html = _re.sub(
        r'<h3>([^<]+?)\s*\(((?:https?://)?[A-Za-z0-9][-A-Za-z0-9.]+\.[A-Za-z]{2,}[^)]*)\)</h3>',
        _linkify,
        sections_html,
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


@app.route("/api/categories/<name>", methods=["PUT"])
def api_update_category(name):
    data = request.get_json(force=True)
    cfg = _load_config()
    for cat in cfg.get("categories", []):
        if cat["name"] == name:
            cat["name"] = (data.get("name") or cat["name"]).strip()
            cat["weight"] = int(data.get("weight", cat.get("weight", 1)))
            cat["description"] = data.get("description", cat.get("description", ""))
            _save_config(cfg)
            return jsonify({"ok": True})
    return jsonify({"error": "not found"}), 404


@app.route("/api/categories/<name>", methods=["DELETE"])
def api_delete_category(name):
    cfg = _load_config()
    cfg["categories"] = [c for c in cfg.get("categories", []) if c["name"] != name]
    _save_config(cfg)
    return jsonify({"ok": True})


@app.route("/api/categories/<name>/sources", methods=["POST"])
def api_add_source(name):
    data = request.get_json(force=True)
    url = (data.get("url") or "").strip()
    if not url:
        return jsonify({"error": "url required"}), 400
    cfg = _load_config()
    for cat in cfg.get("categories", []):
        if cat["name"] == name:
            cat.setdefault("sources", []).append({
                "url": url,
                "type": data.get("type", "rss"),
            })
            _save_config(cfg)
            return jsonify({"ok": True})
    return jsonify({"error": "not found"}), 404


@app.route("/api/categories/<name>/sources/<int:idx>", methods=["DELETE"])
def api_delete_source(name, idx):
    cfg = _load_config()
    for cat in cfg.get("categories", []):
        if cat["name"] == name:
            sources = cat.get("sources", [])
            if 0 <= idx < len(sources):
                sources.pop(idx)
            _save_config(cfg)
            return jsonify({"ok": True})
    return jsonify({"error": "not found"}), 404


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    port = int(os.environ.get("PORT", 8765))
    print(f"[claudio] Serving at http://localhost:{port}")
    print("[claudio] Press Ctrl+C to stop")
    app.run(host="127.0.0.1", port=port, debug=False, use_reloader=False)


if __name__ == "__main__":
    main()
