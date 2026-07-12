# PeakPo Mouse Actions

This note summarizes the mouse-driven interactions in PeakPo and the UI
location where each action is available.

The shared plot area is used in both the 1D pattern view and the Cake view.
Some actions are global to the plot, while others are enabled only in a
specific tab or dialog.

## Shared Plot Gestures

| Gesture | Scope | UI location | Result |
| --- | --- | --- | --- |
| Left drag | 1D plot and Cake plot | Plot area | Zoom to the dragged rectangle. |
| Hold `X` + left drag | 1D plot and Cake plot | Plot area | Zoom X only. |
| Hold `Y` + left drag | 1D plot and Cake plot | Plot area | Zoom Y only. |
| Hold `P` + left drag | 1D plot and Cake plot | Plot area | Pan the view. |
| Very small left drag | 1D plot and Cake plot | Plot area | Ignored to avoid accidental zooming. |
| Right click | 1D plot and Cake plot | Plot area | Zoom out by 20 percent. |
| Hold `X` + right click | 1D plot and Cake plot | Plot area | Zoom out 20 percent in X only. |
| Hold `Y` + right click | 1D plot and Cake plot | Plot area | Zoom out 20 percent in Y only. |
| Double right click | 1D plot and Cake plot | Plot area | Return to the full current view. |
| Left double click | 1D plot and Cake plot | Plot area | Inspect d-spacing and nearest JCPDS or HKL information. |

## Mouse Mode Toolbar

The plot toolbar includes a mouse mode selector:

| Mode | UI location | Purpose |
| --- | --- | --- |
| `Zoom` | Plot toolbar | Default navigation mode for rectangular zooming. |
| `ROI` | Plot toolbar | Enable ROI selection workflows. |
| `Peak` | Plot toolbar | Enable peak add, remove, and peak-drag actions. |
| `JCPDS` | Plot toolbar | Temporary inspect mode for the nearest JCPDS line; it returns to `Zoom` after a left click. |

The same toolbar also has a `Mouse Help` button. The `Shortcut keys` action
opens the same help dialog.

## ROI Workflows

### Map Tab

| Control | UI location | Mouse action |
| --- | --- | --- |
| `Select ROI` | `Map` tab, `ROI` group box | Activate ROI drawing on the shared 1D or Cake plot. |
| `Clear ROI` | `Map` tab, `ROI` group box | Remove the stored ROI and its overlay. |
| `Compute Map` | `Map` tab, `ROI` group box | Recompute the map from the selected ROI. |

Behavior:

| Gesture | Result |
| --- | --- |
| Click `Select ROI`, then left drag on the plot | Draw a map ROI. |
| Click `Select ROI` again | Cancel ROI selection mode. |
| Right click while ROI mode is active | Clear the current map ROI. |

### Sequence Tab

| Control | UI location | Mouse action |
| --- | --- | --- |
| `Select ROI` | `Sequence` tab, `ROI` group box | Activate ROI drawing on the shared 1D or Cake plot. |
| `Clear ROI` | `Sequence` tab, `ROI` group box | Remove the stored ROI and its overlay. |
| `Compute Seq.` | `Sequence` tab, `ROI` group box | Recompute the sequence from the selected ROI. |

Behavior:

| Gesture | Result |
| --- | --- |
| Click `Select ROI`, then left drag on the plot | Draw a sequence ROI. |
| Click `Select ROI` again | Cancel ROI selection mode. |
| Right click while ROI mode is active | Clear the current sequence ROI. |

### Cake Tab

| Control | UI location | Mouse action |
| --- | --- | --- |
| `Set ROI` / `ROI ON` | `Cake` tab, azimuthal CHI / ROI controls | Activate azimuthal ROI selection on the Cake plot. |
| `Add ROI` | `Cake` tab, azimuthal CHI / ROI controls | Add queued azimuthal ROI ranges to the table. |
| `Remove selected` | `Cake` tab, azimuthal CHI / ROI controls | Remove highlighted azimuthal ROI rows. |
| `Clear ranges` | `Cake` tab, azimuthal CHI / ROI controls | Clear all queued azimuthal ROI ranges. |
| `Integrate only` | `Cake` tab | Integrate the selected azimuthal ranges without opening the result. |
| `Integrate and open` | `Cake` tab | Integrate the selected azimuthal ranges and open the result for peak fitting. |

Behavior:

| Gesture | Result |
| --- | --- |
| Click `Set ROI`, then left drag on the Cake plot | Queue an azimuthal ROI range. |
| Draw additional left-drag ROIs | Queue more azimuthal ROI ranges. |
| Click `Add ROI` | Commit the queued ranges into the ROI table. |
| Click `Set ROI` again | Cancel Cake ROI selection mode. |

## Peak Fitting

Peak fitting mouse actions are available on the `Fits` tab. The main control is
the section titled `Add (Shift+left click) / Remove (Shift+right click) peaks`.

| Gesture | UI location | Result |
| --- | --- | --- |
| `Shift` + left click | `Fits` tab, plot area | Add a peak at the clicked position. |
| `Shift` + right click | `Fits` tab, plot area | Remove the nearest peak. |
| `Shift` + left drag on a selected peak | `Fits` tab, plot area | Move the selected peak position. |

Notes:

| Condition | Result |
| --- | --- |
| A peak row must be selected before dragging a peak marker | The drag updates the selected peak row. |
| If the current fit already exists | Moving a peak invalidates the fit result. |

## Peak Constraints and Background Setup

These actions use the plot as an input device for range selection.

### Peak Constraints Dialog

| Control | UI location | Result |
| --- | --- | --- |
| `Set position range from plot` | Peak constraints dialog | Open an editable X-range over the plot for the peak center limits. |
| `Set FWHM max from plot` | Peak constraints dialog | Open an editable X-range over the plot for the peak width limits. |

Editable range behavior:

| Gesture | Result |
| --- | --- |
| Drag a range edge | Resize the editable range. |
| Drag inside the range | Move the editable range. |
| Right click | Cancel the range edit. |

### Background Setup Tab

| Control | UI location | Result |
| --- | --- | --- |
| `Add range from plot` | `Fits` tab, `Background Setup` page | Add background anchor ranges by dragging on the plot. |
| `Remove range` | `Fits` tab, `Background Setup` page | Remove background anchor ranges by dragging over an existing range. |

Range-picking behavior:

| Gesture | Result |
| --- | --- |
| Left drag | Add or remove a background range. |
| Right click | Finish repeated range picking or cancel the active range tool. |

## Practical Summary

| UI area | Mouse actions that matter most |
| --- | --- |
| Plot toolbar | Zoom, ROI, Peak, JCPDS modes. |
| Map tab | Select ROI, clear ROI, compute map. |
| Sequence tab | Select ROI, clear ROI, compute sequence. |
| Cake tab | Draw azimuthal ROIs, add them to the table, integrate them. |
| Fits tab | Add/remove peaks, drag peaks, set constraint ranges, manage background anchors. |
