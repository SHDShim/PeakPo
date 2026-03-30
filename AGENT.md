# AGENT.md

This repository contains `PeakPo`, a Python desktop application for X-ray diffraction analysis.

## Project layout

- `peakpo/`: main application package
- `ui/`: Qt Designer UI source
- `shortcuts/`: launcher helpers for local/manual use
- `jupyter-tools/`: notebooks and utility material not shipped with the package
- `scripts/`: obsolete helper files; do not rely on them

## Packaging

- PyPI packaging is defined by `pyproject.toml` and `setup.py`.
- The package name is `PeakPo`.
- The console entry point is `peakpo=peakpo.__main__:main`.
- Python requirement is `>=3.11`.
- Runtime dependencies are declared in `setup.py`.

## Distribution policy

- PyPI is the supported distribution channel.
- Do not add `scripts/`, `jupyter-tools/`, `shortcuts/`, `ui/`, or `environments/` to package artifacts unless explicitly requested.
- `scripts/` is obsolete and should not be included in git or pip distributions.

## Editing guidance

- Prefer small, targeted changes.
- Preserve the existing package structure and entry point.
- If dependency changes are needed for installation from PyPI, update `setup.py`.
- If shipped files change, verify `MANIFEST.in` and `package_data` in `setup.py`.

## Verification

Useful local checks:

```bash
python -m compileall peakpo
python -m pip install -e .
python -m peakpo
```

Use judgment with GUI launch commands in headless or sandboxed environments.
