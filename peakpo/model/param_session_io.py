import json
import os
import shutil
import tempfile
import datetime
import io
import glob
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
BACKUP_KEEP_LAST = 20


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


def _serialize_pattern(pattern, chi_root):
    if pattern is None:
        return None
    bgsub_name, bg_name = _bg_temp_names(pattern)
    return {
        "fname": _relpath_or_abs(getattr(pattern, "fname", None), chi_root),
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
    fname = _resolve_path(payload.get("fname"), chi_root)
    if fname and os.path.exists(fname):
        ptn.read_file(fname)
    else:
        ptn.fname = fname
        ptn.x_raw = None
        ptn.y_raw = None
    ptn.wavelength = payload.get("wavelength", 0.3344)
    ptn.color = payload.get("color", "white")
    ptn.display = payload.get("display", False)
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


def _section_to_dict(section):
    return {
        "x": None if section.x is None else np.asarray(section.x).tolist(),
        "y_bgsub": None if section.y_bgsub is None else np.asarray(section.y_bgsub).tolist(),
        "y_bg": None if section.y_bg is None else np.asarray(section.y_bg).tolist(),
        "timestamp": section.timestamp,
        "baseline_in_queue": section.baseline_in_queue,
        "peaks_in_queue": section.peaks_in_queue,
        "peakinfo": section.peakinfo,
        "fit_result": _fit_result_to_dict(section),
    }


def _dict_to_section(payload):
    section = Section()
    section.x = None if payload.get("x") is None else np.asarray(payload.get("x"), dtype=float)
    section.y_bgsub = None if payload.get("y_bgsub") is None else np.asarray(payload.get("y_bgsub"), dtype=float)
    section.y_bg = None if payload.get("y_bg") is None else np.asarray(payload.get("y_bg"), dtype=float)
    section.timestamp = payload.get("timestamp")
    section.baseline_in_queue = payload.get("baseline_in_queue", [])
    section.peaks_in_queue = payload.get("peaks_in_queue", [])
    section.peakinfo = payload.get("peakinfo", {})
    fit_payload = payload.get("fit_result")
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


def _prune_backup_events(param_dir, index, keep_last=BACKUP_KEEP_LAST):
    events = index.get("events", [])
    if len(events) <= keep_last:
        return index
    to_remove = events[:-keep_last]
    to_keep = events[-keep_last:]
    for evt in to_remove:
        backup_id = evt.get("id")
        if not backup_id:
            continue
        snap_dir = os.path.join(param_dir, "backups", backup_id)
        if os.path.isdir(snap_dir):
            shutil.rmtree(snap_dir, ignore_errors=True)
    index["events"] = to_keep
    return index
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"format_family": FORMAT_FAMILY, "events": []}


def _make_backup_id():
    # Include microseconds to avoid collisions when multiple saves happen
    # within the same second (e.g., pre-restore backup + restore load).
    return datetime.datetime.now().strftime("%Y%m%d-%H%M%S-%f")


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


def _prepare_payloads(model, ui_state=None):
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

    session_data = {
        "schema": 1,
        "saved_pressure": model.saved_pressure,
        "saved_temperature": model.saved_temperature,
        "chi_path": ".",
        "jcpds_path": _relpath_or_abs(model.jcpds_path, chi_root),
        "poni": _relpath_or_abs(model.poni, chi_root),
        "base_pattern": _serialize_pattern(model.base_ptn, chi_root),
        "waterfall_patterns": [_serialize_pattern(p, chi_root) for p in model.waterfall_ptn],
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

    sections_data = {
        "schema": 1,
        "sections": [_section_to_dict(s) for s in model.section_lst],
    }
    jcpds_data = {
        "schema": 1,
        "phases": [_serialize_jcpds_item(j, chi_root) for j in model.jcpds_lst],
    }
    ui_data = {
        "schema": 1,
        "ui_state": ui_state or {},
    }
    return session_data, sections_data, jcpds_data, ui_data


def save_model_to_param(model, ui_state=None, reason="manual-save"):
    if model is None or (not model.base_ptn_exist()):
        raise ValueError("Base pattern must exist before saving PARAM session.")
    param_dir = get_temp_dir(model.get_base_ptn_filename(), branch="-param")
    os.makedirs(param_dir, exist_ok=True)

    session_data, sections_data, jcpds_data, ui_data = _prepare_payloads(model, ui_state=ui_state)
    manifest = {
        "format_family": FORMAT_FAMILY,
        "format_version": FORMAT_VERSION,
        "created_at": datetime.datetime.now().isoformat(timespec="seconds"),
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

    changed_files = []
    for rel_path, new_bytes in payload_map.items():
        full_path = os.path.join(param_dir, rel_path)
        old_bytes = _file_bytes(full_path) if os.path.exists(full_path) else None
        if old_bytes != new_bytes:
            changed_files.append(rel_path)

    backup_id = None
    backup_root = None
    if changed_files:
        backup_id = _make_backup_id()
        backup_root = os.path.join(param_dir, "backups", backup_id)
        for rel_path in changed_files:
            src = os.path.join(param_dir, rel_path)
            if not os.path.exists(src):
                continue
            dst = os.path.join(backup_root, rel_path)
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copy2(src, dst)

    for rel_path, payload in payload_map.items():
        _atomic_write_bytes(os.path.join(param_dir, rel_path), payload)

    index_path = os.path.join(param_dir, BACKUP_INDEX_FILE)
    index = _get_backup_index(index_path)
    if changed_files:
        index["events"].append(
            {
                "id": backup_id,
                "timestamp": datetime.datetime.now().isoformat(timespec="seconds"),
                "reason": reason,
                "changed_files": changed_files,
            }
        )
        index = _prune_backup_events(param_dir, index, keep_last=BACKUP_KEEP_LAST)
    _atomic_write_json(index_path, index)

    return SaveResult(
        param_dir=param_dir,
        manifest_path=os.path.join(param_dir, MANIFEST_FILE),
        backup_id=backup_id,
        changed_files=changed_files,
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

    # Snapshot semantics:
    # each backup event stores file versions *before* that save.
    # "Restore event X" should reconstruct state *after* X was saved, so apply
    # snapshots for events newer than X (latest ... X+1), not X itself.
    for i in range(len(events) - 1, target_pos, -1):
        evt = events[i]
        snap_dir = os.path.join(param_dir, "backups", evt.get("id", ""))
        for rel_path in evt.get("changed_files", []):
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
    phase_payloads = jcpds_data.get("phases", jcpds_data.get("items", []))
    model.jcpds_lst = [_load_jcpds_item(p, chi_root) for p in phase_payloads]
    model.section_lst = [_dict_to_section(s) for s in sections_data.get("sections", [])]

    current_idx = session_data.get("current_section_index")
    model.current_section = None
    if isinstance(current_idx, int) and (0 <= current_idx < len(model.section_lst)):
        model.current_section = model.section_lst[current_idx]

    model.saved_pressure = session_data.get("saved_pressure", model.saved_pressure)
    model.saved_temperature = session_data.get("saved_temperature", model.saved_temperature)
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
    }
