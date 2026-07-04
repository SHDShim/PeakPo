# What is New in PeakPo

## Version 7.11 (since 7.10.12)

### JCPDS Share — Import/Export JCPDS Sets
- **Export Set**: saves all current JCPDS cards and a `pkpo_jcpds.json` into a new `JCPDS-share-YYYY-MM-DD` folder next to the chi file. The JSON contains the full JCPDS table state needed to repopulate the table on import.
- **Import Set**: opens a directory chooser to load an exported JCPDS Share folder; validates the folder first. If the JCPDS table is not empty you are asked whether to save a backup snapshot before importing.

### Improved Map & Metadata Handling
- **Metadata-driven map construction** from `dioptas_batch_gui` JSON metadata — map points are now placed at their correct coordinates instead of by file order.
- **Structured Metadata table** (File > Metadata) with grouped scientific metadata fields and a searchable raw JSON viewer below.
- **Interactive histogram-based map and cake color-scale controls** with draggable min/max bars and range sliding.
- Map pixels now start from the top-left corner; pixel coordinates shown in hover text when metadata coordinates are unavailable.

### Smarter CHI File Filtering
- **Three-mode CHI file chooser**: show all CHI files, only CHI files with JCPDS, or CHI files without JCPDS.
- **JCPDS-only filter**: quickly show only `.chi` files that have a corresponding `pkpo_jcpds.json` file.

### User Experience Improvements
- **Ignore filenumber option** for controlling map data input order.
- **Progress dialogs** for map loading and processing.
- **Backup log** accessible in the status bar, with restore capability for any previous session state.
- Wildcard input support (e.g., `map2_*.chi`) in the CHI multi-file chooser.