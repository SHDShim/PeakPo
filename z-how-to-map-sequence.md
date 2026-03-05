# How to Use Map and Sequence in PeakPo

## Map (2D spatial map)

1. Open the `Map` tab.
2. Click `Load CHI files` and select all map `.chi` files.
3. Check `Nx`, `Ny`:
- They are auto-guessed.
- `Nx * Ny` must equal number of loaded files.
4. Choose ROI:
- Click `Select ROI`.
- Drag on 1D pattern for 1D ROI, or on cake image for 2D ROI.
5. Click `Compute Map` (or ROI selection auto-computes).
6. Click a pixel in map image to load that file into main 1D/2D view.
7. Optional:
- Change colormap / reverse / log.
- Use `Auto`, `%`, `Reset` for map scale.
- Export with `Export Image` or `Export NPY`.

### Notes

- File order is sorted by filename number (with special handling for `map_###` names).
- If `Bg` is ON, 1D integration uses bg-subtracted CHI when available.
- 2D ROI uses raw cake intensity (no bg subtraction).

---

## Sequence (intensity vs file number)

1. Open the `Seq` tab.
2. Click `Load CHI files` and select sequence `.chi` files.
3. Choose ROI:
- Click `Select ROI`.
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
