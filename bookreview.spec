# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for the AI Book Review desktop GUI."""

from pathlib import Path

project_root = Path(SPECPATH).resolve()

a = Analysis(
    [str(project_root / "bookreview" / "gui.py")],
    pathex=[str(project_root)],
    binaries=[],
    datas=[],
    hiddenimports=[
        "bookreview.core.parsers.docx_parser",
        "bookreview.core.parsers.epub_parser",
        "bookreview.core.parsers.mobi_parser",
        "bookreview.core.parsers.cleaner",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter"],
    noarchive=False,
    optimize=1,
)

pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="AI-Book-Review",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
)

