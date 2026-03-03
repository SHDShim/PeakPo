import os
import glob
import numpy as np

from ..utils import get_temp_dir, readchi


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
