from types import SimpleNamespace

from peakpo.control.exportpythoncontroller import ExportPythonController


def test_default_folder_prefix_uses_base_pattern_filename():
    model = SimpleNamespace(
        chi_path="/data/current-folder",
        get_base_ptn_filename=lambda: "/data/current-folder/sample_001.chi",
        base_ptn=SimpleNamespace(fname="/data/current-folder/other.chi"),
    )
    ctrl = ExportPythonController(model, widget=None)

    assert ctrl._default_folder_prefix() == "sample_001"


def test_default_folder_prefix_falls_back_to_peakpo_without_data_filename():
    model = SimpleNamespace(chi_path="/data/current-folder", base_ptn=None)
    ctrl = ExportPythonController(model, widget=None)

    assert ctrl._default_folder_prefix() == "peakpo"
