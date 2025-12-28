import os
import sys
import faulthandler

# ========================================
# STEP 1: Environment Setup (BEFORE any imports)
# ========================================
if sys.platform == 'darwin':
    os.environ['QT_MAC_WANTS_LAYER'] = '1'
    os.environ['MPLBACKEND'] = 'Qt5Agg'

faulthandler.enable()

# ========================================
# STEP 2: Configure Matplotlib (BEFORE PyQt5)
# ========================================
import matplotlib
matplotlib.use('Qt5Agg')

# ========================================
# STEP 3: Import PyQt5 ONLY (not your app modules yet)
# ========================================
from PyQt5.QtCore import Qt, QCoreApplication
from PyQt5 import QtCore, QtWidgets
from PyQt5.QtGui import QPalette, QColor

# Standard library imports
from io import StringIO
import traceback
import time
from sys import platform as _platform

# ========================================
# STEP 4: Set Qt Attributes (BEFORE QApplication)
# ========================================
if sys.platform == 'darwin':
    QCoreApplication.setAttribute(Qt.AA_ShareOpenGLContexts, True)
    QCoreApplication.setAttribute(Qt.AA_EnableHighDpiScaling, False)

# ========================================
# STEP 5: CREATE QApplication FIRST!
# ========================================
app = QtWidgets.QApplication(sys.argv)
app.setStyle('Fusion')

# ========================================
# STEP 6: NOW Import Your Application Modules
# (Safe because QApplication exists)
# ========================================
from utils import ErrorMessageBox
from control import MainController


# ========================================
# Exception Handler
# ========================================
def excepthook(exc_type, exc_value, traceback_obj):
    """Global exception handler"""
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
        with open(log_file, "w") as f:
            f.write(msg)
    except IOError:
        pass
    
    error_message = str(msg)
    errorbox = ErrorMessageBox()
    errorbox.setText(error_message)
    errorbox.exec_()


sys.excepthook = excepthook

# ========================================
# Setup Dark Palette
# ========================================
dark_palette = QPalette()
dark_palette.setColor(QPalette.Window, QColor(53, 53, 53))
dark_palette.setColor(QPalette.WindowText, Qt.white)
dark_palette.setColor(QPalette.Base, QColor(35, 35, 35))
dark_palette.setColor(QPalette.AlternateBase, QColor(53, 53, 53))
dark_palette.setColor(QPalette.ToolTipBase, QColor(25, 25, 25))
dark_palette.setColor(QPalette.ToolTipText, Qt.white)

if _platform == "darwin":
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

# ========================================
# Create and Show Window
# ========================================
controller = MainController()
controller.show_window()

# ✅ Give Qt time to create the window and initialize canvas
QtCore.QTimer.singleShot(200, lambda: print("Event loop running, canvas should be ready"))
app.processEvents()

# ========================================
# Run Event Loop
# ========================================
ret = app.exec_()
controller.write_setting()
sys.exit(ret)