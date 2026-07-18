from peakpo.control.maincontroller import MainController


class _SettingsStub:
    def __init__(self, values):
        self.values = dict(values)

    def contains(self, key):
        return key in self.values

    def value(self, key):
        return self.values[key]

    def setValue(self, key, value):
        self.values[key] = value


def test_legacy_jcpds_dimming_setting_is_migrated_once():
    controller = MainController.__new__(MainController)
    controller.settings = _SettingsStub({"plot_cfg/jcpds_alpha_cake": 0.36})

    controller._migrate_legacy_plot_config_settings()

    assert controller.settings.values["plot_cfg/jcpds_dimming_factor"] == 0.36


def test_existing_jcpds_dimming_setting_is_not_overwritten():
    controller = MainController.__new__(MainController)
    controller.settings = _SettingsStub({
        "plot_cfg/jcpds_alpha_cake": 0.36,
        "plot_cfg/jcpds_dimming_factor": 0.20,
    })

    controller._migrate_legacy_plot_config_settings()

    assert controller.settings.values["plot_cfg/jcpds_dimming_factor"] == 0.20
