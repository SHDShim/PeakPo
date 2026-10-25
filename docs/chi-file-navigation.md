# CHI File Navigation

Use the **Name** or **Time** option beside the CHI navigation buttons to choose
the file order. The step control determines how many files **Next** or **Prev**
advances. Navigation stops at the first and last file; it does not wrap around.

With **Name** selected, PeakPo treats the filename before its final number as
the name set. For example, `file_001.chi` and `file_002.chi` are in the same
set, while `picture_001.chi` is in another set. The comparison ignores letter
case.

Before moving to a different name set, PeakPo shows the current and selected
filenames. Choose **Open selected file** to continue or **Stay on current file** to
cancel. This also applies when navigating with DPP files. With **Time**
selected, PeakPo does not ask about name sets.

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
active file and tab selection. These copies are stored in the operating
system's application data folder, separately from CHI PARAM folders. Uncheck
**Restore last working state when PeakPo starts** to disable both saving and
restoring the private copy. Recovery requires the original CHI file to remain
available at its saved path.
