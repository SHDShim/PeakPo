import os
import glob
import numpy as np

from ..utils import get_temp_dir, readchi
from ..ds_powdiff.DiffractionPattern import Pattern


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
        bg_params=None):
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
    for chi_path in files:
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
