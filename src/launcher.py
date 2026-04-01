"""
Claudio launcher — entry point for the bundled desktop app.

Starts the Flask server in a background thread, opens the browser,
and shows a system tray icon with Open / Quit actions.
"""

import os
import sys
import threading
import time
import webbrowser
from pathlib import Path

# When running as a PyInstaller bundle, add the _MEIPASS dir to sys.path
# so all src/ modules can be found.
if getattr(sys, "frozen", False):
    bundle_dir = Path(sys._MEIPASS)  # type: ignore[attr-defined]
    sys.path.insert(0, str(bundle_dir / "src"))
else:
    sys.path.insert(0, str(Path(__file__).resolve().parent))

from paths import ensure_dirs, ENV_FILE  # noqa: E402

# Load .env before importing server (which imports anthropic etc.)
try:
    from dotenv import load_dotenv
    load_dotenv(ENV_FILE)
except ImportError:
    pass

ensure_dirs()

PORT = int(os.environ.get("PORT", 8765))
URL = f"http://localhost:{PORT}"


# ── Flask server ──────────────────────────────────────────────────────────────

def _run_server() -> None:
    # Import here so paths are initialized first
    from server import app
    app.run(host="127.0.0.1", port=PORT, debug=False, use_reloader=False)


def _start_server() -> None:
    t = threading.Thread(target=_run_server, daemon=True)
    t.start()
    # Give the server a moment to start, then open the browser
    time.sleep(1.5)
    webbrowser.open(URL)


# ── System tray icon ──────────────────────────────────────────────────────────

def _load_icon():
    from PIL import Image
    import importlib.resources

    # Look for icon next to the executable (bundled) or in assets/ (source)
    candidates = [
        Path(sys.executable).parent / "icon.png",
        Path(__file__).resolve().parent.parent / "assets" / "icon.png",
    ]
    if getattr(sys, "frozen", False):
        candidates.insert(0, Path(sys._MEIPASS) / "assets" / "icon.png")  # type: ignore[attr-defined]

    for p in candidates:
        if p.exists():
            return Image.open(p)

    # Fallback: draw a minimal icon programmatically
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    from PIL import ImageDraw
    draw = ImageDraw.Draw(img)
    draw.ellipse([2, 2, 62, 62], fill="#1c1c1e")
    draw.text((20, 16), "C", fill="#ffffff")
    return img


def _open_browser(icon, item) -> None:  # noqa: ARG001
    webbrowser.open(URL)


def _quit_app(icon, item) -> None:  # noqa: ARG001
    icon.stop()
    os._exit(0)


def _run_tray() -> None:
    try:
        import pystray
        icon_image = _load_icon()
        menu = pystray.Menu(
            pystray.MenuItem("Open Claudio", _open_browser, default=True),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Quit", _quit_app),
        )
        icon = pystray.Icon("claudio", icon_image, "Claudio", menu)
        icon.run()
    except Exception as exc:
        # pystray unavailable (e.g. headless CI) — just keep the process alive
        print(f"[claudio] Tray icon unavailable: {exc}. Running in background.")
        threading.Event().wait()


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    print(f"[claudio] Starting server at {URL}")
    _start_server()
    _run_tray()


if __name__ == "__main__":
    main()
