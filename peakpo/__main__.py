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


def main():
    if "--version" in sys.argv[1:]:
        from .version import __version__

        print(__version__)
        return 0

    if "--verify-rendering" in sys.argv[1:]:
        return _verify_rendering()

    # Importing this module launches the Qt application.
    from . import peakpo  # noqa: F401
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
