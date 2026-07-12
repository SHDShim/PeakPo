# UI Layout Constraints: Cake Integration Tab

## Context
This document defines the mandatory grid layout for the Cake Integration section to prevent visual regressions.
- **Location:** `tabWidget_2Page2` $\rightarrow$ `scrollAreaWidgetContents_8` $\rightarrow$ `verticalLayout_37`
- **Structure:**
  - Top: `groupBox_19` $\rightarrow$ `gridLayout_16` (2×2 grid, all buttons `Expanding` horizontal)
  - Middle: `tableWidget_DiffImgAzi` (ROI table)
  - Bottom: `frame_CakeIntegrationBottom` $\rightarrow$ `horizontalLayout_CakeIntegrationBottom` (side-by-side, both `Expanding`)

## Top Grid Map (`gridLayout_16`)
All buttons use `QSizePolicy.Expanding` horizontally.

| UI Label | Internal Variable | Coordinates (Row, Col) |
| :--- | :--- | :--- |
| **Set ROI** | `pushButton_HighlightSelectedMarker` | **(0, 0)** |
| **Add ROI** | `pushButton_AddAzi` | **(0, 1)** |
| **Integrate and open** | `pushButton_IntegrateCake` | **(1, 0)** |
| **Integrate only** | `pushButton_InvertCakeBoxes` | **(1, 1)** |

Note: "Load setup" (`pushButton_LoadCakeMarkerFile`) and "Save setup" (`pushButton_SaveCakeMarkerFile`) have been removed.

## Bottom Row (`frame_CakeIntegrationBottom`)
Both buttons use `QSizePolicy.Expanding` horizontally and are side-by-side.

| UI Label | Internal Variable |
| :--- | :--- |
| **Remove selected** | `pushButton_RemoveAzi` |
| **Clear ranges** | `pushButton_ClearAziList` |

## Styling
- `pushButton_IntegrateCake` ("Integrate and open") uses red accent:
  - Base: `#b22222`, Hover: `#c92a2a`, Pressed: `#8f1b1b`, Border: `#7a1313`

## Strict Constraints
1. **No Rearrangement:** Do not change the `addWidget(widget, row, col)` parameters for the top grid variables.
2. **Label Independence:** Modifications to button text (`setText()`) must not trigger changes to the grid coordinates.
3. **Variable Truth:** Use the `Internal Variable` column as the sole source of truth for positioning, not the `UI Label`.