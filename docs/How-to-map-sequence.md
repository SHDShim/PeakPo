# How to Use Map and Sequence in PeakPo

## Map (2D spatial map)

1. Open the `Map` tab.
2. Click `Load CHI files` and select all map `.chi` files. PeakPo saves the
   selected file list, grid, ROI, and Map display controls under `map_param/`.
   When a CHI from that saved set is opened later, the Map tab restores those
   controls and recomputes the map when the Map tab is opened. If the folder contains
   several saved sets, use `Map set` in the Data panel to switch between them.
   An older `map_param/` with no saved set record is upgraded by grouping CHI
   files that share the current file's name pattern.
   If the plotted CHI belongs to no saved Map set, PeakPo clears the loaded
   Map data and plot while leaving the CHI plot open. Saved sets remain
   available in the `Map set` dropdown.
   If the currently plotted CHI is outside the selected set, PeakPo opens the
   file at the map grid's center. Before this automatic switch, PeakPo asks
   whether to save the current CHI's PARAM session, open without saving PARAM,
   or stay on the current file. If the plotted CHI is already in the set, it
   stays open without a prompt. The normal CHI opening process loads the
   selected file's PARAM session when available. Clicking a map pixel follows
   the configured **Save PARAM on navigation** setting.
3. Check `Nx`, `Ny`:
- They are auto-guessed.
- `Nx * Ny` must equal number of loaded files.
- Leave `Input order / ignore metadata` checked to use the selected file order.
- Uncheck it to use metadata coordinates or map file numbers when available.
4. Choose ROI:
- Click the global ROI mouse-mode button.
- Drag on 1D pattern for 1D ROI, or on cake image for 2D ROI.
5. Click `Compute Map` (or ROI selection auto-computes).
6. Click a pixel in map image to load that file into main 1D/2D view.
7. Optional:
- Change colormap / reverse / log.
- Use `Auto`, `%`, `Reset` for map scale.
- Export with `Export Image` or `Export NPY`.

### Notes

- File order is sorted by filename number (with special handling for `map_###` names).
- If `Bg` is ON, Map fits the background using the current background ROI and
  parameters. Changing the Map ROI reuses that fit; changing the background
  controls or a source CHI recomputes it. Map does not write these derived
  results into each file's PARAM session.
- For CHI files in one folder, Map saves each selected file set in a named
  subfolder of `map_param/`. Derived 1D data is disposable, but the same
  subfolder also holds the Map tab's saved state. Deleting `map_param/`
  removes both the cached calculations and saved Map selections. If the data
  folder is read-only, Map works in memory for the current session.
- 2D ROI uses raw cake intensity (no bg subtraction).

---

## Sequence (intensity vs file number)

1. Open the `Seq` tab.
2. Click `Load CHI files` and select sequence `.chi` files.
3. Choose ROI:
- Click the global ROI mouse-mode button.
- Drag on 1D pattern or 2D cake.
4. Click `Compute Seq.` (or ROI selection auto-computes).
5. Read result:
- X = file number (integer ticks).
- Y = integrated intensity in selected ROI.
- Title shows selected 2theta range.
6. Click a point in the sequence plot to load that file into main 1D/2D view.
7. Export with `Export Image` or `Export NPY`.

### Notes

- Sequence files are sorted by numbers in filename.
- If `Bg` is ON, 1D uses bg-subtracted CHI when available.
- 2D ROI uses raw cake intensity.

---

## Practical tips

- For 2D ROI in Map/Seq, make sure data exists for each file (generated in normal cake workflow).
- If result looks flat or empty, check ROI range and whether selected files actually contain that peak region.
