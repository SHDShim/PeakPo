import pickle
import importlib
import types
import builtins

import dill

try:
    import uncertainties.core as _unc_core
except Exception:  # pragma: no cover
    _unc_core = None

_compat_azimuthal_integrator_cls = None
_dill_code_patch_applied = False
_orig_dill_create_code = None
_orig_code_type = types.CodeType
_compat_code_ctor_calls = 0
_BASE_DILL_UNPICKLER = getattr(pickle, "_Unpickler", pickle.Unpickler)


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
    if module_name == "dill.dill":
        return "dill._dill"
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
    if module == "types" and name == "CodeType":
        return _compat_code_type_ctor
    if module == "builtins" and name == "code":
        return _compat_code_type_ctor
    if module in {"dill._dill", "dill.dill", "_dill"} and name == "_create_code":
        return _compat_dill_create_code
    if module in {"dill._dill", "dill.dill", "_dill"} and name == "_get_attr":
        return _compat_dill_get_attr
    return None


def _compat_code_type_ctor(*args):
    global _compat_code_ctor_calls
    _compat_code_ctor_calls += 1
    """
    Rebuild legacy pickled code objects on newer Python runtimes.

    Older dill payloads may serialize CodeType with 15/16 positional args
    (Python 3.7/3.8 style), while Python 3.11 expects additional fields.
    """
    code_type = _orig_code_type
    try:
        return code_type(*args)
    except TypeError as inst:
        msg = str(inst)
        if "code expected at least" not in msg:
            raise

    argc = len(args)
    if argc == 15:
        (
            argcount, kwonlyargcount, nlocals, stacksize, flags,
            codestring, constants, names, varnames,
            filename, name, firstlineno, lnotab, freevars, cellvars,
        ) = args
        return code_type(
            argcount, 0, kwonlyargcount, nlocals, stacksize, flags,
            codestring, constants, names, varnames,
            filename, name, name, firstlineno, lnotab, b"",
            freevars, cellvars,
        )
    if argc == 16:
        (
            argcount, posonlyargcount, kwonlyargcount, nlocals, stacksize,
            flags, codestring, constants, names, varnames,
            filename, name, firstlineno, lnotab, freevars, cellvars,
        ) = args
        return code_type(
            argcount, posonlyargcount, kwonlyargcount, nlocals, stacksize,
            flags, codestring, constants, names, varnames,
            filename, name, name, firstlineno, lnotab, b"",
            freevars, cellvars,
        )

    # Unknown legacy signature; re-raise with original context.
    return code_type(*args)


def _to_bytes_if_needed(value):
    return value.encode() if hasattr(value, "encode") else value


def _compat_dill_create_code(*args):
    """
    Compatibility wrapper for old dill _create_code implementations.
    """
    if _orig_dill_create_code is not None:
        try:
            return _orig_dill_create_code(*args)
        except TypeError as inst:
            if "code expected at least" not in str(inst):
                raise

    code_args = args
    lnotab = b""
    # Some dill versions store lnotab/linetable as a prefixed first arg.
    if code_args and not isinstance(code_args[0], int):
        lnotab = _to_bytes_if_needed(code_args[0])
        code_args = code_args[1:]

    code_type = _orig_code_type
    argc = len(code_args)
    if argc == 15:
        (
            argcount, kwonlyargcount, nlocals, stacksize, flags,
            codestring, constants, names, varnames,
            filename, name, firstlineno, lnotab_or_linetable,
            freevars, cellvars,
        ) = code_args
        return code_type(
            argcount, 0, kwonlyargcount, nlocals, stacksize, flags,
            _to_bytes_if_needed(codestring), constants, names, varnames,
            filename, name, name, firstlineno,
            _to_bytes_if_needed(lnotab_or_linetable if lnotab_or_linetable else lnotab),
            b"", freevars, cellvars,
        )
    if argc == 16:
        (
            argcount, posonlyargcount, kwonlyargcount, nlocals, stacksize,
            flags, codestring, constants, names, varnames,
            filename, name, firstlineno, lnotab_or_linetable,
            freevars, cellvars,
        ) = code_args
        return code_type(
            argcount, posonlyargcount, kwonlyargcount, nlocals, stacksize,
            flags, _to_bytes_if_needed(codestring), constants, names, varnames,
            filename, name, name, firstlineno,
            _to_bytes_if_needed(lnotab_or_linetable if lnotab_or_linetable else lnotab),
            b"", freevars, cellvars,
        )

    # Fallback for unknown signatures.
    return _compat_code_type_ctor(*code_args)


def _compat_dill_get_attr(obj, name):
    """
    Compatibility wrapper for dill._dill._get_attr.

    Some legacy payloads reconstruct CodeType through:
    _get_attr(_import_module("types"), "CodeType")
    """
    value = getattr(obj, name, None) or getattr(builtins, name)
    if value is _orig_code_type:
        return _compat_code_type_ctor
    return value


def _patch_dill_create_code():
    """
    Patch dill's internal code-object constructor globally for legacy payloads.
    """
    global _dill_code_patch_applied, _orig_dill_create_code
    if _dill_code_patch_applied:
        return
    try:
        import dill._dill as _dill_impl
    except Exception:
        return
    if _orig_dill_create_code is None:
        _orig_dill_create_code = getattr(_dill_impl, "_create_code", None)
    if _orig_dill_create_code is None:
        return

    def _patched_create_code(*args):
        try:
            return _orig_dill_create_code(*args)
        except TypeError as inst:
            if "code expected at least" not in str(inst):
                raise
            return _compat_dill_create_code(*args)

    _dill_impl._create_code = _patched_create_code
    # Some legacy payloads reference dill._dill.CodeType directly.
    # Rebind it to our compat constructor to handle 15/16-arg signatures.
    try:
        _dill_impl.CodeType = _compat_code_type_ctor
    except Exception:
        pass
    # Handle payloads that resolve via GLOBAL 'builtins code' without touching
    # stdlib types.CodeType (inspect/isinstance expect a real type there).
    try:
        builtins.code = _compat_code_type_ctor
    except Exception:
        pass
    # Guard against previous runs that may have replaced types.CodeType.
    try:
        if types.CodeType is not _orig_code_type:
            types.CodeType = _orig_code_type
    except Exception:
        pass
    _dill_code_patch_applied = True


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


class PeakPoCompatDillUnpickler(_BASE_DILL_UNPICKLER):
    def __init__(self, file_obj):
        _patch_dill_create_code()
        super().__init__(file_obj, encoding="latin1")

    def find_class(self, module, name):
        compat_class = _resolve_compat_class(module, name)
        if compat_class is not None:
            return compat_class
        return super().find_class(_map_legacy_module(module), name)

    def load_reduce(self):
        stack = self.stack
        args = stack.pop()
        func = stack[-1]
        try:
            stack[-1] = func(*args)
        except TypeError as inst:
            if "code expected at least" not in str(inst):
                raise
            stack[-1] = _compat_code_type_ctor(*args)


# Ensure REDUCE opcode uses our compatibility load_reduce implementation.
if hasattr(_BASE_DILL_UNPICKLER, "dispatch"):
    PeakPoCompatDillUnpickler.dispatch = _BASE_DILL_UNPICKLER.dispatch.copy()
    PeakPoCompatDillUnpickler.dispatch[pickle.REDUCE[0]] = PeakPoCompatDillUnpickler.load_reduce


# Apply dill code-object compatibility patch on module import as well, so any
# fallback/raw dill usage in the process is also protected.
_patch_dill_create_code()
