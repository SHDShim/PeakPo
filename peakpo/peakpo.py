# fbs - uncomment the following line
#from fbs_runtime.application_context.PyQt5 import ApplicationContext
#
import sys
from utils import ErrorMessageBox
from control import MainController
from PyQt5.QtCore import Qt
from PyQt5 import QtCore
from PyQt5 import QtWidgets
from PyQt5.QtGui import QPalette, QColor
from io import StringIO
import traceback
import numpy
import time
import os
import faulthandler
from sys import platform as _platform

faulthandler.enable()

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
app = QtWidgets.QApplication(sys.argv) #app.setAttribute(QtCore.Qt.AA_EnableHighDpiScaling)
app.setStyle('Fusion') # default Fusion
#['bb10dark', 'bb10bright', 'cleanlooks', 'cde', 'motif', 'plastique', 'Windows', 'Fusion']
# fbs
#  comment two lines above and uncomment the following two lines
#appctxt = ApplicationContext() #QtWidgets.QApplication(sys.argv)
#appctxt.app.setStyle('Fusion')
sys.excepthook = excepthook

# Now use a palette to switch to dark colors:
dark_palette = QPalette()
dark_palette.setColor(QPalette.Window, QColor(53, 53, 53))
dark_palette.setColor(QPalette.WindowText, Qt.white)
dark_palette.setColor(QPalette.Base, QColor(35, 35, 35))
dark_palette.setColor(QPalette.AlternateBase, QColor(53, 53, 53))
dark_palette.setColor(QPalette.ToolTipBase, QColor(25, 25, 25))
dark_palette.setColor(QPalette.ToolTipText, Qt.white)
if _platform == "darwin": # works only for mac
    dark_palette.setColor(QPalette.Text, Qt.white)
else:
    dark_palette.setColor(QPalette.Text, Qt.darkGray)
dark_palette.setColor(QPalette.Button, QColor(53, 53, 53))
dark_palette.setColor(QPalette.ButtonText, Qt.white)
dark_palette.setColor(QPalette.BrightText, Qt.red)
dark_palette.setColor(QPalette.Link, QColor(42, 130, 218))
dark_palette.setColor(QPalette.Highlight, QColor(42, 130, 218))
dark_palette.setColor(QPalette.HighlightedText, QColor(35, 35, 35))
dark_palette.setColor(QPalette.Active, QPalette.Button, QColor(53, 53, 53))
dark_palette.setColor(QPalette.Disabled, QPalette.ButtonText, Qt.darkGray)
dark_palette.setColor(QPalette.Disabled, QPalette.WindowText, Qt.darkGray)
dark_palette.setColor(QPalette.Disabled, QPalette.Text, Qt.darkGray)
dark_palette.setColor(QPalette.Disabled, QPalette.Light, QColor(53, 53, 53))
app.setPalette(dark_palette)

# fbs
#  comment a line above and uncomment the following line
#    appctxt.app.setPalette(dark_palette)


controller = MainController()
controller.show_window()
ret = app.exec_()
# fbs
#  comment line above and uncomment line below
#ret = appctxt.app.exec_()
controller.write_setting()
sys.exit(ret)
