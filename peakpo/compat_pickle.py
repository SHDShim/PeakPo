import pickle

import dill


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


class PeakPoCompatPickleUnpickler(pickle.Unpickler):
    def __init__(self, file_obj):
        super().__init__(file_obj, encoding="latin1")

    def find_class(self, module, name):
        return super().find_class(_map_legacy_module(module), name)


class PeakPoCompatDillUnpickler(dill.Unpickler):
    def find_class(self, module, name):
        return super().find_class(_map_legacy_module(module), name)
