import os
import sys
import time
import numpy
import traceback
from io import StringIO
from PyQt5 import QtWidgets
from PyQt5 import QtCore
from PyQt5.QtCore import Qt
from control import MainController
from utils import ErrorMessageBox
import qdarkstyle


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


# 2020/02/15 block below does not affect screen resolution
#QtCore.QCoreApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
#os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"

app = QtWidgets.QApplication(sys.argv)
# 2020/02/15 block below does not affect screen resolution
# app.setAttribute(QtCore.Qt.AA_EnableHighDpiScaling)
sys.excepthook = excepthook
if '-day' in sys.argv:
    app.setStyle('default')
else:
    app.setStyleSheet(qdarkstyle.load_stylesheet_pyqt5())
controller = MainController()
controller.show_window()
ret = app.exec_()
controller.write_setting()
sys.exit(ret)
