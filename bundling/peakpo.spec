# -*- mode: python ; coding: utf-8 -*-
"""Cross-platform PyInstaller definition for PeakPo."""

from pathlib import Path

from PyInstaller.compat import is_darwin
from PyInstaller.utils.hooks import collect_all, collect_data_files


project_root = Path(SPECPATH).parent


def include_runtime_module(name):
    """Exclude development-only modules from recursive collection."""
    excluded_parts = {
        "benchmark",
        "benchmarks",
        "doc",
        "docs",
        "example",
        "examples",
        "test",
        "tests",
    }
    return not excluded_parts.intersection(name.split("."))


datas = collect_data_files("peakpo", include_py_files=False)
binaries = []
hiddenimports = []

# These scientific packages discover plugins, compiled extensions, or data at
# runtime. Recursive collection makes the frozen application independent of the
# Python environment on the destination computer.
for package in ("dioptas", "fabio", "hdf5plugin", "pyFAI", "pymatgen", "silx"):
    package_datas, package_binaries, package_hiddenimports = collect_all(
        package,
        include_py_files=False,
        filter_submodules=include_runtime_module,
        on_error="warn once",
    )
    datas += package_datas
    binaries += package_binaries
    hiddenimports += package_hiddenimports

icon = project_root / "peakpo" / "assets" / (
    "PeakPo.icns" if is_darwin else "PeakPo.ico"
)

analysis = Analysis(
    [str(project_root / "bundling" / "peakpo_launcher.py")],
    pathex=[str(project_root)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["PyQt5", "PySide2", "PySide6"],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(analysis.pure)

executable = EXE(
    pyz,
    analysis.scripts,
    [],
    exclude_binaries=True,
    name="PeakPo",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(icon),
)

application = COLLECT(
    executable,
    analysis.binaries,
    analysis.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="PeakPo",
)

if is_darwin:
    version_scope = {}
    exec(
        (project_root / "peakpo" / "version.py").read_text(encoding="utf-8"),
        version_scope,
    )
    app = BUNDLE(
        application,
        name="PeakPo.app",
        icon=str(icon),
        bundle_identifier="org.shdshim.peakpo",
        info_plist={
            "CFBundleDisplayName": "PeakPo",
            "CFBundleShortVersionString": version_scope["__version__"],
            "NSHighResolutionCapable": True,
        },
    )
