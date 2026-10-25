"""Derived 1D data for fast, repeatable Map ROI integration.

The cache contains no session settings. It can be deleted at any time; source
CHI files and background controls always determine the computed values.
"""

import hashlib
import json
import os
import re
import tempfile
import zipfile

import numpy as np

from .xrdiohelpers import load_chi_xy
from ..ds_powdiff.DiffractionPattern import Pattern


_CACHE_VERSION = 1


class MapDataCache:
    def __init__(self):
        self.directory = None
        self.root_directory = None
        self.set_name = None
        self._memory = {}
        self._fingerprints = {}
        self._raw = {}
        self._coordinates = {}
        self._coordinates_dirty = False

    def set_files(self, files):
        parents = {os.path.dirname(os.path.abspath(path)) for path in files}
        root = (os.path.join(parents.pop(), "map_param")
                if files and len(parents) == 1 else None)
        self.root_directory = root
        self.set_name = self.file_set_name(files) if root else None
        directory = (os.path.join(root, self.set_name) if root else None)
        if directory != self.directory:
            self.directory = directory
            self._coordinates = {}
            if directory:
                try:
                    coordinate_file = os.path.join(directory, "coordinates.json")
                    if not os.path.isfile(coordinate_file):
                        coordinate_file = os.path.join(root, "coordinates.json")
                    with open(coordinate_file,
                              encoding="utf-8") as source:
                        payload = json.load(source)
                    if payload.get("version") == _CACHE_VERSION:
                        self._coordinates = payload.get("entries", {})
                except (OSError, ValueError, AttributeError):
                    pass
        selected = set(files)
        self._raw = {key: value for key, value in self._raw.items()
                     if key in selected}
        self._fingerprints = {
            key: value for key, value in self._fingerprints.items()
            if key in selected}
        self._memory = {
            key: value for key, value in self._memory.items()
            if key[0] in selected}

    @staticmethod
    def file_set_pattern(path):
        stem = os.path.splitext(os.path.basename(path))[0]
        match = re.search(r"map_(\d+)", stem, flags=re.IGNORECASE)
        if match:
            return stem[:match.start(1)] + "series" + stem[match.end(1):]
        match = re.fullmatch(r"(.*\D)(\d+)(\D+)(\d+)", stem)
        if match:
            return match.group(1) + "series" + match.group(3) + match.group(4)
        return re.sub(r"\d+$", "series", stem)

    @staticmethod
    def file_set_name(files):
        """Readable, portable directory name unique to the exact CHI selection."""
        basenames = [os.path.basename(path) for path in files]
        labels = {MapDataCache.file_set_pattern(name) for name in basenames}
        label = next(iter(labels)) if len(labels) == 1 else "mixed-map-set"
        safe = re.sub(r"[^A-Za-z0-9._-]+", "_", label).strip("._-")[:70]
        digest = hashlib.sha256(
            "\n".join(sorted(name.casefold() for name in basenames)).encode("utf-8")
        ).hexdigest()[:10]
        return f"{safe or 'map-set'}-{digest}"

    def save_state(self, state):
        if self.directory is None:
            return False
        temporary = None
        try:
            os.makedirs(self.directory, exist_ok=True)
            with tempfile.NamedTemporaryFile(
                    mode="w", encoding="utf-8", dir=self.directory,
                    suffix=".json", delete=False) as output:
                temporary = output.name
                json.dump({"version": _CACHE_VERSION, **state}, output)
            os.replace(temporary, os.path.join(self.directory, "state.json"))
            return True
        except (OSError, TypeError, ValueError):
            return False
        finally:
            if temporary and os.path.exists(temporary):
                try:
                    os.unlink(temporary)
                except OSError:
                    pass

    @staticmethod
    def discover_states(folder):
        root = os.path.join(folder, "map_param")
        states = []
        try:
            candidates = os.scandir(root)
        except OSError:
            return states
        with candidates:
            for entry in candidates:
                if not entry.is_dir():
                    continue
                path = os.path.join(entry.path, "state.json")
                try:
                    with open(path, encoding="utf-8") as source:
                        state = json.load(source)
                    if (state.get("version") != _CACHE_VERSION or
                            not isinstance(state.get("files"), list) or
                            not state["files"] or
                            any(not isinstance(name, str) or
                                os.path.basename(name) != name or
                                not name.lower().endswith(".chi")
                                for name in state["files"])):
                        continue
                    state["_directory"] = entry.path
                    state["_mtime_ns"] = os.stat(path).st_mtime_ns
                    states.append(state)
                except (OSError, ValueError, AttributeError, TypeError):
                    continue
        return sorted(states, key=lambda state: state["_mtime_ns"], reverse=True)

    @staticmethod
    def has_legacy_data(folder, files):
        """Only infer an old flat set when that cache names one of its CHIs."""
        root = os.path.join(folder, "map_param")
        for path in files:
            name = hashlib.sha256(
                os.path.basename(path).encode("utf-8")).hexdigest()[:20]
            if any(os.path.isfile(os.path.join(root, f"{name}-{kind}.npz"))
                   for kind in ("raw", "bg")):
                return True
        try:
            with open(os.path.join(root, "coordinates.json"),
                      encoding="utf-8") as source:
                entries = json.load(source).get("entries", {})
            return any(os.path.basename(path) in entries for path in files)
        except (OSError, ValueError, AttributeError):
            return False

    def coordinates(self, path, sources, resolver):
        stamps = []
        for source in sources:
            try:
                stat = os.stat(source)
                stamps.append([os.path.relpath(source, os.path.dirname(path)), stat.st_size,
                               stat.st_mtime_ns])
            except OSError:
                continue
        # A cache folder may be copied between Windows and macOS. The source
        # folder contains only one CHI with each basename.
        key = os.path.basename(path) if self.directory else os.path.abspath(path)
        cached = self._coordinates.get(key)
        if cached is not None and cached.get("sources") == stamps:
            return cached.get("xy")
        xy = resolver()
        self._coordinates[key] = {
            "sources": stamps,
            "xy": list(xy) if xy is not None else None,
        }
        self._coordinates_dirty = True
        return xy

    def save_coordinates(self):
        if not self._coordinates_dirty or self.directory is None:
            return
        temporary = None
        try:
            os.makedirs(self.directory, exist_ok=True)
            with tempfile.NamedTemporaryFile(
                    mode="w", encoding="utf-8", dir=self.directory,
                    suffix=".json", delete=False) as output:
                temporary = output.name
                json.dump({"version": _CACHE_VERSION,
                           "entries": self._coordinates}, output)
            os.replace(temporary, os.path.join(self.directory,
                                               "coordinates.json"))
            self._coordinates_dirty = False
        except (OSError, TypeError, ValueError):
            pass
        finally:
            if temporary and os.path.exists(temporary):
                try:
                    os.unlink(temporary)
                except OSError:
                    pass

    def _fingerprint(self, path):
        stat = os.stat(path)
        stamp = (stat.st_size, stat.st_mtime_ns)
        cached = self._fingerprints.get(path)
        if cached is not None and cached[0] == stamp:
            return cached[1]
        digest = hashlib.sha256()
        with open(path, "rb") as source:
            for block in iter(lambda: source.read(1024 * 1024), b""):
                digest.update(block)
        fingerprint = (stat.st_size, stat.st_mtime_ns, digest.hexdigest())
        self._fingerprints[path] = (stamp, fingerprint)
        self._raw.pop(path, None)
        self._memory = {key: value for key, value in self._memory.items()
                        if key[0] != path}
        return fingerprint

    def _cache_path(self, path, bg):
        if self.directory is None:
            return None
        name = hashlib.sha256(os.path.basename(path).encode("utf-8")).hexdigest()[:20]
        return os.path.join(self.directory, f"{name}-{'bg' if bg else 'raw'}.npz")

    def _raw_xy(self, path):
        if path not in self._raw:
            self._raw[path] = load_chi_xy(path, self._raw)
        return self._raw[path]

    @staticmethod
    def _background_xy(x, y, bg_roi, bg_params):
        lo = max(float(np.nanmin(x)), float(min(bg_roi)))
        hi = min(float(np.nanmax(x)), float(max(bg_roi)))
        if hi <= lo:
            lo, hi = float(np.nanmin(x)), float(np.nanmax(x))
        pattern = Pattern()
        pattern.x_raw, pattern.y_raw = x, y
        pattern.subtract_bg([lo, hi], params=list(bg_params), yshift=0)
        return pattern.get_bgsub()

    @staticmethod
    def _series(x, y):
        x = np.asarray(x, dtype=float)
        y = np.asarray(y, dtype=float)
        if x.ndim != 1 or y.ndim != 1 or x.size != y.size:
            raise ValueError("Invalid CHI data for Map")
        # Prefix subtraction is valid only for ordered, finite data. Retain
        # direct sums for unusual legacy CHI files with inf or unsorted axes.
        if np.all(np.isfinite(x)) and np.all(np.diff(x) >= 0) and not np.any(np.isinf(y)):
            prefix = np.concatenate(([0.0], np.cumsum(np.where(np.isnan(y), 0.0, y))))
            return x, prefix, None
        return x, None, y

    def series(self, path, bg_roi=None, bg_params=None):
        fingerprint = self._fingerprint(path)
        bg = bg_roi is not None
        settings = (tuple(float(v) for v in bg_roi),
                    tuple(int(v) for v in bg_params)) if bg else None
        signature = json.dumps([_CACHE_VERSION, fingerprint, settings],
                               separators=(",", ":"))
        key = (path, signature)
        if key in self._memory:
            return self._memory[key]

        cache_path = self._cache_path(path, bg)
        legacy_path = (os.path.join(self.root_directory,
                                   os.path.basename(cache_path))
                       if cache_path and self.root_directory else None)
        readable_path = cache_path if cache_path and os.path.isfile(cache_path) else legacy_path
        if readable_path and os.path.isfile(readable_path):
            try:
                with np.load(readable_path, allow_pickle=False) as data:
                    if str(data["signature"].item()) == signature:
                        result = (data["x"], data["prefix"], None)
                        self._memory[key] = result
                        return result
            except (OSError, ValueError, KeyError, EOFError, zipfile.BadZipFile):
                pass  # Incomplete or older cache: recompute from CHI.

        x, y = self._raw_xy(path)
        if bg:
            x, y = self._background_xy(x, y, bg_roi, bg_params)
        result = self._series(x, y)
        self._memory[key] = result
        if cache_path and result[1] is not None:
            temporary = None
            try:
                os.makedirs(self.directory, exist_ok=True)
                with tempfile.NamedTemporaryFile(
                        dir=self.directory, suffix=".npz", delete=False) as output:
                    temporary = output.name
                    np.savez(output, signature=signature, x=result[0],
                             prefix=result[1])
                os.replace(temporary, cache_path)
            except OSError:
                pass  # Read-only data folders still use the in-memory cache.
            finally:
                if temporary and os.path.exists(temporary):
                    try:
                        os.unlink(temporary)
                    except OSError:
                        pass
        return result

    def sum_roi(self, path, roi, bg_roi=None, bg_params=None):
        x, prefix, y = self.series(path, bg_roi=bg_roi, bg_params=bg_params)
        xmin, xmax = roi
        if prefix is None:
            mask = (x >= xmin) & (x <= xmax)
            return float(np.nansum(y[mask])) if np.any(mask) else np.nan
        left = int(np.searchsorted(x, xmin, side="left"))
        right = int(np.searchsorted(x, xmax, side="right"))
        return float(prefix[right] - prefix[left]) if right > left else np.nan
