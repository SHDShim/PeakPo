import sys
from PyQt5 import QtWidgets
import qdarkstyle
from control import MainController


def excepthook(exc_type, exc_value, traceback_obj):
    """
    Global function to catch unhandled exceptions. This function will result in an error dialog which displays the
    error information.
    :param exc_type: exception type
    :param exc_value: exception value
    :param traceback_obj: traceback object
    :return:
    """
    error_message = str(notice) + str(msg) + str(version_info)
    QtWidgets.QMessageBox.warning(
        self.widget, "Warning", error_message)


app = QtWidgets.QApplication(sys.argv)
app.setStyleSheet(qdarkstyle.load_stylesheet_pyqt5())
# app.setStyleSheet('fusion')
controller = MainController()
controller.show_window()
ret = app.exec_()
sys.exit(ret)
