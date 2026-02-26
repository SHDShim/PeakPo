import pickle

import dill

try:
    import uncertainties.core as _unc_core
except Exception:  # pragma: no cover
    _unc_core = None


_LEGACY_ROOTS = {
    "control",
    "model",
    "view",
    "utils",
    "version",
    "citation",
    "ds_cake",
    "ds_jcpds",
    "ds_powdiff",
    "ds_section",
}


def _map_legacy_module(module_name):
    if module_name.startswith("peakpo."):
        return module_name
    root = module_name.split(".", 1)[0]
    if root in _LEGACY_ROOTS:
        return f"peakpo.{module_name}"
    return module_name


class _CompatCallableStdDev(object):
    """
    Minimal compatibility shim for legacy uncertainties pickles.

    Older versions of uncertainties exposed uncertainties.core.CallableStdDev.
    Newer versions may not, which breaks dill/pickle loading for old .dpp files.
    This class accepts arbitrary pickled state and returns a safe float when
    called, allowing the session to load.
    """
    def __init__(self, *args, **kwargs):
        # Accept any legacy constructor signature used in old pickles.
        value = 0.0
        if args:
            try:
                value = float(args[0])
            except Exception:
                value = 0.0
        elif "value" in kwargs:
            try:
                value = float(kwargs["value"])
            except Exception:
                value = 0.0
        self.value = value

    def __call__(self, *args, **kwargs):
        return self.value

    def __float__(self):
        return float(self.value)


def _resolve_compat_class(module, name):
    if module == "uncertainties.core" and name == "CallableStdDev":
        # Prefer real symbol when present.
        if _unc_core is not None and hasattr(_unc_core, "CallableStdDev"):
            return getattr(_unc_core, "CallableStdDev")
        return _CompatCallableStdDev
    return None


class PeakPoCompatPickleUnpickler(pickle.Unpickler):
    def __init__(self, file_obj):
        super().__init__(file_obj, encoding="latin1")

    def find_class(self, module, name):
        compat_class = _resolve_compat_class(module, name)
        if compat_class is not None:
            return compat_class
        return super().find_class(_map_legacy_module(module), name)


class PeakPoCompatDillUnpickler(dill.Unpickler):
    def find_class(self, module, name):
        compat_class = _resolve_compat_class(module, name)
        if compat_class is not None:
            return compat_class
        return super().find_class(_map_legacy_module(module), name)
