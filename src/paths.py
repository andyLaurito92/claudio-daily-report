"""Centralized user-data paths — works both from source and as a PyInstaller bundle."""

import os
import shutil
import sys
from pathlib import Path


def _user_data_dir() -> Path:
    """Return the platform-correct writable data directory for claudio."""
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    return base / "claudio"


def _bundled_default_config() -> Path | None:
    """Return path to the default config bundled inside a PyInstaller executable, or None."""
    if getattr(sys, "frozen", False):
        # Running as a PyInstaller bundle — _MEIPASS is the temp extraction dir
        return Path(sys._MEIPASS) / "config" / "config.yaml"  # type: ignore[attr-defined]
    # Running from source — use the repo's config/
    repo_root = Path(__file__).resolve().parent.parent
    candidate = repo_root / "config" / "config.yaml"
    return candidate if candidate.exists() else None


# ── Public paths ──────────────────────────────────────────────────────────────

USER_DIR = _user_data_dir()
CONFIG_DIR = USER_DIR / "config"
DATA_DIR = USER_DIR / "data"
OUTPUT_DIR = USER_DIR / "output"
CONFIG_FILE = CONFIG_DIR / "config.yaml"
ENV_FILE = USER_DIR / ".env"


def ensure_dirs() -> None:
    """Create user data directories and seed default config on first run."""
    for d in (CONFIG_DIR, DATA_DIR, OUTPUT_DIR):
        d.mkdir(parents=True, exist_ok=True)

    if not CONFIG_FILE.exists():
        default = _bundled_default_config()
        if default and default.exists():
            shutil.copy(default, CONFIG_FILE)
        else:
            # Write a minimal default so the app can start
            CONFIG_FILE.write_text(
                "reading_time_minutes: 10\n"
                "categories: []\n"
                "output:\n  dir: output\n"
                "data_dir: data\n"
                "archive:\n  window_days: 15\n"
                "llm:\n  provider: anthropic\n  model: claude-sonnet-4-6\n",
                encoding="utf-8",
            )
