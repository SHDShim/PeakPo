import datetime
import json
import os
import re

from ..utils import get_temp_dir


AZINT_FORMAT = "peakpo-azimuthal-integration"
AZINT_VERSION = 1
AZINT_DIRNAME = "azimuthal_integrations"


def _as_float(value, default=None):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _clean_label(label):
    if label is None:
        return ""
    return str(label).strip()


def normalize_range(range_info, default_label=""):
    """
    Return a standard azimuth range dictionary.

    Supports the new schema and the old cake marker row format:
    [comment, tth_min, azi_min, tth_max, azi_max].
    """
    if isinstance(range_info, dict):
        azi_min = _as_float(range_info.get("azi_min"))
        azi_max = _as_float(range_info.get("azi_max"))
        label = _clean_label(range_info.get("label", default_label))
        note = _clean_label(range_info.get("note", ""))
        use = bool(range_info.get("use", True))
    else:
        try:
            values = list(range_info)
        except TypeError:
            values = []
        label = _clean_label(values[0] if len(values) > 0 else default_label)
        note = ""
        use = True
        if len(values) >= 5:
            azi_min = _as_float(values[2])
            azi_max = _as_float(values[4])
        elif len(values) >= 2:
            azi_min = _as_float(values[0])
            azi_max = _as_float(values[1])
        else:
            azi_min = None
            azi_max = None

    if azi_min is None or azi_max is None:
        return None
    if azi_max < azi_min:
        azi_min, azi_max = azi_max, azi_min
    return {
        "use": use,
        "label": label,
        "azi_min": float(azi_min),
        "azi_max": float(azi_max),
        "note": note,
    }


def normalize_ranges(ranges):
    out = []
    for i, range_info in enumerate(ranges or []):
        normalized = normalize_range(range_info, default_label=f"range {i + 1}")
        if normalized is not None:
            out.append(normalized)
    return out


def format_angle(value):
    value = float(value)
    text = f"{abs(value):06.2f}".replace(".", "p")
    prefix = "m" if value < 0 else "p"
    return prefix + text


def format_range(range_info, precision=2):
    r = normalize_range(range_info)
    if r is None:
        return ""
    return f"{r['azi_min']:.{precision}f} to {r['azi_max']:.{precision}f}"


def format_ranges(ranges, precision=2):
    normalized = normalize_ranges(ranges)
    return "; ".join(format_range(r, precision=precision) for r in normalized)


def _sanitize_token(text):
    text = str(text or "").strip().lower()
    text = re.sub(r"[^a-z0-9]+", "_", text)
    text = text.strip("_")
    return text or "azimuth"


def range_slug(ranges, label=""):
    normalized = normalize_ranges(ranges)
    if len(normalized) == 1:
        r = normalized[0]
        return f"azi_{format_angle(r['azi_min'])}_to_{format_angle(r['azi_max'])}"
    label_token = _sanitize_token(label)
    if label_token != "azimuth":
        return f"azi_{label_token}"
    if normalized:
        return f"azi_{len(normalized)}ranges"
    return "azi_ranges"


def output_dir_for_source(source_chi):
    param_dir = get_temp_dir(source_chi)
    output_dir = os.path.join(param_dir, AZINT_DIRNAME)
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    return output_dir


def default_setup_path(source_chi):
    stem = os.path.splitext(os.path.basename(source_chi))[0]
    return os.path.join(output_dir_for_source(source_chi), f"{stem}__azimuth_setup.json")


def unique_output_chi_path(source_chi, ranges, label=""):
    output_dir = output_dir_for_source(source_chi)
    source_stem = os.path.splitext(os.path.basename(source_chi))[0]
    slug = range_slug(ranges, label=label)
    base = f"{source_stem}__{slug}"
    if len(base) > 150:
        base = base[:150].rstrip("_")
    candidate = os.path.join(output_dir, base + ".chi")
    if not os.path.exists(candidate):
        return candidate
    idx = 2
    while True:
        candidate = os.path.join(output_dir, f"{base}_{idx:03d}.chi")
        if not os.path.exists(candidate):
            return candidate
        idx += 1


def sidecar_path_for_chi(chi_path):
    base, _ = os.path.splitext(chi_path)
    return base + ".azint.json"


def make_metadata(source_chi, derived_chi, ranges, azimuth_shift,
                  tth_range=None, source_image=None, poni=None, label=""):
    normalized = normalize_ranges(ranges)
    return {
        "format": AZINT_FORMAT,
        "version": AZINT_VERSION,
        "created_at": datetime.datetime.now().isoformat(timespec="seconds"),
        "source_chi": os.path.abspath(source_chi) if source_chi else "",
        "derived_chi": os.path.abspath(derived_chi) if derived_chi else "",
        "source_image": os.path.abspath(source_image) if source_image else "",
        "poni": os.path.abspath(poni) if poni else "",
        "label": _clean_label(label),
        "azimuth_shift": float(azimuth_shift),
        "two_theta_range": list(tth_range) if tth_range is not None else [],
        "azimuth_ranges": normalized,
    }


def write_sidecar(chi_path, metadata):
    path = sidecar_path_for_chi(chi_path)
    with open(path, "w") as handle:
        json.dump(metadata, handle, indent=2, sort_keys=True)
        handle.write("\n")
    return path


def read_sidecar(chi_path):
    path = sidecar_path_for_chi(chi_path)
    if not os.path.exists(path):
        return None
    try:
        with open(path) as handle:
            payload = json.load(handle)
    except (OSError, ValueError):
        return None
    if payload.get("format") != AZINT_FORMAT:
        return None
    return payload


def raw_provenance(chi_path=None):
    chi_path = os.path.abspath(chi_path) if chi_path else ""
    return {
        "source_kind": "full_chi",
        "source_chi": chi_path,
        "derived_chi": chi_path,
        "label": "Full CHI",
        "azimuth_ranges": [],
        "azimuth_shift": None,
    }


def provenance_from_metadata(metadata):
    if not isinstance(metadata, dict):
        return raw_provenance()
    ranges = normalize_ranges(metadata.get("azimuth_ranges", []))
    return {
        "source_kind": "azimuthal_integration",
        "source_chi": metadata.get("source_chi", ""),
        "derived_chi": metadata.get("derived_chi", ""),
        "label": metadata.get("label", ""),
        "azimuth_ranges": ranges,
        "azimuth_shift": metadata.get("azimuth_shift"),
    }


def provenance_for_chi(chi_path):
    metadata = read_sidecar(chi_path)
    if metadata is None:
        return raw_provenance(chi_path)
    return provenance_from_metadata(metadata)


def source_label(provenance):
    if not isinstance(provenance, dict):
        return "Full CHI"
    if provenance.get("source_kind") == "azimuthal_integration":
        label = _clean_label(provenance.get("label"))
        if label:
            return f"Azimuthal: {label}"
        return "Azimuthal CHI"
    return "Full CHI"


def source_ranges_label(provenance):
    if not isinstance(provenance, dict):
        return ""
    return format_ranges(provenance.get("azimuth_ranges", []), precision=1)
