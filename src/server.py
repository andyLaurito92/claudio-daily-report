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

from main import main as run_pipeline  # noqa: E402
from renderer import render_empty_state  # noqa: E402

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

@app.route("/")
def index():
    reports = sorted(glob.glob("output/*.html"))
    if not reports:
        return render_empty_state()
    with open(reports[-1], encoding="utf-8") as f:
        return f.read()


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


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    port = int(os.environ.get("PORT", 8765))
    print(f"[claudio] Serving at http://localhost:{port}")
    print("[claudio] Press Ctrl+C to stop")
    app.run(host="127.0.0.1", port=port, debug=False, use_reloader=False)


if __name__ == "__main__":
    main()
