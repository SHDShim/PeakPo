import os
import glob
import re
import json
import math
from dataclasses import dataclass
import numpy as np

from ..utils import get_temp_dir, readchi
from ..ds_powdiff.DiffractionPattern import Pattern


@dataclass
class MapPointInfo:
    filepath: str
    filename: str
    frame_index: object = None
    x_pos: object = None
    y_pos: object = None


@dataclass
class CoordinateCandidate:
    axis: str
    priority: int
    group_path: str
    object_path: str
    value: float


_COORD_PRIORITY_NAMES = (
    ("scan", 0),
    ("measurement", 1),
    ("snapshot", 2),
    ("instrument", 3),
)

_SNAPSHOT_TOKENS = (
    "snapshot", "snapshots", "scan_snapshot",
    "detector_snapshot", "beamline_snapshot",
)


def _safe_text(value):
    if isinstance(value, bytes):
        try:
            return value.decode("utf-8", errors="ignore")
        except Exception:
            return ""
    return str(value or "")


def _name_tokens(text):
    return [t for t in re.split(r"[^a-z0-9]+", _safe_text(text).lower()) if t]


def _priority_for_path(path, nx_class=""):
    hay = "/".join(_name_tokens(path) + _name_tokens(nx_class))
    if any(tok in hay for tok in _SNAPSHOT_TOKENS):
        return 2
    for token, priority in _COORD_PRIORITY_NAMES:
        if token in hay:
            return priority
    return 4


def _axis_from_name(name):
    tokens = _name_tokens(name)
    if not tokens:
        return None
    x_tokens = {"x", "sx", "samplex", "sample_x", "stagex", "stage_x", "motorx", "motor_x"}
    y_tokens = {"y", "sy", "sampley", "sample_y", "stagey", "stage_y", "motory", "motor_y"}
    compact = "".join(tokens)
    if compact in x_tokens or tokens[-1] == "x":
        return "x"
    if compact in y_tokens or tokens[-1] == "y":
        return "y"
    if "x" in tokens and not ("pixel" in tokens or "size" in tokens or "axis" in tokens):
        return "x"
    if "y" in tokens and not ("pixel" in tokens or "size" in tokens or "axis" in tokens):
        return "y"
    return None


def _scalar_or_frame_value(raw, frame_index=None):
    arr = np.asarray(raw)
    if arr.size == 0:
        return None
    if arr.size == 1:
        value = float(arr.reshape(-1)[0])
        return value if np.isfinite(value) else None
    if frame_index is None:
        return None
    try:
        idx = int(frame_index)
    except Exception:
        return None
    flat = arr.reshape(-1)
    if idx < 0 or idx >= flat.size:
        return None
    value = float(flat[idx])
    return value if np.isfinite(value) else None


def _candidate_from_value(axis, priority, group_path, object_path, raw, frame_index):
    value = _scalar_or_frame_value(raw, frame_index=frame_index)
    if value is None:
        return None
    return CoordinateCandidate(
        axis=axis,
        priority=int(priority),
        group_path=str(group_path),
        object_path=str(object_path),
        value=float(value),
    )


def _collect_hdf5_coordinate_candidates(h5, frame_index=None):
    candidates = []

    def visit(path, obj):
        nx_class = _safe_text(getattr(obj, "attrs", {}).get("NX_class", ""))
        priority = _priority_for_path(path, nx_class=nx_class)
        group_path = os.path.dirname("/" + path).rstrip("/") or "/"
        axis = _axis_from_name(path)
        if axis is not None and hasattr(obj, "shape"):
            try:
                candidate = _candidate_from_value(
                    axis, priority, group_path, "/" + path, obj[()], frame_index)
                if candidate is not None:
                    candidates.append(candidate)
            except Exception:
                pass

        attrs = getattr(obj, "attrs", {})
        for attr_name, attr_value in attrs.items():
            axis_attr = _axis_from_name(attr_name)
            if axis_attr is None:
                continue
            candidate = _candidate_from_value(
                axis_attr, priority, group_path, "/" + path + f"@{attr_name}",
                attr_value, frame_index)
            if candidate is not None:
                candidates.append(candidate)

    h5.visititems(visit)
    return candidates


def _choose_unambiguous_coordinate_pair(candidates):
    for priority in sorted({c.priority for c in candidates}):
        by_group = {}
        for cand in candidates:
            if cand.priority != priority:
                continue
            by_group.setdefault(cand.group_path, {}).setdefault(cand.axis, []).append(cand)

        pairs = []
        for group_path, axes in by_group.items():
            if "x" not in axes or "y" not in axes:
                continue
            x_vals = {round(c.value, 12) for c in axes["x"]}
            y_vals = {round(c.value, 12) for c in axes["y"]}
            if len(x_vals) == 1 and len(y_vals) == 1:
                pairs.append((float(next(iter(x_vals))), float(next(iter(y_vals))), group_path))

        unique_pairs = {(round(x, 12), round(y, 12)) for x, y, __ in pairs}
        if len(unique_pairs) == 1:
            x, y = next(iter(unique_pairs))
            return float(x), float(y)
        if len(unique_pairs) > 1:
            return None
    return None


def extract_scan_coordinates(h5_path, frame_index=None):
    """
    Extract unambiguous physical scan coordinates from an HDF5 file.

    Search priority is scan, measurement, snapshot, instrument, then other
    metadata. If same-priority coordinate pairs disagree, return None.
    """
    try:
        import h5py
    except Exception:
        return None
    if (not h5_path) or (not os.path.exists(h5_path)):
        return None
    try:
        with h5py.File(h5_path, "r") as h5:
            candidates = _collect_hdf5_coordinate_candidates(
                h5, frame_index=frame_index)
    except Exception:
        return None
    return _choose_unambiguous_coordinate_pair(candidates)


def has_valid_scan_coordinates(h5_path, frame_index=None):
    return extract_scan_coordinates(h5_path, frame_index=frame_index) is not None


def parse_dioptas_map_filename(filename):
    """
    Parse map row/snapshot identifiers from names like map_1_001_0001.

    The final numeric block is a provenance/file identifier and is ignored.
    """
    stem = os.path.splitext(os.path.basename(str(filename)))[0]
    match = re.search(r"(?:^|_)map_(\d+)_(\d+)(?:_(\d+))?(?:$|_)", stem.lower())
    if match is None:
        return None
    return {
        "row_index": int(match.group(1)),
        "snapshot_index": int(match.group(2)),
    }


def discover_dioptas_metadata_files(param_dir):
    if not param_dir or not os.path.isdir(param_dir):
        return []
    patterns = [
        os.path.join(param_dir, "*.metadata.v1.json"),
        os.path.join(param_dir, "*.metadata.json"),
    ]
    files = []
    seen = set()
    for pattern in patterns:
        for path in sorted(glob.glob(pattern)):
            if path not in seen:
                seen.add(path)
                files.append(path)
    return files


def _json_load_allow_nan(path):
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def _metadata_dataset_values(payload, wanted_names):
    wanted = {str(name).strip().lower() for name in wanted_names}
    for source in payload.get("source_files", []) or []:
        hdf5 = source.get("hdf5", {}) or {}
        nodes = hdf5.get("nodes", {}) or {}
        for node in nodes.values():
            name = str(node.get("name", "")).strip().lower()
            attrs = node.get("attrs", {}) or {}
            attr_name = str(attrs.get("NDAttrName", "")).strip().lower()
            if name not in wanted and attr_name not in wanted:
                continue
            dataset = node.get("dataset", {}) or {}
            if "value" in dataset:
                return dataset.get("value")
    return None


def _metadata_scalar(payload, key, default=None):
    value = payload.get(key, default)
    try:
        return int(value)
    except Exception:
        return default


def _as_float_list(values):
    if values is None:
        return []
    out = []
    for value in values:
        try:
            fval = float(value)
        except Exception:
            out.append(None)
            continue
        out.append(fval if np.isfinite(fval) else None)
    return out


class DioptasMetadataExport:
    def __init__(self, path, payload):
        self.path = path
        self.payload = payload
        self.schema_version = str(payload.get("schema_version", ""))
        self.output_base_name = str(payload.get("output_base_name", ""))
        self.image_index = _metadata_scalar(payload, "image_index", None)
        self.horizontal = _as_float_list(
            _metadata_dataset_values(payload, ("Horizontal", "Sample Horizontal")))
        self.vertical = _as_float_list(
            _metadata_dataset_values(payload, ("Vertical", "Sample Vertical")))
        self.focus = _as_float_list(
            _metadata_dataset_values(payload, ("Focus", "Sample Focus")))
        self.xrd_file_numbers = _metadata_dataset_values(payload, ("XRD File Number",))
        self.xrd_file_names = _metadata_dataset_values(payload, ("XRD File Name",))

    @classmethod
    def from_file(cls, path):
        payload = _json_load_allow_nan(path)
        export = cls(path, payload)
        if export.schema_version not in ("1.0", "1"):
            raise ValueError(f"Unsupported metadata schema_version: {export.schema_version}")
        return export

    def get_scan_geometry(self):
        return {
            "n_horizontal": len(self.horizontal),
            "n_vertical": len(self.vertical),
            "n_focus": len(self.focus),
        }

    def get_snapshot_mapping(self):
        return {
            "xrd_file_numbers": self.xrd_file_numbers,
            "xrd_file_names": self.xrd_file_names,
        }

    def _coordinate_at_index(self, index):
        if index is None:
            return None
        if index < 0:
            return None
        if index >= len(self.horizontal) or index >= len(self.vertical):
            return None
        x_pos = self.horizontal[index]
        y_pos = self.vertical[index]
        if x_pos is None or y_pos is None:
            return None
        return float(x_pos), float(y_pos)

    def get_coordinates(self, filename=None, row_index=None,
                        snapshot_index=None, frame_index=None):
        if frame_index is not None:
            coords = self._coordinate_at_index(int(frame_index))
            if coords is not None:
                return coords

        parsed = parse_dioptas_map_filename(filename or "")
        if parsed is not None:
            row_index = parsed["row_index"]
            snapshot_index = parsed["snapshot_index"]

        if snapshot_index is not None:
            # Beamline filenames use one-based snapshot labels.
            coords = self._coordinate_at_index(int(snapshot_index) - 1)
            if coords is not None:
                return coords

        if self.image_index is not None:
            coords = self._coordinate_at_index(int(self.image_index))
            if coords is not None:
                return coords

        return None


class DioptasMetadataCollection:
    def __init__(self, exports=None):
        self.exports = list(exports or [])

    @classmethod
    def from_param_dir(cls, param_dir):
        exports = []
        for path in discover_dioptas_metadata_files(param_dir):
            try:
                exports.append(DioptasMetadataExport.from_file(path))
            except Exception:
                continue
        return cls(exports)

    def get_coordinates(self, filename=None, frame_index=None):
        base = os.path.splitext(os.path.basename(str(filename or "")))[0]
        for export in self.exports:
            if export.output_base_name and export.output_base_name != base:
                continue
            coords = export.get_coordinates(filename=filename, frame_index=frame_index)
            if coords is not None:
                return coords
        for export in self.exports:
            coords = export.get_coordinates(filename=filename, frame_index=frame_index)
            if coords is not None:
                return coords
        return None

    def get_scan_geometry(self):
        return [export.get_scan_geometry() for export in self.exports]

    def get_snapshot_mapping(self):
        return [export.get_snapshot_mapping() for export in self.exports]


def _coord_to_bin(value, decimals=3):
    scale = 10 ** int(decimals)
    return int(np.rint(float(value) * scale))


def _uniform_axis_from_bins(bins, decimals=3):
    unique_bins = sorted(set(int(b) for b in bins))
    if len(unique_bins) <= 1:
        return unique_bins
    diffs = [
        b1 - b0 for b0, b1 in zip(unique_bins[:-1], unique_bins[1:])
        if (b1 - b0) > 0
    ]
    if not diffs:
        return unique_bins
    step = int(diffs[0])
    for diff in diffs[1:]:
        step = int(math.gcd(step, int(diff)))
    step = max(step, 1)
    return list(range(unique_bins[0], unique_bins[-1] + step, step))


def _bin_to_coord(bin_value, decimals=3):
    return round(float(bin_value) / float(10 ** int(decimals)), int(decimals))


def build_coordinate_grid(values, x_positions, y_positions, decimals=3):
    valid = []
    for idx, (value, x, y) in enumerate(zip(values, x_positions, y_positions)):
        if x is None or y is None:
            continue
        valid.append((
            idx,
            float(value),
            _coord_to_bin(x, decimals=decimals),
            _coord_to_bin(y, decimals=decimals),
        ))
    if not valid:
        return None
    unique_x = _uniform_axis_from_bins(
        [x_bin for __, __, x_bin, __ in valid], decimals=decimals)
    unique_y = _uniform_axis_from_bins(
        [y_bin for __, __, __, y_bin in valid], decimals=decimals)
    x_to_col = {x: i for i, x in enumerate(unique_x)}
    y_to_row = {y: i for i, y in enumerate(unique_y)}
    grid = np.full((len(unique_y), len(unique_x)), np.nan, dtype=float)
    coord_to_index = {}
    duplicates = set()
    for idx, value, x_bin, y_bin in valid:
        key = (_bin_to_coord(x_bin, decimals=decimals),
               _bin_to_coord(y_bin, decimals=decimals))
        if key in coord_to_index:
            duplicates.add(key)
            continue
        row = y_to_row[y_bin]
        col = x_to_col[x_bin]
        grid[row, col] = value
        coord_to_index[key] = idx
    if duplicates:
        return None
    return (
        grid,
        [_bin_to_coord(x, decimals=decimals) for x in unique_x],
        [_bin_to_coord(y, decimals=decimals) for y in unique_y],
        coord_to_index,
    )


def load_chi_xy(chi_path, chi_cache):
    if chi_path in chi_cache:
        return chi_cache[chi_path]
    __, __, x, y = readchi(chi_path)
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    chi_cache[chi_path] = (x, y)
    return x, y


def load_bgsub_or_raw_xy(chi_path, use_bgsub, chi_cache):
    if not bool(use_bgsub):
        return load_chi_xy(chi_path, chi_cache)

    # Priority 1: temp bgsub file under <chi>-param/
    try:
        temp_dir = get_temp_dir(chi_path)
        base = os.path.splitext(os.path.basename(chi_path))[0]
        temp_bgsub = os.path.join(temp_dir, f"{base}.bgsub.chi")
        if os.path.exists(temp_bgsub):
            __, __, x, y = readchi(temp_bgsub)
            return np.asarray(x, dtype=float), np.asarray(y, dtype=float)
    except Exception:
        pass

    # Priority 2: sibling bgsub file next to chi
    sibling_bgsub = os.path.splitext(chi_path)[0] + ".bgsub.chi"
    if os.path.exists(sibling_bgsub):
        __, __, x, y = readchi(sibling_bgsub)
        return np.asarray(x, dtype=float), np.asarray(y, dtype=float)

    # Fallback: raw chi if bgsub file is unavailable.
    return load_chi_xy(chi_path, chi_cache)


def refresh_temp_bgsub_for_chi_files(
        chi_files,
        preferred_chi=None,
        bg_roi=None,
        bg_params=None,
        progress_callback=None):
    """
    Force-refresh temporary bg/bgsub files for map/sequence workflows.
    Files are written only under each CHI's temporary PARAM directory.
    """
    files = [str(f) for f in (chi_files or []) if f]
    if not files:
        return {"reference": None, "updated": 0, "failed": 0, "failures": []}

    preferred = str(preferred_chi) if preferred_chi else None
    if preferred in files:
        reference = preferred
    else:
        reference = files[0]

    if (bg_roi is None) or (len(bg_roi) < 2):
        roi = None
    else:
        roi = [float(bg_roi[0]), float(bg_roi[1])]
    if (bg_params is None) or (len(bg_params) < 3):
        params = [20, 10, 20]
    else:
        params = [int(bg_params[0]), int(bg_params[1]), int(bg_params[2])]

    if roi is None:
        __, __, x_ref, __ = readchi(reference)
        x_ref = np.asarray(x_ref, dtype=float)
        roi = [float(np.nanmin(x_ref)), float(np.nanmax(x_ref))]

    failures = []
    updated = 0
    for i, chi_path in enumerate(files):
        if progress_callback is not None:
            progress_callback(i, len(files), chi_path)
        try:
            ptn = Pattern(chi_path)
            x_raw, __ = ptn.get_raw()
            x_raw = np.asarray(x_raw, dtype=float)
            roi_min = max(float(np.nanmin(x_raw)), float(min(roi)))
            roi_max = min(float(np.nanmax(x_raw)), float(max(roi)))
            if roi_max <= roi_min:
                roi_min = float(np.nanmin(x_raw))
                roi_max = float(np.nanmax(x_raw))
            ptn.subtract_bg([roi_min, roi_max], params=params, yshift=0)
            ptn.write_temporary_bgfiles(get_temp_dir(chi_path))
            updated += 1
        except Exception as exc:
            failures.append((chi_path, str(exc)))
    if progress_callback is not None:
        progress_callback(len(files), len(files), None)

    return {
        "reference": reference,
        "updated": int(updated),
        "failed": int(len(failures)),
        "failures": failures,
    }


def find_temp_cake_triplet(chi_path):
    temp_dir = get_temp_dir(chi_path)
    tth_files = sorted(glob.glob(os.path.join(temp_dir, "*.tth.cake.npy")))
    if not tth_files:
        return None

    stem_map = {}
    for tth_f in tth_files:
        stem = tth_f[: -len(".tth.cake.npy")]
        azi_f = stem + ".azi.cake.npy"
        int_f = stem + ".int.cake.npy"
        if os.path.exists(azi_f) and os.path.exists(int_f):
            stem_map[stem] = (tth_f, azi_f, int_f)
    if not stem_map:
        return None

    # Most recent triplet first.
    triplets = sorted(stem_map.values(), key=lambda t: os.path.getmtime(t[2]), reverse=True)
    return triplets[0]


def load_cake_data(chi_path, cake_cache):
    if chi_path in cake_cache:
        return cake_cache[chi_path]

    triplet = find_temp_cake_triplet(chi_path)
    if triplet is None:
        return None

    tth = np.load(triplet[0])
    azi = np.load(triplet[1])
    intensity = np.load(triplet[2])
    payload = (
        np.asarray(tth, dtype=float),
        np.asarray(azi, dtype=float),
        np.asarray(intensity, dtype=float),
    )
    cake_cache[chi_path] = payload
    return payload
