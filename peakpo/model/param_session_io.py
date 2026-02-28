import json
import os
import shutil
import tempfile
import datetime
import io
import glob
import hashlib
import re
from dataclasses import dataclass
from typing import Optional

import numpy as np

from ..utils import get_temp_dir
from ..ds_powdiff import PatternPeakPo
from ..ds_jcpds import JCPDSplt, DiffractionLine
from ..ds_section import Section
from ..ds_cake import DiffImg


MANIFEST_FILE = "peakpo_manifest.json"
SESSION_FILE = "pkpo_session.json"
SECTIONS_FILE = "pkpo_sections.json"
UI_STATE_FILE = "pkpo_ui_state.json"
JCPDS_FILE = "pkpo_jcpds.json"
BACKUP_INDEX_FILE = "pkpo_backup_index.json"

FORMAT_FAMILY = "peakpo-session"
FORMAT_VERSION = 1


@dataclass
class SaveResult:
    param_dir: str
    manifest_path: str
    backup_id: Optional[str]
    changed_files: list[str]


class _ParamLite:
    def __init__(self, value=None, stderr=None, vary=True):
        self.value = value
        self.stderr = stderr
        self.vary = vary


class _FitResultLite:
    def __init__(self, payload=None):
        payload = payload or {}
        self.chisqr = payload.get("chisqr")
        self.redchi = payload.get("redchi")
        self.aic = payload.get("aic")
        self.bic = payload.get("bic")
        self.best_fit = np.asarray(payload.get("best_fit", []), dtype=float)
        self._components = {
            k: np.asarray(v, dtype=float)
            for k, v in payload.get("components", {}).items()
        }
        self.params = {}
        for key, val in payload.get("params", {}).items():
            self.params[key] = _ParamLite(
                value=val.get("value"),
                stderr=val.get("stderr"),
                vary=val.get("vary", True),
            )

    def eval_components(self, x=None):
        return self._components


def _json_default(obj):
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    if isinstance(obj, np.integer):
        return int(obj)
    if isinstance(obj, np.floating):
        return float(obj)
    if isinstance(obj, np.bool_):
        return bool(obj)
    if hasattr(obj, "__dict__"):
        return obj.__dict__
    return str(obj)


def _atomic_write_bytes(path, payload):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile("wb", delete=False, dir=os.path.dirname(path)) as f:
            tmp_path = f.name
            f.write(payload)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, path)
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.remove(tmp_path)


def _atomic_write_json(path, data):
    payload = json.dumps(data, indent=2, sort_keys=True, default=_json_default).encode("utf-8")
    _atomic_write_bytes(path, payload)


def _file_bytes(path):
    with open(path, "rb") as f:
        return f.read()


def _relpath_or_abs(path, root):
    if path is None:
        return None
    path = str(path)
    try:
        rel = os.path.relpath(path, root)
    except Exception:
        return path
    if rel.startswith(".."):
        return path
    return rel


def _resolve_path(stored_path, root):
    if stored_path is None:
        return None
    if os.path.isabs(stored_path):
        return stored_path
    return os.path.normpath(os.path.join(root, stored_path))


def _bg_temp_names(pattern):
    base = os.path.splitext(os.path.basename(pattern.fname))[0]
    return f"{base}.bgsub.chi", f"{base}.bg.chi"


def _serialize_pattern(
        pattern, chi_root, fallback_relpath=None, force_abs_fname=False):
    if pattern is None:
        return None
    bgsub_name, bg_name = _bg_temp_names(pattern)
    stored_fname = getattr(pattern, "_pkpo_original_fname", None) or getattr(pattern, "fname", None)
    if fallback_relpath is None:
        fallback_relpath = getattr(pattern, "_pkpo_fallback_relpath", None)
    stored_fname_out = str(stored_fname) if force_abs_fname else _relpath_or_abs(stored_fname, chi_root)
    return {
        "fname": stored_fname_out,
        "fallback_fname": fallback_relpath,
        "wavelength": getattr(pattern, "wavelength", None),
        "color": getattr(pattern, "color", None),
        "display": getattr(pattern, "display", None),
        "bgsub_file": bgsub_name,
        "bg_file": bg_name,
    }


def _load_pattern(payload, chi_root, temp_dir):
    if payload is None:
        return None
    ptn = PatternPeakPo()
    fname_primary = _resolve_path(payload.get("fname"), chi_root)
    fallback_stored = payload.get("fallback_fname")
    if fallback_stored is None:
        fname_fallback = None
    elif os.path.isabs(str(fallback_stored)):
        fname_fallback = str(fallback_stored)
    else:
        fname_fallback = os.path.normpath(os.path.join(temp_dir, str(fallback_stored)))

    used_fallback = False
    if fname_primary and os.path.exists(fname_primary):
        ptn.read_file(fname_primary)
        ptn.fname = fname_primary
    elif fname_fallback and os.path.exists(fname_fallback):
        ptn.read_file(fname_fallback)
        ptn.fname = fname_fallback
        used_fallback = True
    else:
        ptn.fname = fname_primary
        ptn.x_raw = None
        ptn.y_raw = None
    ptn.wavelength = payload.get("wavelength", 0.3344)
    ptn.color = payload.get("color", "white")
    ptn.display = payload.get("display", False)
    ptn._pkpo_original_fname = fname_primary
    ptn._pkpo_fallback_fname = fname_fallback
    ptn._pkpo_fallback_relpath = fallback_stored
    ptn._pkpo_fallback_in_use = used_fallback
    # Keep background-subtracted state in legacy chi files.
    if ptn.fname is not None:
        ptn.read_bg_from_tempfile(temp_dir=temp_dir)
    return ptn


def _serialize_jcpds_item(phase, chi_root):
    dlines = []
    for line in getattr(phase, "DiffLines", []):
        dlines.append(
            {
                "dsp": getattr(line, "dsp", 0.0),
                "dsp0": getattr(line, "dsp0", 0.0),
                "intensity": getattr(line, "intensity", 0.0),
                "h": getattr(line, "h", 0),
                "k": getattr(line, "k", 0),
                "l": getattr(line, "l", 0),
            }
        )
    return {
        "file": _relpath_or_abs(getattr(phase, "file", None), chi_root),
        "name": getattr(phase, "name", ""),
        "version": getattr(phase, "version", 0),
        "comments": getattr(phase, "comments", ""),
        "symmetry": getattr(phase, "symmetry", ""),
        "k0": getattr(phase, "k0", 0.0),
        "k0p": getattr(phase, "k0p", 0.0),
        "thermal_expansion": getattr(phase, "thermal_expansion", 0.0),
        "a0": getattr(phase, "a0", 0.0),
        "b0": getattr(phase, "b0", 0.0),
        "c0": getattr(phase, "c0", 0.0),
        "alpha0": getattr(phase, "alpha0", 0.0),
        "beta0": getattr(phase, "beta0", 0.0),
        "gamma0": getattr(phase, "gamma0", 0.0),
        "v0": getattr(phase, "v0", 0.0),
        "a": getattr(phase, "a", 0.0),
        "b": getattr(phase, "b", 0.0),
        "c": getattr(phase, "c", 0.0),
        "alpha": getattr(phase, "alpha", 0.0),
        "beta": getattr(phase, "beta", 0.0),
        "gamma": getattr(phase, "gamma", 0.0),
        "v": getattr(phase, "v", 0.0),
        "color": getattr(phase, "color", ""),
        "display": getattr(phase, "display", True),
        "maxint": getattr(phase, "maxint", 1.0),
        "twk_b_a": getattr(phase, "twk_b_a", 1.0),
        "twk_c_a": getattr(phase, "twk_c_a", 1.0),
        "twk_v0": getattr(phase, "twk_v0", 1.0),
        "twk_k0": getattr(phase, "twk_k0", 1.0),
        "twk_k0p": getattr(phase, "twk_k0p", 1.0),
        "twk_thermal_expansion": getattr(phase, "twk_thermal_expansion", 1.0),
        "twk_int": getattr(phase, "twk_int", 1.0),
        "k0_org": getattr(phase, "k0_org", None),
        "k0p_org": getattr(phase, "k0p_org", None),
        "v0_org": getattr(phase, "v0_org", None),
        "thermal_expansion_org": getattr(phase, "thermal_expansion_org", None),
        "DiffLines": dlines,
    }


def _load_jcpds_item(payload, chi_root):
    phase = JCPDSplt()
    for k, v in payload.items():
        if k == "DiffLines":
            continue
        if k == "file":
            setattr(phase, k, _resolve_path(v, chi_root))
        else:
            setattr(phase, k, v)
    dlines = []
    for row in payload.get("DiffLines", []):
        line = DiffractionLine()
        line.dsp0 = row.get("dsp0", 0.0)
        line.dsp = row.get("dsp", 0.0)
        line.intensity = row.get("intensity", 0.0)
        line.h = row.get("h", 0)
        line.k = row.get("k", 0)
        line.l = row.get("l", 0)
        dlines.append(line)
    phase.DiffLines = dlines
    if getattr(phase, "k0_org", None) is None:
        phase.k0_org = getattr(phase, "k0", 0.0)
    if getattr(phase, "k0p_org", None) is None:
        phase.k0p_org = getattr(phase, "k0p", 0.0)
    if getattr(phase, "v0_org", None) is None:
        phase.v0_org = getattr(phase, "v0", 0.0)
    if getattr(phase, "thermal_expansion_org", None) is None:
        phase.thermal_expansion_org = getattr(phase, "thermal_expansion", 0.0)
    return phase


def _fit_result_to_dict(section):
    fit = getattr(section, "fit_result", None)
    if fit is None:
        return None
    out = {
        "chisqr": getattr(fit, "chisqr", None),
        "redchi": getattr(fit, "redchi", None),
        "aic": getattr(fit, "aic", None),
        "bic": getattr(fit, "bic", None),
        "params": {},
        "best_fit": None,
        "components": {},
    }
    params = getattr(fit, "params", {}) or {}
    for key, prm in params.items():
        out["params"][key] = {
            "value": getattr(prm, "value", None),
            "stderr": getattr(prm, "stderr", None),
            "vary": getattr(prm, "vary", True),
        }
    best_fit = getattr(fit, "best_fit", None)
    if best_fit is not None:
        out["best_fit"] = np.asarray(best_fit).tolist()
    try:
        comps = fit.eval_components(x=section.x)
        out["components"] = {k: np.asarray(v).tolist() for k, v in comps.items()}
    except Exception:
        out["components"] = {}
    return out


def _sanitize_name(name):
    return re.sub(r"[^A-Za-z0-9_.-]", "_", str(name))


def _trim_trailing_nan(arr):
    arr = np.asarray(arr, dtype=float).reshape(-1)
    if arr.size == 0:
        return arr
    valid = np.where(~np.isnan(arr))[0]
    if valid.size == 0:
        return np.asarray([], dtype=float)
    return arr[: valid[-1] + 1]


def _component_sort_key(name):
    key = str(name).strip().lower()
    m = re.fullmatch(r"p(\d+)", key)
    if m is not None:
        return (0, int(m.group(1)))
    if key == "b":
        return (2, 0)
    return (1, key)


def _compute_section_csv_payload(columns):
    if not columns:
        return b""
    col_names = [name for name, _ in columns]
    n_rows = max(np.asarray(values, dtype=float).reshape(-1).size for _, values in columns)
    matrix = np.full((n_rows, len(columns)), np.nan, dtype=float)
    for idx, (_, values) in enumerate(columns):
        vals = np.asarray(values, dtype=float).reshape(-1)
        matrix[:vals.size, idx] = vals
    buf = io.StringIO()
    np.savetxt(
        buf,
        matrix,
        fmt="%.18g",
        delimiter=",",
        header=",".join(col_names),
        comments="",
    )
    return buf.getvalue().encode("utf-8")


def _load_section_csv_columns(path):
    try:
        if (path is None) or (not os.path.exists(path)):
            return {}
        data = np.genfromtxt(path, delimiter=",", names=True, dtype=float, encoding="utf-8")
        if data is None:
            return {}
        names = getattr(getattr(data, "dtype", None), "names", None)
        if not names:
            return {}
        out = {}
        for name in names:
            col = data[name]
            arr = np.asarray([float(col)], dtype=float) if np.isscalar(col) else np.asarray(col, dtype=float)
            out[name] = _trim_trailing_nan(arr)
        return out
    except Exception:
        return {}


def _load_csv_array_legacy(path):
    try:
        if (path is None) or (not os.path.exists(path)):
            return np.asarray([], dtype=float)
        with open(path, "r", encoding="utf-8") as f:
            text = f.read().strip()
        if text == "":
            return np.asarray([], dtype=float)
        return np.loadtxt(io.StringIO(text), delimiter=",", dtype=float, ndmin=1)
    except Exception:
        return np.asarray([], dtype=float)


def _fit_result_to_dict_with_csv(section):
    fit = getattr(section, "fit_result", None)
    if fit is None:
        return None
    out = {
        "chisqr": getattr(fit, "chisqr", None),
        "redchi": getattr(fit, "redchi", None),
        "aic": getattr(fit, "aic", None),
        "bic": getattr(fit, "bic", None),
        "params": {},
        "best_fit_column": None,
        "component_columns": {},
    }
    params = getattr(fit, "params", {}) or {}
    for key, prm in params.items():
        out["params"][key] = {
            "value": getattr(prm, "value", None),
            "stderr": getattr(prm, "stderr", None),
            "vary": getattr(prm, "vary", True),
        }
    return out


def _section_to_dict(section, section_tag, section_payloads):
    columns = []
    if section.x is not None:
        columns.append(("x", section.x))
    if section.y_bgsub is not None:
        columns.append(("y_bgsub", section.y_bgsub))
    if section.y_bg is not None:
        columns.append(("y_bg", section.y_bg))

    fit_payload = _fit_result_to_dict_with_csv(section)
    fit = getattr(section, "fit_result", None)
    if fit is not None:
        best_fit = getattr(fit, "best_fit", None)
        if best_fit is not None:
            columns.append(("fit_best", best_fit))
            fit_payload["best_fit_column"] = "fit_best"
        try:
            comps = fit.eval_components(x=section.x) or {}
        except Exception:
            comps = {}
        for comp_name in sorted(comps.keys(), key=_component_sort_key):
            col_name = f"comp_{_sanitize_name(comp_name)}"
            columns.append((col_name, comps[comp_name]))
            fit_payload["component_columns"][comp_name] = col_name

    section_csv_file = None
    section_csv_columns = [name for name, _ in columns]
    if columns:
        section_csv_file = os.path.join("sections", f"{section_tag}.csv")
        section_payloads[section_csv_file] = _compute_section_csv_payload(columns)

    return {
        "section_csv_file": section_csv_file,
        "section_csv_columns": section_csv_columns,
        "timestamp": section.timestamp,
        "baseline_in_queue": section.baseline_in_queue,
        "peaks_in_queue": section.peaks_in_queue,
        "peakinfo": section.peakinfo,
        "fit_result": fit_payload,
    }


def _dict_to_section(payload, param_dir, missing_files=None):
    section = Section()
    section_cols = {}
    section_csv_file = payload.get("section_csv_file")
    if section_csv_file is not None:
        full_csv = os.path.join(param_dir, section_csv_file)
        section_cols = _load_section_csv_columns(full_csv)
        if (section_cols == {}) and (not os.path.exists(full_csv)) and (missing_files is not None):
            missing_files.append(section_csv_file)

    if "x" in section_cols:
        section.x = section_cols.get("x")
    else:
        x_file = payload.get("x_file")
        if x_file is not None:
            section.x = _load_csv_array_legacy(os.path.join(param_dir, x_file))
        else:
            section.x = None if payload.get("x") is None else np.asarray(payload.get("x"), dtype=float)

    if "y_bgsub" in section_cols:
        section.y_bgsub = section_cols.get("y_bgsub")
    else:
        y_bgsub_file = payload.get("y_bgsub_file")
        if y_bgsub_file is not None:
            section.y_bgsub = _load_csv_array_legacy(os.path.join(param_dir, y_bgsub_file))
        else:
            section.y_bgsub = None if payload.get("y_bgsub") is None else np.asarray(payload.get("y_bgsub"), dtype=float)

    if "y_bg" in section_cols:
        section.y_bg = section_cols.get("y_bg")
    else:
        y_bg_file = payload.get("y_bg_file")
        if y_bg_file is not None:
            section.y_bg = _load_csv_array_legacy(os.path.join(param_dir, y_bg_file))
        else:
            section.y_bg = None if payload.get("y_bg") is None else np.asarray(payload.get("y_bg"), dtype=float)
    section.timestamp = payload.get("timestamp")
    section.baseline_in_queue = payload.get("baseline_in_queue", [])
    section.peaks_in_queue = payload.get("peaks_in_queue", [])
    section.peakinfo = payload.get("peakinfo", {})
    fit_payload = payload.get("fit_result")
    if isinstance(fit_payload, dict):
        best_col = fit_payload.get("best_fit_column", "fit_best")
        if best_col in section_cols:
            fit_payload["best_fit"] = np.asarray(section_cols.get(best_col), dtype=float).tolist()
        else:
            best_fit_file = fit_payload.get("best_fit_file")
            if best_fit_file is not None:
                old_arr = _load_csv_array_legacy(os.path.join(param_dir, best_fit_file))
                fit_payload["best_fit"] = np.asarray(old_arr, dtype=float).tolist()

        comps = {}
        comp_cols = fit_payload.get("component_columns", {})
        if isinstance(comp_cols, dict) and comp_cols:
            for comp_name, col_name in comp_cols.items():
                if col_name in section_cols:
                    comps[comp_name] = np.asarray(section_cols.get(col_name), dtype=float).tolist()
        elif section_cols:
            for col_name, values in section_cols.items():
                if col_name.startswith("comp_"):
                    comps[col_name[5:]] = np.asarray(values, dtype=float).tolist()
        else:
            comp_files = fit_payload.get("components_files", {})
            if isinstance(comp_files, dict) and comp_files:
                for k, rel in comp_files.items():
                    old_arr = _load_csv_array_legacy(os.path.join(param_dir, rel))
                    comps[k] = np.asarray(old_arr, dtype=float).tolist()
        if comps:
            fit_payload["components"] = comps
    section.fit_result = None if fit_payload is None else _FitResultLite(fit_payload)
    section.parameters = None
    section.fit_model = None
    return section


def _compute_np_payload(arr):
    buf = io.BytesIO()
    np.save(buf, arr)
    return buf.getvalue()


def _get_backup_index(path):
    if not os.path.exists(path):
        return {"format_family": FORMAT_FAMILY, "events": []}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            if not isinstance(data, dict):
                return {"format_family": FORMAT_FAMILY, "events": []}
            if "events" not in data or not isinstance(data.get("events"), list):
                data["events"] = []
            if "format_family" not in data:
                data["format_family"] = FORMAT_FAMILY
            return data
    except Exception:
        return {"format_family": FORMAT_FAMILY, "events": []}



def _make_backup_id(param_dir):
    index_path = os.path.join(param_dir, BACKUP_INDEX_FILE)
    index = _get_backup_index(index_path)
    used = set()
    for evt in index.get("events", []):
        bid = evt.get("id")
        if bid is None:
            continue
        try:
            used.add(int(str(bid)))
        except Exception:
            continue
    backups_dir = os.path.join(param_dir, "backups")
    if os.path.isdir(backups_dir):
        for name in os.listdir(backups_dir):
            try:
                used.add(int(str(name)))
            except Exception:
                continue
    next_id = 0 if not used else (max(used) + 1)
    while next_id in used:
        next_id += 1
    return str(next_id)


def _collect_companion_files(param_dir):
    """
    Track legacy/session companion files in PARAM so their changes are included
    in backup snapshots as well.
    """
    patterns = [
        "*.poni",
        "*.cake.npy",
        "*.bg.chi",
        "*.bgsub.chi",
        "*.cakeformat",
    ]
    rel_files = set()
    for pat in patterns:
        for full in glob.glob(os.path.join(param_dir, pat)):
            if os.path.isfile(full):
                rel_files.add(os.path.basename(full))
    return sorted(rel_files)


def _prepare_payloads(model, param_dir, ui_state=None):
    chi_root = model.chi_path
    cake_tth_file = None
    cake_azi_file = None
    cake_int_file = None
    mask_file = None
    if model.diff_img is not None:
        if model.diff_img.img_filename is not None:
            base = os.path.splitext(os.path.basename(model.diff_img.img_filename))[0]
        else:
            base = "cake"
        # Keep historical naming style used by write_temp_cakefiles.
        cake_tth_file = f"{base}.tth.cake.npy" if model.diff_img.tth_cake is not None else None
        cake_azi_file = f"{base}.azi.cake.npy" if model.diff_img.chi_cake is not None else None
        cake_int_file = f"{base}.int.cake.npy" if model.diff_img.intensity_cake is not None else None
        mask_file = f"{base}.mask.npy" if model.diff_img.mask is not None else None

    waterfall_payloads = {}
    waterfall_patterns = []
    for i, ptn in enumerate(model.waterfall_ptn):
        fallback_rel = None
        src = getattr(ptn, "_pkpo_original_fname", None) or getattr(ptn, "fname", None)
        if (src is not None) and os.path.exists(src):
            rel = os.path.join("waterfall", f"{i:04d}_{os.path.basename(src)}")
            try:
                waterfall_payloads[rel] = _file_bytes(src)
                fallback_rel = rel
            except Exception:
                fallback_rel = None
        waterfall_patterns.append(
            _serialize_pattern(
                ptn,
                chi_root,
                fallback_relpath=fallback_rel,
                force_abs_fname=True,
            )
        )

    session_data = {
        "schema": 1,
        "chi_path": ".",
        "jcpds_path": _relpath_or_abs(model.jcpds_path, chi_root),
        "poni": _relpath_or_abs(model.poni, chi_root),
        "base_pattern": _serialize_pattern(model.base_ptn, chi_root),
        "waterfall_patterns": waterfall_patterns,
        "diff_img": {
            "img_filename": _relpath_or_abs(getattr(model.diff_img, "img_filename", None), chi_root),
            "mask_file": mask_file,
            "cake_tth_file": cake_tth_file,
            "cake_azi_file": cake_azi_file,
            "cake_int_file": cake_int_file,
        },
        "current_section_index": None,
    }

    if model.current_section is not None:
        for i, sec in enumerate(model.section_lst):
            if sec.timestamp == model.current_section.timestamp:
                session_data["current_section_index"] = i
                break

    section_payloads = {}
    sections_data = {
        "schema": 1,
        "sections": [
            _section_to_dict(s, section_tag=f"sec_{i:04d}", section_payloads=section_payloads)
            for i, s in enumerate(model.section_lst)
        ],
        # Preserve in-progress/unsaved fit-section edits as part of state.
        "current_section": (
            _section_to_dict(
                model.current_section,
                section_tag="current_section",
                section_payloads=section_payloads,
            )
            if model.current_section is not None else None
        ),
    }
    jcpds_data = {
        "schema": 1,
        "saved_pressure": model.saved_pressure,
        "saved_temperature": model.saved_temperature,
        "phases": [_serialize_jcpds_item(j, chi_root) for j in model.jcpds_lst],
    }
    ui_data = {
        "schema": 1,
        "ui_state": ui_state or {},
    }
    return session_data, sections_data, jcpds_data, ui_data, section_payloads, waterfall_payloads


def _highlight_changed_files(changed_files):
    highlights = []
    if JCPDS_FILE in changed_files:
        highlights.append("JCPDS")
    if SECTIONS_FILE in changed_files:
        highlights.append("Fits")
    if SESSION_FILE in changed_files:
        highlights.append("Session")
    if UI_STATE_FILE in changed_files:
        highlights.append("UI")
    if not highlights and changed_files:
        highlights.append("Files")
    return highlights


def _safe_load_json(path):
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def _semantic_change_flags(param_dir, session_data, sections_data, jcpds_data, ui_data):
    old_session = _safe_load_json(os.path.join(param_dir, SESSION_FILE))
    old_sections = _safe_load_json(os.path.join(param_dir, SECTIONS_FILE))
    old_jcpds = _safe_load_json(os.path.join(param_dir, JCPDS_FILE))
    old_ui = _safe_load_json(os.path.join(param_dir, UI_STATE_FILE))

    # Fits significance: compare only saved sections list, not current_section.
    old_sections_list = [] if old_sections is None else old_sections.get("sections", [])
    new_sections_list = sections_data.get("sections", [])
    # JCPDS significance with backward compatibility.
    old_phases = []
    if old_jcpds is not None:
        old_phases = old_jcpds.get("phases", old_jcpds.get("items", []))
    new_phases = jcpds_data.get("phases", [])

    return {
        "session": (old_session != session_data),
        "fits": (old_sections_list != new_sections_list),
        "jcpds": (old_phases != new_phases),
        "ui": (old_ui != ui_data),
    }


def _highlights_from_flags(flags, force_backup=False):
    highlights = []
    if flags.get("jcpds", False):
        highlights.append("JCPDS")
    if flags.get("fits", False):
        highlights.append("Fits")
    if flags.get("session", False):
        highlights.append("Session")
    if flags.get("ui", False):
        highlights.append("UI")
    if not highlights and force_backup:
        highlights.append("Snapshot")
    elif not highlights:
        highlights.append("none")
    return highlights


def _compute_state_hash(payload_map):
    h = hashlib.sha256()
    for rel_path in sorted(payload_map.keys()):
        h.update(rel_path.encode("utf-8"))
        h.update(b"\0")
        h.update(hashlib.sha256(payload_map[rel_path]).digest())
        h.update(b"\0")
    return h.hexdigest()


def _known_state_hashes(index):
    hashes = set()
    for ev in index.get("events", []):
        state_hash = ev.get("state_hash")
        if isinstance(state_hash, str) and state_hash != "":
            hashes.add(state_hash)
    return hashes


def _exclude_from_backup(rel_path):
    rp = str(rel_path).lower()
    return rp.endswith(".chi") or rp.endswith(".npy")


def save_model_to_param(
        model, ui_state=None, reason="manual-save",
        force_backup=False, create_backup=True):
    if model is None or (not model.base_ptn_exist()):
        raise ValueError("Base pattern must exist before saving PARAM session.")
    param_dir = get_temp_dir(model.get_base_ptn_filename(), branch="-param")
    os.makedirs(param_dir, exist_ok=True)

    session_data, sections_data, jcpds_data, ui_data, section_payloads, waterfall_payloads = _prepare_payloads(
        model, param_dir=param_dir, ui_state=ui_state)
    existing_created_at = None
    existing_manifest_path = os.path.join(param_dir, MANIFEST_FILE)
    if os.path.exists(existing_manifest_path):
        try:
            existing_manifest = _load_json(existing_manifest_path)
            existing_created_at = existing_manifest.get("created_at")
        except Exception:
            existing_created_at = None

    manifest = {
        "format_family": FORMAT_FAMILY,
        "format_version": FORMAT_VERSION,
        # Keep created_at stable across saves so no-op saves do not look changed.
        "created_at": existing_created_at or datetime.datetime.now().isoformat(timespec="seconds"),
        "files": {
            "session": SESSION_FILE,
            "sections": SECTIONS_FILE,
            "jcpds": JCPDS_FILE,
            "ui_state": UI_STATE_FILE,
            "backup_index": BACKUP_INDEX_FILE,
        },
    }

    payload_map = {
        SESSION_FILE: json.dumps(session_data, indent=2, sort_keys=True, default=_json_default).encode("utf-8"),
        SECTIONS_FILE: json.dumps(sections_data, indent=2, sort_keys=True, default=_json_default).encode("utf-8"),
        # Keep insertion order for readability:
        # phase fields first, DiffLines after; and h/k/l grouped in each line.
        JCPDS_FILE: json.dumps(jcpds_data, indent=2, sort_keys=False, default=_json_default).encode("utf-8"),
        UI_STATE_FILE: json.dumps(ui_data, indent=2, sort_keys=True, default=_json_default).encode("utf-8"),
        MANIFEST_FILE: json.dumps(manifest, indent=2, sort_keys=True, default=_json_default).encode("utf-8"),
    }
    payload_map.update(section_payloads)
    payload_map.update(waterfall_payloads)

    # Keep background information as chi files in PARAM.
    if model.base_ptn is not None:
        try:
            model.base_ptn.write_temporary_bgfiles(temp_dir=param_dir)
        except Exception:
            pass
    if model.waterfall_ptn:
        for ptn in model.waterfall_ptn:
            try:
                ptn.write_temporary_bgfiles(temp_dir=param_dir)
            except Exception:
                pass

    # Keep cake naming/style consistent with existing temp npy files.
    if model.diff_img is not None:
        if model.diff_img.tth_cake is not None and model.diff_img.chi_cake is not None and model.diff_img.intensity_cake is not None:
            try:
                model.diff_img.write_temp_cakefiles(temp_dir=param_dir)
            except Exception:
                pass
        diff_info = session_data.get("diff_img", {})
        for key in ("cake_tth_file", "cake_azi_file", "cake_int_file"):
            rel = diff_info.get(key)
            if rel is None:
                continue
            full = os.path.join(param_dir, rel)
            if os.path.exists(full):
                payload_map[rel] = _file_bytes(full)
        if model.diff_img.mask is not None:
            rel = diff_info.get("mask_file")
            if rel is not None:
                payload_map[rel] = _compute_np_payload(model.diff_img.mask)

    # Add BG chi files to tracked payload so they can be backed up/restored.
    for ptn in [model.base_ptn] + list(model.waterfall_ptn):
        if ptn is None:
            continue
        bgsub_name, bg_name = _bg_temp_names(ptn)
        for rel in (bgsub_name, bg_name):
            full = os.path.join(param_dir, rel)
            if os.path.exists(full):
                payload_map[rel] = _file_bytes(full)

    # Include companion files (e.g., poni/cakeformat/cake npy/bg chi) in
    # change detection + backups, preserving historical PARAM usage.
    for rel in _collect_companion_files(param_dir):
        full = os.path.join(param_dir, rel)
        if os.path.exists(full):
            payload_map[rel] = _file_bytes(full)

    changed_files_all = []
    for rel_path, new_bytes in payload_map.items():
        full_path = os.path.join(param_dir, rel_path)
        old_bytes = _file_bytes(full_path) if os.path.exists(full_path) else None
        if old_bytes != new_bytes:
            changed_files_all.append(rel_path)

    backup_payload_map = {
        rel_path: payload
        for rel_path, payload in payload_map.items()
        if not _exclude_from_backup(rel_path)
    }
    changed_files = [p for p in changed_files_all if p in backup_payload_map]
    delta_files = list(changed_files)
    semantic_flags = _semantic_change_flags(
        param_dir, session_data, sections_data, jcpds_data, ui_data)
    state_hash = _compute_state_hash(backup_payload_map)

    backup_id = None
    backup_root = None
    index_path = os.path.join(param_dir, BACKUP_INDEX_FILE)
    index = _get_backup_index(index_path)
    known_hashes = _known_state_hashes(index)
    state_already_known = state_hash in known_hashes

    create_backup_event = create_backup and ((changed_files != []) or force_backup)
    if create_backup_event and state_already_known and (not force_backup):
        # Avoid duplicate backups for states that already exist in history.
        create_backup_event = False

    if create_backup_event:
        # Store full post-save snapshot so each backup row maps 1:1 to
        # what gets restored (avoids pre/post mismatch confusion).
        snapshot_files = sorted(backup_payload_map.keys())
        backup_id = _make_backup_id(param_dir)
        backup_root = os.path.join(param_dir, "backups", backup_id)
        for rel_path in snapshot_files:
            dst = os.path.join(backup_root, rel_path)
            _atomic_write_bytes(dst, backup_payload_map[rel_path])

    for rel_path, payload in payload_map.items():
        _atomic_write_bytes(os.path.join(param_dir, rel_path), payload)

    if create_backup_event:
        highlights = _highlights_from_flags(semantic_flags, force_backup=force_backup)
        index["events"].append(
            {
                "id": backup_id,
                "timestamp": datetime.datetime.now().isoformat(timespec="seconds"),
                "reason": reason,
                "changed_files": delta_files,
                "snapshot_files": snapshot_files,
                "snapshot_mode": "full",
                "highlights": highlights,
                "state_hash": state_hash,
            }
        )
    _atomic_write_json(index_path, index)

    return SaveResult(
        param_dir=param_dir,
        manifest_path=os.path.join(param_dir, MANIFEST_FILE),
        backup_id=backup_id,
        changed_files=changed_files_all,
    )


def _load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def is_new_param_folder(param_dir):
    manifest = os.path.join(param_dir, MANIFEST_FILE)
    if not os.path.exists(manifest):
        return False
    try:
        data = _load_json(manifest)
    except Exception:
        return False
    return data.get("format_family") == FORMAT_FAMILY


def list_backup_events(param_dir):
    index_path = os.path.join(param_dir, BACKUP_INDEX_FILE)
    index = _get_backup_index(index_path)
    return index.get("events", [])


def restore_to_backup_event(param_dir, event_id=None, event_index=None):
    events = list_backup_events(param_dir)
    if not events:
        return False
    if event_index is not None:
        if (event_index < 0) or (event_index >= len(events)):
            return False
        target_pos = int(event_index)
    else:
        ids = [e.get("id") for e in events]
        if event_id not in ids:
            return False
        # If duplicate ids exist in legacy index files, prefer the latest
        # matching one for deterministic behavior.
        target_pos = max(i for i, _id in enumerate(ids) if _id == event_id)

    target_evt = events[target_pos]
    target_mode = target_evt.get("snapshot_mode", "")
    if target_mode == "full":
        snap_dir = os.path.join(param_dir, "backups", target_evt.get("id", ""))
        rel_files = target_evt.get("snapshot_files", [])
        for rel_path in rel_files:
            src = os.path.join(snap_dir, rel_path)
            dst = os.path.join(param_dir, rel_path)
            if os.path.exists(src):
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                shutil.copy2(src, dst)
        return True

    # Legacy fallback for older pre/post mixed snapshots.
    for i in range(len(events) - 1, target_pos - 1, -1):
        evt = events[i]
        snap_dir = os.path.join(param_dir, "backups", evt.get("id", ""))
        rel_files = evt.get("snapshot_files")
        if not isinstance(rel_files, list):
            rel_files = evt.get("changed_files", [])
        for rel_path in rel_files:
            src = os.path.join(snap_dir, rel_path)
            dst = os.path.join(param_dir, rel_path)
            if os.path.exists(src):
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                shutil.copy2(src, dst)
    return True


def load_model_from_param(model, base_chi_file, backup_event_id=None, backup_event_index=None):
    chi_root = os.path.dirname(base_chi_file)
    param_dir = get_temp_dir(base_chi_file, branch="-param")
    if not is_new_param_folder(param_dir):
        return False, {"reason": "missing-or-invalid-manifest", "param_dir": param_dir}

    if (backup_event_id is not None) or (backup_event_index is not None):
        ok = restore_to_backup_event(
            param_dir,
            event_id=backup_event_id,
            event_index=backup_event_index,
        )
        if not ok:
            return False, {
                "reason": "invalid-backup-id",
                "param_dir": param_dir,
                "backup_id": backup_event_id,
                "backup_index": backup_event_index,
            }

    manifest = _load_json(os.path.join(param_dir, MANIFEST_FILE))
    files = manifest.get("files", {})
    session_data = _load_json(os.path.join(param_dir, files.get("session", SESSION_FILE)))
    sections_data = _load_json(os.path.join(param_dir, files.get("sections", SECTIONS_FILE)))
    jcpds_data = _load_json(os.path.join(param_dir, files.get("jcpds", JCPDS_FILE)))
    ui_data = _load_json(os.path.join(param_dir, files.get("ui_state", UI_STATE_FILE)))

    model.base_ptn = _load_pattern(session_data.get("base_pattern"), chi_root, param_dir)
    model.waterfall_ptn = [
        _load_pattern(p, chi_root, param_dir)
        for p in session_data.get("waterfall_patterns", [])
    ]
    fallback_waterfall = []
    for ptn in model.waterfall_ptn:
        if bool(getattr(ptn, "_pkpo_fallback_in_use", False)):
            fallback_waterfall.append(
                os.path.basename(
                    getattr(ptn, "_pkpo_original_fname", None) or getattr(ptn, "fname", "") or ""
                )
            )
    phase_payloads = jcpds_data.get("phases", jcpds_data.get("items", []))
    model.jcpds_lst = [_load_jcpds_item(p, chi_root) for p in phase_payloads]
    missing_section_csv_files = []
    loaded_sections = []
    old_to_new_idx = {}
    for old_idx, sec_payload in enumerate(sections_data.get("sections", [])):
        sec_obj = _dict_to_section(sec_payload, param_dir, missing_files=missing_section_csv_files)
        x_arr = getattr(sec_obj, "x", None)
        if (x_arr is None) or (len(x_arr) == 0):
            continue
        old_to_new_idx[old_idx] = len(loaded_sections)
        loaded_sections.append(sec_obj)
    model.section_lst = loaded_sections

    current_idx = session_data.get("current_section_index")
    current_payload = sections_data.get("current_section")
    model.current_section = None
    if current_payload is not None:
        current_section = _dict_to_section(
            current_payload, param_dir, missing_files=missing_section_csv_files)
        if (getattr(current_section, "x", None) is None) or (len(current_section.x) == 0):
            current_section = None
        mapped_idx = old_to_new_idx.get(current_idx) if isinstance(current_idx, int) else None
        if (current_section is not None) and isinstance(mapped_idx, int) and (0 <= mapped_idx < len(model.section_lst)):
            listed = model.section_lst[mapped_idx]
            if getattr(listed, "timestamp", None) == getattr(current_section, "timestamp", None):
                model.current_section = listed
            else:
                model.current_section = current_section
        else:
            model.current_section = current_section
    elif isinstance(current_idx, int):
        mapped_idx = old_to_new_idx.get(current_idx)
        if isinstance(mapped_idx, int) and (0 <= mapped_idx < len(model.section_lst)):
            model.current_section = model.section_lst[mapped_idx]

    model.saved_pressure = jcpds_data.get(
        "saved_pressure", session_data.get("saved_pressure", model.saved_pressure))
    model.saved_temperature = jcpds_data.get(
        "saved_temperature", session_data.get("saved_temperature", model.saved_temperature))
    model.chi_path = chi_root
    model.jcpds_path = _resolve_path(session_data.get("jcpds_path"), chi_root) or ""
    model.poni = _resolve_path(session_data.get("poni"), chi_root)

    diff_img_info = session_data.get("diff_img", {})
    img_filename = _resolve_path(diff_img_info.get("img_filename"), chi_root)
    has_any = any(
        diff_img_info.get(k) is not None
        for k in ("mask_file", "cake_tth_file", "cake_azi_file", "cake_int_file")
    ) or (img_filename is not None)
    if has_any:
        diff = DiffImg()
        diff.img_filename = img_filename
        mask_file = diff_img_info.get("mask_file")
        cake_tth_file = diff_img_info.get("cake_tth_file")
        cake_azi_file = diff_img_info.get("cake_azi_file")
        cake_int_file = diff_img_info.get("cake_int_file")
        if mask_file is not None:
            f = os.path.join(param_dir, mask_file)
            if os.path.exists(f):
                diff.mask = np.load(f, allow_pickle=False)
        if cake_tth_file is not None:
            f = os.path.join(param_dir, cake_tth_file)
            if os.path.exists(f):
                diff.tth_cake = np.load(f, allow_pickle=False)
        if cake_azi_file is not None:
            f = os.path.join(param_dir, cake_azi_file)
            if os.path.exists(f):
                diff.chi_cake = np.load(f, allow_pickle=False)
        if cake_int_file is not None:
            f = os.path.join(param_dir, cake_int_file)
            if os.path.exists(f):
                diff.intensity_cake = np.load(f, allow_pickle=False)
        model.diff_img = diff
    else:
        model.diff_img = None

    return True, {
        "param_dir": param_dir,
        "manifest": os.path.join(param_dir, MANIFEST_FILE),
        "ui_state": ui_data.get("ui_state", {}),
        "missing_section_csv_files": sorted(set(missing_section_csv_files)),
        "fallback_waterfall_files": sorted(set([x for x in fallback_waterfall if x])),
        "category_presence": {
            "backup_information": (len(list_backup_events(param_dir)) > 0),
            "jcpds": (len(phase_payloads) > 0),
            "pressure": (("saved_pressure" in jcpds_data) or ("saved_pressure" in session_data)),
            "temperature": (("saved_temperature" in jcpds_data) or ("saved_temperature" in session_data)),
            "cake_z_scale": (ui_data.get("ui_state", {}).get("cake", {}) != {}),
            "background": (ui_data.get("ui_state", {}).get("background", {}) != {}),
            "waterfall_list": (len(session_data.get("waterfall_patterns", [])) > 0),
            "poni": (session_data.get("poni") not in (None, "")),
            "fits_information": (
                (len(sections_data.get("sections", [])) > 0) or
                (sections_data.get("current_section") is not None)
            ),
        },
    }


def load_section_from_param(base_chi_file, section_index):
    """
    Load one saved section by index from PARAM session files.
    Returns Section object on success, or None if unavailable/invalid.
    """
    if base_chi_file is None:
        return None
    param_dir = get_temp_dir(base_chi_file, branch="-param")
    if not is_new_param_folder(param_dir):
        return None
    try:
        manifest = _load_json(os.path.join(param_dir, MANIFEST_FILE))
        files = manifest.get("files", {})
        sections_data = _load_json(os.path.join(param_dir, files.get("sections", SECTIONS_FILE)))
        sections = sections_data.get("sections", [])
        idx = int(section_index)
        if (idx < 0) or (idx >= len(sections)):
            return None
        return _dict_to_section(sections[idx], param_dir)
    except Exception:
        return None
