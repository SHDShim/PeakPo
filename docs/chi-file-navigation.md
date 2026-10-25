# CHI File Navigation

Use the **Name** or **Time** option beside the CHI navigation buttons to choose
the file order. The step control determines how many files **Next** or **Prev**
advances. Navigation stops at the first and last file; it does not wrap around.

With **Name** selected, PeakPo treats files as the same name set when they
share the text before a changing final number. For example, `file_001.chi`
and `file_002.chi` are in the same set, while `picture_001.chi` is in another.
Files with a changing second-last number and the same final number also stay
in one set: `8R_map_3_S1_map_11_003_0001.chi` and
`8R_map_3_S1_map_11_002_0001.chi`. The comparison ignores letter case.

Before moving to a different name set, PeakPo shows the current and selected
filenames. Choose **Open selected file** to continue or **Stay on current file** to
cancel. This also applies when navigating with DPP files. With **Time**
selected, PeakPo does not ask about name sets.

## Setup choice for Prev and Next

The toolbar control between **Prev** and **Next** selects how the destination
CHI is opened. It is synchronized with **Prev/Next action** under **When next
file already has information** in **JCPDS > Data**. The selection stays in
effect for subsequent navigation.

- **Existing** (default for new installations): use the destination's saved PARAM
  without carry-over. When no saved PARAM exists, carry the enabled categories.
- **Carry**: replace the enabled categories with current settings. Any other
  categories in the destination's saved PARAM remain intact.
- **Custom**: use the older separate JCPDS and other-setting rules. Existing
  installations with those saved rules start in Custom so their behavior is
  preserved. The separate controls appear only in this mode.

The red dot on Prev or Next means its destination has a valid saved PARAM;
the hollow gray dot means it does not. **Setup: Existing** appears in the
same red when selected. The tooltip gives the destination
filename and action. A button is disabled when no file exists in that
direction at the selected step. The dot describes the destination and does
not indicate whether the current file has unsaved changes.

The **Save** button has its normal toolbar appearance when the current PARAM
matches the state loaded or last saved for that CHI. It turns yellow when
PARAM settings change, including settings carried into the file. This status
updates after navigation and periodically while editing; reverting all
changes restores the normal appearance. Automatic plot setup after opening an
existing setup does not count as a user change.

**Add Current Chi to Waterfall List** is in the Waterfall tab above **Update
plot**. It adds the current CHI to the waterfall list.

## Opening a CHI with a saved PARAM

When **Open** selects a different CHI file with a valid saved PARAM session,
PeakPo asks whether to **Use existing PARAM**, **Carry current settings**, or
**Cancel**. The choice also applies when a CHI path is entered in the filename
field. **Use existing PARAM** is the default. **Carry current settings** loads
the selected file, then replaces its saved values in the categories enabled
under **Keep these settings for the next file**. Categories not enabled there
retain the selected file's saved values. The carry-over status identifies the
categories applied. Cancel leaves the current file open.

Opening a CHI without a saved PARAM does not show this choice. When there is
no current CHI to carry from, PeakPo loads the selected file's PARAM directly.

## Saving while navigating

In **JCPDS > Data**, the **Save PARAM when leaving a file** control has three
choices:

- **New or incomplete sessions** (default) saves a CHI session when carried
  information fills a missing category or an automatically created session has
  changed. A manual Save remains authoritative for the current file.
- **Every changed session** also updates existing sessions during navigation.
- **Never** leaves PARAM saving entirely to the manual Save action.

PeakPo saves the current file only after the next file exists and any name-set
transition has been accepted. An automatic save adds a backup entry only when
the PARAM contents change. If the save fails, navigation stops on the current
file.

**Working state recovery** is enabled by default. PeakPo saves a private copy
of the open CHI analysis every three minutes, on navigation, and on a normal
quit. It restores the latest available copy at the next launch, including the
active file and tab selection, then rescales the plot to the recovered data.
These copies are stored in the operating system's application data folder,
separately from CHI PARAM folders. Uncheck
**Restore last working state when PeakPo starts** to disable both saving and
restoring the private copy. Recovery requires the original CHI file to remain
available at its saved path.
