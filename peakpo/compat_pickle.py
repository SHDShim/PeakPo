import pickle
import importlib

import dill

try:
    import uncertainties.core as _unc_core
except Exception:  # pragma: no cover
    _unc_core = None

_compat_azimuthal_integrator_cls = None


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
    if name == "AzimuthalIntegrator" and module in {
        "pyFAI.azimuthalIntegrator",
        "pyFAI.integrator.azimuthal",
    }:
        return _get_compat_azimuthal_integrator_class()
    return None


def _sanitize_pyfai_state(state):
    """Drop known legacy attributes that became read-only in newer pyFAI."""
    readonly_keys = {"_dssa"}
    if isinstance(state, dict):
        return {
            k: _sanitize_pyfai_state(v)
            for k, v in state.items()
            if k not in readonly_keys
        }
    if isinstance(state, tuple):
        return tuple(_sanitize_pyfai_state(v) for v in state)
    if isinstance(state, list):
        return [_sanitize_pyfai_state(v) for v in state]
    return state


def _apply_state_fallback(obj, state):
    """Best-effort state restore that tolerates read-only attributes."""
    if isinstance(state, dict):
        for key, value in state.items():
            try:
                setattr(obj, key, value)
            except Exception:
                pass
        return
    if isinstance(state, tuple):
        for item in state:
            _apply_state_fallback(obj, item)


def _build_compat_azimuthal_integrator_class():
    base_cls = None
    for module_name in ("pyFAI.azimuthalIntegrator", "pyFAI.integrator.azimuthal"):
        try:
            module = importlib.import_module(module_name)
            base_cls = getattr(module, "AzimuthalIntegrator", None)
        except Exception:
            base_cls = None
        if base_cls is not None:
            break
    if base_cls is None:
        return None

    class _CompatAzimuthalIntegrator(base_cls):
        # Keep legacy pickles from failing when trying to set _dssa.
        @property
        def _dssa(self):
            return getattr(self, "__peakpo_compat_dssa", None)

        @_dssa.setter
        def _dssa(self, value):
            self.__peakpo_compat_dssa = value

        def __setstate__(self, state):
            cleaned_state = _sanitize_pyfai_state(state)
            try:
                parent_setstate = getattr(super(), "__setstate__", None)
                if parent_setstate is not None:
                    return parent_setstate(cleaned_state)
            except Exception as inst:
                if "_dssa" not in str(inst):
                    raise
            _apply_state_fallback(self, cleaned_state)

    return _CompatAzimuthalIntegrator


def _get_compat_azimuthal_integrator_class():
    global _compat_azimuthal_integrator_cls
    if _compat_azimuthal_integrator_cls is None:
        _compat_azimuthal_integrator_cls = _build_compat_azimuthal_integrator_class()
    return _compat_azimuthal_integrator_cls


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
