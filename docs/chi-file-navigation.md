# CHI File Navigation

Use the **Name** or **Time** option beside the CHI navigation buttons to choose
the file order. The step control determines how many files **Next** or **Prev**
advances. Navigation stops at the first and last file; it does not wrap around.
CHI and DPP extension matching is case-insensitive, so folders copied from
Windows can contain both `.CHI` and `.chi` files. PeakPo ignores macOS `._`
metadata sidecars when building the navigation list.

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
CHI is opened. It is synchronized with **How Prev/Next opens another CHI**
under **When next file already has information** in **JCPDS > Data**. The
selection stays in effect for subsequent navigation.
The toolbar uses short labels: **Carry if none**, **Force carry**, **Existing only**, and
**Custom**, in the order of the full Config choices below.

- **Carry over only if no existing** (default): use a saved PARAM when present; otherwise
  carry enabled categories from the current CHI. This preserves the behavior
  of the former **Existing** option in saved preferences.
- **Force carryover**: replace enabled categories with current settings.
  Other categories in a saved PARAM remain intact.
- **Use existing**: load the destination's saved PARAM without carry-over.
  If no saved PARAM exists, open the CHI with fresh setup defaults.
- **Custom**: use the separate JCPDS and other-setting rules. The separate
  controls appear only in this mode. By default, both rules keep the
  destination's existing JCPDS and other information.

An explicitly saved setup choice is retained. Older category preferences
remain available under **Custom**, but do not change the default choice.

When an existing setup loads, the top toolbar and JCPDS tab show the same
saved pressure and temperature values. Editing either control updates the
other control and the JCPDS reference plot.
If a PARAM file contains an invalid saved pressure or temperature, PeakPo
shows an error and skips that setup instead of stopping the application.
If PONI is missing, PeakPo warns before opening the CHI and offers
**Choose PONI**, **Use current PONI** (when available), **Open without PONI**,
or **Stay on current file**. Choosing a PONI copies it into the destination's
PARAM folder. **Choose PONI** is the default action. If the file opens without
a PONI, existing saved Cake data can still be displayed as a reference, but
Cake controls are disabled. Use the PONI picker in **Cake > Config** to enable
processing, display controls, and integration. With neither PONI nor cached
Cake, the CHI opens without Cake. A PONI that pyFAI can read but
Dioptas cannot parse directly is normalized in a temporary copy for Cake
processing; the PARAM copy is unchanged.
When the destination has no unique readable PONI in its PARAM folder and no
usable PONI reference in its saved setup, navigation warns about the missing
calibration. An unreadable PONI file does not enable Cake controls. A selected
or carried PONI is copied into the destination PARAM folder before the CHI
opens. With no usable PONI, azimuthal integration and 2D Map/Sequence analysis
are unavailable; 1D Map/Sequence analysis remains available.
If the destination fails to open and the current CHI remains open, PeakPo
removes a new PONI copy. This one-file choice takes precedence over the
navigation mode's PONI rule; closing the prompt leaves the current CHI open.

The red dot on Prev or Next means its destination has a valid saved PARAM;
the hollow gray dot means it does not. The toolbar navigation dropdown uses the
normal font color. **How Prev/Next opens another CHI** in Config uses the normal
font color for Custom, Force carryover, and Carry over only if no existing,
and red when **Use existing** is selected. The tooltip gives the destination
filename and action. A button is disabled when no file exists in that direction at the
selected step. PeakPo watches the active CHI folder and updates the buttons
when new CHI files appear. While either button is disabled, it also checks the
folder every two seconds in case a network-mounted folder does not report file
changes. The dot describes the destination and does not indicate whether the
current file has unsaved changes.

The **Save** button has its normal toolbar appearance when the current PARAM
matches the state loaded or last saved for that CHI. It turns yellow when
PARAM settings change, including settings carried into the file. This status
updates after navigation and periodically while editing; reverting all
changes restores the normal appearance. Automatic plot setup after opening an
existing setup does not count as a user change.

The Cake histogram's blue and orange intensity limits are remembered separately
for each CHI during navigation. Returning to a file restores its adjusted
limits and histogram view. Saving PARAM or a recovery snapshot also stores the
exact adjusted limits; reopening that setup restores them.

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
  information fills a missing category, a new CHI without PARAM has unsaved
  setup changes, or an automatically created session has changed. A manual
  Save remains authoritative for the current file.
- **Every changed session** also updates existing sessions during navigation.
- **Never** leaves PARAM saving entirely to the manual Save action.

PeakPo saves the current file only after the next file exists and any name-set
transition has been accepted. An automatic save adds a backup entry only when
the PARAM contents change. If the save fails, navigation stops on the current
file. On macOS volumes, `._` metadata files beside PARAM data are ignored;
they are not part of the saved setup. Temporary save cleanup also tolerates
these metadata files disappearing while their matching data files are removed.

**Working state recovery** is enabled by default. PeakPo saves a private copy
of the open CHI analysis every three minutes and on a normal quit. During
navigation it records the active CHI, tab selection, and saved PARAM location
when PARAM exists. If a CHI has no saved PARAM, navigation writes a full private
snapshot instead. It restores the recorded file and setup at the next launch,
then rescales the plot to the recovered data. Recent unsaved changes to the
file opened by navigation may be absent until the next periodic snapshot or
normal quit; use **Save** when those changes must be preserved immediately.
When a departing file has unsaved setup changes, PeakPo also keeps a full
private copy while you visit other CHI files. **Existing only** always opens
that file's saved PARAM when one exists, so Save is gray until you change the
setup. For a CHI without saved PARAM, PeakPo can restore its private working
copy on return; the Save button is yellow until you save it. Clean copies from
previous files are removed during navigation.
These copies are stored in the operating system's application data folder,
separately from CHI PARAM folders. Uncheck
**Restore last working state when PeakPo starts** to disable both saving and
restoring the private copy. Recovery requires the original CHI file to remain
available at its saved path.
If recovery is off and a navigation choice would leave unsaved setup changes,
PeakPo asks whether to save PARAM, leave without saving, or stay on the file.
If an enabled recovery snapshot fails while there are unsaved changes,
navigation stops on the current file.
