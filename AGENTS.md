# AGENTS.md

## Overview

This repository contains `PeakPo`, a Python desktop application for X-ray diffraction analysis.

## Project Structure

- `peakpo/`: main application package
- `ui/`: Qt Designer UI source
- `shortcuts/`: launcher helpers for local/manual use
- `jupyter-tools/`: notebooks and utility material not shipped with the package
- `scripts/`: obsolete helper files; do not rely on them

## Packaging and Distribution

- PyPI packaging is defined by `pyproject.toml` and `setup.py`.
- The package name is `PeakPo`.
- The console entry point is `peakpo=peakpo.__main__:main`.
- Python requirement is `>=3.11`.
- Runtime dependencies are declared in `setup.py`.
- PyPI is the supported distribution channel.
- Do not add `scripts/`, `jupyter-tools/`, `shortcuts/`, `ui/`, or `environments/` to package artifacts unless explicitly requested.
- `scripts/` is obsolete and should not be included in git or pip distributions.

## Editing Guidance

- Prefer small, targeted changes.
- Preserve the existing package structure and entry point.
- If dependency changes are needed for installation from PyPI, update `setup.py`.
- If shipped files change, verify `MANIFEST.in` and `package_data` in `setup.py`.
- Preserve backward compatibility for legacy `.dpp` and `.ppss` files: PeakPo must
  at least be able to read them, even when it no longer writes those formats in
  normal workflows. Keep compatibility shims, legacy class locations, and
  representative read tests when changing serialization or session code.

## Verification

Use the `dev26a` Conda environment for local Python commands in this repository. Prefer the environment's Python executable directly when possible:

```bash
/opt/homebrew/Caskroom/miniforge/base/envs/dev26a/bin/python -m compileall peakpo
/opt/homebrew/Caskroom/miniforge/base/envs/dev26a/bin/python -m pip install -e .
/opt/homebrew/Caskroom/miniforge/base/envs/dev26a/bin/python -m peakpo
```

Avoid assuming the shell's currently active Conda environment is correct. In particular, the `main` environment may be active in automated shells but is not the intended development environment for this project.

Use judgment with GUI launch commands in headless or sandboxed environments.

## Graphify

This project has a knowledge graph at `graphify-out/` with god nodes, community structure, and cross-file relationships.

When the user types `/graphify`, use the installed graphify skill or instructions before doing anything else.

Rules:

- For codebase questions, first run `graphify query "<question>"` when `graphify-out/graph.json` exists.
- Use `graphify path "<A>" "<B>"` for relationships and `graphify explain "<concept>"` for focused concepts.
- These return a scoped subgraph, usually much smaller than `GRAPH_REPORT.md` or raw grep output.
- Dirty `graphify-out/` files are expected after hooks or incremental updates; dirty graph files are not a reason to skip graphify. Only skip graphify if the task is about stale or incorrect graph output, or the user explicitly says not to use it.
- If `graphify-out/wiki/index.md` exists, use it for broad navigation instead of raw source browsing.
- Read `graphify-out/GRAPH_REPORT.md` only for broad architecture review or when query/path/explain do not surface enough context.
- After modifying code, run `graphify update .` to keep the graph current (AST-only, no API cost).

## Checkable Push Buttons

Checkable (`setCheckable(true)`) push buttons should follow a consistent visual style that clearly distinguishes their unchecked and checked states without conflicting with the application's existing color semantics.

### Unchecked

- Use the standard dark gray button background.
- Draw a thin 1 px orange outline or border.
- Use the normal button text color.

### Checked

- Fill the button with the same orange used for the unchecked border.
- Use a slightly darker orange border, or no distinct border if the fill provides sufficient contrast.
- Use a high-contrast text color, white or dark gray depending on the fill color.
- Optionally display a checkmark icon if appropriate.

### Rationale

- The orange outline indicates that the button is checkable even in its normal state.
- Filling the button with the same orange provides an immediate and intuitive indication that the option is enabled.
- Using a single accent color for both states creates a strong visual association while avoiding conflicts with the application's existing color semantics:
  - Green: positive/save actions
  - Yellow: important actions
  - Red: fitting/destructive actions
- Avoid introducing additional accent colors for checkable buttons to maintain a consistent and uncluttered interface.

## Standard Button Dimensions and Shared Styles

Use the shared definitions in `peakpo/view/ui_policy.py` for ordinary
push-button dimensions and reusable button styles. Do not duplicate common QSS
rules in individual views.

- Standard action buttons use a fixed height of 28 px.
- Compact controls embedded in dense tables, histograms, or icon rows may use
  25 px height when the reduced height is necessary for that local layout.
- Textual compact top-toolbar controls use a fixed width of 84 px. Keep
  related controls aligned; do not combine a fixed minimum width with an
  unlimited maximum width.
- Use the shared flat-toolbar, colored-toolbar, and accent-button helpers for
  ordinary actions. Keep specialized stateful-mode styling in the owning
  controller only when it conveys active application state.
- Top-toolbar `QPushButton` controls use a flat, non-beveled appearance.
  Preserve this treatment for new toolbar controls; panel buttons retain the
  application's default native shape unless they have an explicit local style.
- Colored panel actions retain their semantic fill but use the shared accent
  style's raised, native-button-like edge treatment rather than a flat tile.
- Add new common colors, spacing, or dimensions to `ui_policy.py` rather than
  introducing one-off literal values in `mainwidget.py` or generated UI code.

### Maintenance Rules

- Treat `ui/peakpo.ui` as the Qt Designer source and `peakpo/view/qtd.py` as
  generated code. Prefer runtime policy helpers for application-wide visual
  adjustments, and avoid manual edits to generated code.
- When changing a button's label, verify that its tooltip, object name, and
  connected action describe the same operation.
