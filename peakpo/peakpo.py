import sys
import time
import numpy
import traceback
from io import StringIO
from PyQt5 import QtWidgets
import qdarkstyle
from control import MainController
from utils import ErrorMessageBox


def excepthook(exc_type, exc_value, traceback_obj):
    """
    Global function to catch unhandled exceptions. This function will
    result in an error dialog which displays the
    error information.
    :param exc_type: exception type
    :param exc_value: exception value
    :param traceback_obj: traceback object
    :return:
    """
    separator = '-' * 80
    log_file = "error.log"
    time_string = time.strftime("%Y-%m-%d, %H:%M:%S")
    tb_info_file = StringIO()
    traceback.print_tb(traceback_obj, None, tb_info_file)
    tb_info_file.seek(0)
    tb_info = tb_info_file.read()
    errmsg = '%s: \n%s' % (str(exc_type), str(exc_value))
    sections = [separator, time_string, separator, errmsg, separator, tb_info]
    msg = '\n'.join(sections)
    try:
        f = open(log_file, "w")
        f.write(msg)
        f.close()
    except IOError:
        pass

    error_message = str(msg)
    errorbox = ErrorMessageBox()
    errorbox.setText(error_message)
    errorbox.exec_()


app = QtWidgets.QApplication(sys.argv)
sys.excepthook = excepthook
app.setStyleSheet(qdarkstyle.load_stylesheet_pyqt5())
# app.setStyleSheet('fusion')
controller = MainController()
controller.show_window()
ret = app.exec_()
controller.write_setting()
sys.exit(ret)
