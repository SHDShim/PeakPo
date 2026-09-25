import os
import sys


def _verify_rendering():
    """Check that a clean bundled canvas has visible night-mode axes."""
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    from qtpy import QtWidgets

    from .view.mplwidget import MplCanvas

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    canvas = MplCanvas()
    canvas.resize_axes(30)

    expected = (1.0, 1.0, 1.0, 1.0)
    checks = [
        canvas.ax_pattern.xaxis.label.get_color() == "white",
        canvas.ax_pattern.yaxis.label.get_color() == "white",
        canvas.ax_pattern.xaxis.get_tick_params()["labelcolor"] == "white",
        canvas.ax_pattern.yaxis.get_tick_params()["labelcolor"] == "white",
        all(spine.get_edgecolor() == expected
            for spine in canvas.ax_pattern.spines.values()),
    ]
    canvas.close()
    app.processEvents()
    return 0 if all(checks) else 1


def _verify_warning_dialog():
    """Exercise the warning path used at file-navigation boundaries."""
    import gc

    from qtpy import QtCore, QtWidgets

    from .utils import show_warning
    from .view.mainwidget import MainWindow

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    window = MainWindow()
    window.setAttribute(QtCore.Qt.WidgetAttribute.WA_DeleteOnClose)
    window.show()
    window.doubleSpinBox_Pressure.setFocus()
    gc.collect()
    app.processEvents()

    focused_widget = app.focusWidget()
    popup = show_warning(
        window, "Warning", "It is already the last file.")
    app.processEvents()
    passed = bool(
        popup is not None
        and popup.parent() is window.centralWidget()
        and (
            focused_widget is None
            or app.focusWidget() is focused_widget
        )
    )
    window.close()
    app.processEvents()
    del window
    gc.collect()
    return 0 if passed else 1


def _verify_navigation_boundary(data_dir):
    """Exercise the real controller and Prev button on the first CHI file."""
    from qtpy import QtCore, QtWidgets

    from .control.maincontroller import MainController
    from .utils import get_sorted_filelist
    from .utils.pyqtutils import CheckboxIndicatorStyle

    data_dir = os.path.abspath(data_dir)
    files = get_sorted_filelist(
        data_dir, sorted_by_name=True, search_ext="*.chi")
    if not files:
        print(f"No CHI files found in {data_dir}", file=sys.stderr)
        return 2

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    app._peakpo_style = CheckboxIndicatorStyle(
        QtWidgets.QStyleFactory.create("Fusion"))
    app.setStyle(app._peakpo_style)
    controller = MainController()
    window = controller.widget
    window.setAttribute(QtCore.Qt.WidgetAttribute.WA_DeleteOnClose)
    window.show()
    window.radioButton_SortbyNme.setChecked(True)
    window.checkBox_NavDPP.setChecked(False)

    controller.base_ptn_ctrl._load_a_new_pattern(files[0])
    app.processEvents()
    before = controller.model.base_ptn.fname
    window.pushButton_PrevBasePtn.click()
    app.processEvents()
    popup = getattr(window, "_peakpo_warning_popup", None)
    passed = bool(
        controller.model.base_ptn_exist()
        and controller.model.base_ptn.fname == before
        and popup is not None
        and popup.parent() is window.centralWidget()
    )
    for expected in files[1:]:
        window.pushButton_NextBasePtn.click()
        app.processEvents()
        passed = passed and os.path.samefile(
            controller.model.base_ptn.fname, expected)
    for expected in reversed(files[:-1]):
        window.pushButton_PrevBasePtn.click()
        app.processEvents()
        passed = passed and os.path.samefile(
            controller.model.base_ptn.fname, expected)

    before = controller.model.base_ptn.fname
    window.pushButton_PrevBasePtn.click()
    app.processEvents()
    popup = getattr(window, "_peakpo_warning_popup", None)
    passed = bool(
        passed
        and controller.model.base_ptn.fname == before
        and popup is not None
        and popup.parent() is window.centralWidget()
    )
    window.close()
    app.processEvents()
    return 0 if passed else 1


def main():
    if "--version" in sys.argv[1:]:
        from .version import __version__

        print(__version__)
        return 0

    if "--verify-rendering" in sys.argv[1:]:
        return _verify_rendering()

    if "--verify-warning-dialog" in sys.argv[1:]:
        status = _verify_warning_dialog()
        # A short-lived Qt GUI probe can fault during PyQt interpreter
        # teardown after every test object has already been destroyed. Exit
        # directly once the dialog path itself has completed successfully.
        os._exit(status)

    if "--verify-navigation-boundary" in sys.argv[1:]:
        option_index = sys.argv.index("--verify-navigation-boundary")
        try:
            data_dir = sys.argv[option_index + 1]
        except IndexError:
            print(
                "--verify-navigation-boundary requires a data directory",
                file=sys.stderr,
            )
            return 2
        status = _verify_navigation_boundary(data_dir)
        os._exit(status)

    # Importing this module launches the Qt application.
    from . import peakpo  # noqa: F401
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
