# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for Claudio — builds a single-folder app bundle."""

import sys
from pathlib import Path

SRC = Path("src")
ROOT = Path(".")

a = Analysis(
    [str(SRC / "launcher.py")],
    pathex=[str(SRC)],
    binaries=[],
    datas=[
        # Bundle the default config so first-run seeding works
        (str(ROOT / "config" / "config.yaml"), "config"),
        # Bundle the tray icon
        (str(ROOT / "assets" / "icon.png"), "assets"),
    ],
    hiddenimports=[
        # Flask internals
        "flask",
        "werkzeug",
        "werkzeug.serving",
        "werkzeug.debug",
        # Our modules
        "server",
        "main",
        "renderer",
        "summarizer",
        "fetcher",
        "store",
        "tree_builder",
        "paths",
        # Third-party
        "anthropic",
        "openai",
        "feedparser",
        "yaml",
        "markdown",
        "dotenv",
        "scipy",
        "scipy.cluster",
        "scipy.cluster.hierarchy",
        "pystray",
        "PIL",
        "PIL.Image",
        "PIL.ImageDraw",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Claudio",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,           # No terminal window
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(ROOT / "assets" / "icon.png"),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="Claudio",
)

# macOS: wrap in a .app bundle
if sys.platform == "darwin":
    app = BUNDLE(
        coll,
        name="Claudio.app",
        icon=str(ROOT / "assets" / "icon.png"),
        bundle_identifier="com.claudio.app",
        info_plist={
            "CFBundleShortVersionString": "0.1.0",
            "CFBundleName": "Claudio",
            "NSHighResolutionCapable": True,
            "LSUIElement": True,   # Hides from Dock — tray-only app
        },
    )
