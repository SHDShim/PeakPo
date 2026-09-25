# GitHub builds

The `Build distributions` GitHub Actions workflow creates installable Python
packages and native desktop installers. It runs manually through **Actions >
Build distributions > Run workflow** and automatically when a version tag is
pushed.

## Build outputs

Each successful run provides these workflow artifacts:

- `peakpo-<version>.tar.gz`: Python source distribution.
- `peakpo-<version>-py3-none-any.whl`: Python wheel.
- `PeakPo-<version>-windows-x86_64-setup.exe`: Windows installer.
- `PeakPo-<version>-macos-arm64.dmg`: macOS disk image for Apple Silicon.
- `PeakPo-<version>-macos-x86_64.dmg`: macOS disk image for Intel processors.
- `PeakPo-<version>-linux-x86_64.deb`: Debian/Ubuntu Linux installer.

The installers include Python and PeakPo's runtime dependencies. They do not
require a separate Python environment. They are unsigned: users may need to
approve the application in Windows Security or macOS Privacy & Security on
first launch. On macOS, open the DMG and drag PeakPo into Applications.

## Create a release

1. Update `peakpo/version.py` and commit the release changes.
2. Create and push an annotated tag matching that version exactly. For version
   `7.12.3`, use tag `v7.12.3`.
3. Monitor the `Build distributions` workflow.

The workflow rejects a tag that does not match `peakpo/version.py`. After all
platform builds pass, it creates the GitHub release, generates release notes,
and attaches every Python and standalone distribution.

The workflow does not upload to PyPI. PyPI publication remains a separate,
explicit release step.

## Local executable build

Use Python 3.11 in a clean environment:

```bash
python -m pip install . -r bundling/requirements-build.txt
python -m PyInstaller --clean --noconfirm bundling/peakpo.spec
```

The output is written under `dist/`. Verify the frozen entry point without
opening the graphical interface:

```bash
dist/PeakPo/PeakPo --version
```

On macOS, use `dist/PeakPo.app/Contents/MacOS/PeakPo --version`. On Windows,
use `dist\\PeakPo\\PeakPo.exe --version`.

The frozen-build rendering check constructs the actual Qt/Matplotlib canvas
offscreen and verifies that its dark-mode axes remain visible:

```bash
dist/PeakPo/PeakPo --verify-rendering
```
