---
name: pypi-release-publisher
description: Build and publish this Python package to PyPI safely. Use when user asks to prepare or upload a new package release. Mandatory: ask whether release should be alpha (pre-release) or stable before changing version or uploading.
---

# PyPI Release Publisher

Use this skill when publishing this repository to PyPI.

## Mandatory gate

Before changing any version string or uploading, ask the user:
- Should this release be `alpha` (pre-release) or `stable`?

Do not assume. Wait for the user answer.

## Versioning rules

- Stable examples: `7.10.8`, `7.11.0`
- Alpha examples: `7.10.9a1`, `7.10.9a2`
- Keep PEP 440 compliant.
- Update `peakpo/version.py` (`__version__`) and add one concise changelog line in that file.

## Build and upload workflow

1. Clean previous artifacts to avoid accidental upload of old files:
```bash
rm -f dist/*
```
2. Build:
```bash
python -m build
```
3. Upload only the current version artifacts (never `dist/*` unless user explicitly requests):
```bash
python -m twine upload dist/peakpo-<VERSION>*
```

## Safety checks

- If network-restricted command fails (build isolation or upload), retry with required elevated network permissions.
- Report exact files built under `dist/`.
- Report exact PyPI URL(s) after upload.
- If upload for this exact version already exists, report the error clearly and stop.

## Communication style

- Keep responses concise.
- State commands being run.
- Summarize outcomes, including failures and next action.
