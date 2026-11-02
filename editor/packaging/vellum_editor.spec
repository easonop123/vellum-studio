# -*- mode: python ; coding: utf-8 -*-
# PyInstaller recipe for "Vellum Editor.app" (Apple Silicon). Built by .github/workflows/editor.yml.
import os
import sys

ROOT = os.path.abspath(os.path.join(SPECPATH, ".."))
sys.path.insert(0, ROOT)
from vellum_editor import __version__  # noqa: E402

ASSETS = os.path.join(ROOT, "vellum_editor", "assets")
BIN = os.path.join(ASSETS, "bin")

# Fonts and the person model are plain data; ffmpeg/ffprobe are binaries so they get signed with the app.
datas = [
    (os.path.join(ASSETS, "fonts"), "vellum_editor/assets/fonts"),
    (os.path.join(ASSETS, "models"), "vellum_editor/assets/models"),
]
binaries = [(os.path.join(BIN, name), "vellum_editor/assets/bin") for name in ("ffmpeg", "ffprobe") if os.path.exists(os.path.join(BIN, name))]

a = Analysis(
    [os.path.join(ROOT, "run_app.py")],
    pathex=[ROOT],
    binaries=binaries,
    datas=datas,
    hiddenimports=["vellum_editor.render", "vellum_editor.encode", "vellum_editor.cli", "pillow_heif", "onnxruntime"],
    excludes=["tkinter", "matplotlib", "scipy", "pandas", "IPython", "pytest",
              "PySide6.QtQml", "PySide6.QtQuick", "PySide6.QtQuickWidgets", "PySide6.QtQuickControls2",
              "PySide6.QtNetwork", "PySide6.QtSql", "PySide6.QtDesigner", "PySide6.QtHelp", "PySide6.QtUiTools"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Vellum Editor",
    console=False,
    target_arch="arm64",
    codesign_identity=None,
)
coll = COLLECT(exe, a.binaries, a.datas, name="Vellum Editor")
app = BUNDLE(
    coll,
    name="Vellum Editor.app",
    icon=os.path.join(SPECPATH, "icon.icns") if os.path.exists(os.path.join(SPECPATH, "icon.icns")) else None,
    bundle_identifier="studio.vellum.editor",
    info_plist={
        "CFBundleName": "Vellum Editor",
        "CFBundleDisplayName": "Vellum Editor",
        "CFBundleShortVersionString": __version__,
        "CFBundleVersion": __version__,
        "LSMinimumSystemVersion": "12.0",
        "NSHighResolutionCapable": True,
        "LSApplicationCategoryType": "public.app-category.video",
    },
)
