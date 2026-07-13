# AGENTS.md

## Overview

This repository contains `PeakPo`, a Python desktop application for X-ray diffraction analysis.

Main application functions include:

- JCPDS overlaying and reference-bar display
- Waterfall plotting and pattern stacking
- Azimuthal integration for Cake images
- Peak fitting and peak-parameter management
- Unit-cell fitting
- Map generation from selected ROIs
- Difference mode / background subtraction workflows
- Sequence analysis from ROI-selected CHI files
- Plot inspection and navigation tools for 1D and Cake data

Release-related work should use the `pypi-release` skill so packaging, build,
validation, tagging, and publication stay consistent.

## Project Structure

- `peakpo/`: main application package
- `ui/`: Qt Designer UI source
- `shortcuts/`: launcher helpers for local/manual use
- `jupyter-tools/`: notebooks and utility material not shipped with the package
- `docs/`: user and agent documentation for this repository; treat it as the
  canonical location for Markdown guidance, usage notes, and development
  references
- `scripts/`: obsolete helper files; do not rely on them

## Documentation Policy

- Check `docs/` before adding new documentation or renaming existing files.
- Keep filenames in `docs/` consistent with a lowercase kebab-case pattern
  unless there is a strong reason to preserve an established exception.
- Use clear, purpose-driven names that describe the content in plain language.
- Do not change document content when only filename normalization is requested.
- Prefer updating or extending existing documents in `docs/` when the topic
  already exists, so related guidance stays consolidated and easy to find.
- Treat `docs/` as the reference point for documentation consistency during
  future updates, including work in other repositories that follow the same
  pattern.

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

## Consistency Memory

Treat this repository as a long-lived scientific application with a stable
user-facing workflow. Future updates should preserve terminology, interaction
patterns, and file conventions unless there is a strong reason to change them.

- Before changing code, inspect the relevant controller, model, view, and
  documentation files together.
- Use the existing shared helpers and style policy modules before adding new
  one-off logic or new UI styling.
- Keep UI labels, tooltips, object names, connected actions, and documentation
  wording aligned when a user-facing control changes.
- Update `docs/` when behavior changes, especially for user workflows, mouse
  actions, or menu placement.
- Use `docs/` as the canonical place for future user and agent documentation,
  and keep filenames in the established lowercase kebab-case format.
- Treat the shared plot interaction controller as the source of truth for
  mouse behavior on the 1D plot and Cake plot.
- Remember that ROI workflows are spread across Map, Sequence, and Cake tabs;
  keep those paths consistent when changing ROI behavior.
- Preserve peak-fitting semantics in the `Fits` tab, including peak add/remove,
  peak dragging, and constraint editing.
- Preserve backward compatibility for legacy session and diffraction file
  formats when changing serialization or loading code.
- Prefer runtime policy helpers over edits to generated UI code when a change
  affects application-wide behavior.
- If a change introduces a new common pattern, add the shared rule or helper
  first, then apply it in the feature code.
- Treat graph update performance as a core constraint. Do not introduce
  changes that make graphify updates slower unless the user explicitly asks
  for a heavier rebuild or richer extraction path.
- Prefer incremental graph updates and lightweight source changes whenever
  possible, since graph freshness is important for future code review and
  documentation consistency.

## Verification

Use the `dev26a` Conda environment for local Python commands in this repository. Prefer the environment's Python executable directly when possible:

```bash
/opt/homebrew/Caskroom/miniforge/base/envs/dev26a/bin/python -m compileall peakpo
/opt/homebrew/Caskroom/miniforge/base/envs/dev26a/bin/python -m pip install -e .
/opt/homebrew/Caskroom/miniforge/base/envs/dev26a/bin/python -m peakpo
```

Avoid assuming the shell's currently active Conda environment is correct. In particular, the `main` environment may be active in automated shells but is not the intended development environment for this project.

Use judgment with GUI launch commands in headless or sandboxed environments.

## Release Workflow

- Use the `pypi-release` skill for PyPI packaging, release preparation, build,
  validation, tagging, and publication tasks.
- Follow the skill-driven workflow instead of ad hoc release steps so release
  handling stays consistent across future updates.
- Update package metadata in `pyproject.toml`, `setup.py`, changelog-style
  notes, and release checks in the order recommended by the skill.

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

- Use a single shared helper in `peakpo/view/ui_policy.py` for non-toolbar checkable buttons such as `Set ROI`, `Set position range from plot`, `Set FWHM max from plot`, and `Add range from plot`.
- That helper should define the state template in one place: unchecked buttons use the normal Fusion button appearance with only a yellow label color, while pressed or checked buttons use the yellow active-button appearance.
- Do not duplicate the same toggle-button QSS in controllers; reference the shared helper instead.

### Unchecked

- Preserve the normal Fusion button background, border, bevel, hover, and focus treatment.
- Change only the label color to yellow so users can recognize the control as checkable.

### Checked

- Fill the button with the shared yellow/orange active-button style.
- Use a darker orange border or edge treatment if it improves the raised-button effect.
- Use high-contrast text, normally dark gray, on the yellow fill.
- Optionally display a checkmark icon if appropriate.

### Rationale

- The yellow label indicates that the normal-looking button is checkable without making the unchecked state visually conflict with adjacent ordinary buttons.
- Filling the button with yellow/orange provides an immediate and intuitive indication that the option is enabled or actively being pressed.
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
- Non-toolbar checkable buttons that start and stop plot interactions should
  use the shared raised-toggle helper in `ui_policy.py` rather than per-button
  inline styles. Their unchecked state should retain the normal Fusion button
  look except for yellow label text; their pressed and checked states should
  use the shared yellow active-button look. Keep typography regular-weight.
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
