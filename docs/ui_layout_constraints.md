# UI Layout Constraints: Cake Integration Tab

## Context
This document defines the mandatory grid layout for the Cake Integration section to prevent visual regressions.
- **Location:** `tabWidget_2Page2` $\rightarrow$ `groupBox_19` $\rightarrow$ `gridLayout_16`
- **Structure:** Strict 2×4 Grid

## Functional Grid Map
The following mapping links the visual label to the internal variable and its required coordinate. **Coordinates must be maintained regardless of label changes.**

| UI Label | Internal Variable | Coordinates (Row, Col) |
| :--- | :--- | :--- |
| **Set ROI** | `pushButton_HighlightSelectedMarker` | **(0, 0)** |
| **Add ROI** | `pushButton_AddAzi` | **(0, 1)** |
| **Remove Selected** | `pushButton_RemoveAzi` | **(0, 2)** |
| **Clear ranges** | `pushButton_ClearAziList` | **(0, 3)** |
| **Integrate and open** | `pushButton_IntegrateCake` | **(1, 0)** |
| **Integrate only** | `pushButton_InvertCakeBoxes` | **(1, 1)** |
| **Load setup** | `pushButton_LoadCakeMarkerFile` | **(1, 2)** |
| **Save setup** | `pushButton_SaveCakeMarkerFile` | **(1, 3)** |

## Strict Constraints
1. **No Rearrangement:** Do not change the `addWidget(widget, row, col)` parameters for these variables.
2. **Label Independence:** Modifications to button text (`setText()`) must not trigger changes to the grid coordinates.
3. **Variable Truth:** Use the `Internal Variable` column as the sole source of truth for positioning, not the `UI Label`.
