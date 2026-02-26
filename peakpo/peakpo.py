import os
import sys
import faulthandler

# ========================================
# STEP 1: Environment Setup (BEFORE any imports)
# ========================================
if sys.platform == 'darwin':
    os.environ['MPLBACKEND'] = 'QtAgg'

faulthandler.enable()

# ========================================
# STEP 2: Import QtCore and set attributes ASAP
# ========================================
from qtpy.QtCore import Qt, QCoreApplication

if sys.platform == 'darwin':
    # Qt6 moved/removed some AA_* flags; apply only when available.
    app_attr = getattr(Qt, "ApplicationAttribute", None)
    share_gl = getattr(Qt, "AA_ShareOpenGLContexts", None)
    if share_gl is None and app_attr is not None:
        share_gl = getattr(app_attr, "AA_ShareOpenGLContexts", None)
    if share_gl is not None:
        QCoreApplication.setAttribute(share_gl, True)

    disable_hidpi = getattr(Qt, "AA_EnableHighDpiScaling", None)
    if disable_hidpi is None and app_attr is not None:
        disable_hidpi = getattr(app_attr, "AA_EnableHighDpiScaling", None)
    if disable_hidpi is not None:
        QCoreApplication.setAttribute(disable_hidpi, False)

# ========================================
# STEP 3: Configure Matplotlib (BEFORE QtWidgets QApplication)
# ========================================
import matplotlib
matplotlib.use('QtAgg')

# ========================================
# STEP 4: Import remaining Qt modules
# ========================================
from qtpy import QtCore, QtWidgets
from qtpy.QtGui import QPalette, QColor

# Standard library imports
from io import StringIO
import traceback
import time
from sys import platform as _platform

# ========================================
# STEP 5: CREATE QApplication FIRST!
# ========================================
app = QtWidgets.QApplication(sys.argv)
app.setStyle('Fusion')

# ========================================
# STEP 6: NOW Import Your Application Modules
# (Safe because QApplication exists)
# ========================================
if __package__ in (None, ""):
    # Support direct script execution (e.g., python peakpo/peakpo.py)
    # by forcing package context so relative imports behave consistently.
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)
    __package__ = "peakpo"

from .utils import ErrorMessageBox
from .control import MainController


# ========================================
# Exception Handler
# ========================================
def excepthook(exc_type, exc_value, traceback_obj):
    """Global exception handler"""
    # ✅ Safely convert error to string
    try:
        error_msg = str(exc_value)
    except:
        error_msg = repr(exc_value)
    
    # ✅ Don't show GUI for Qt/matplotlib painting errors
    painting_keywords = ['QPainter', 'QBackingStore', 'paint device', 
                        'drawRect', 'paintEvent', 'Painter not active',
                        'TypeError: arguments did not match']
    
    if any(keyword in error_msg for keyword in painting_keywords):
        print(f"\n⚠️  Qt/Matplotlib painting error (suppressed GUI dialog):")
        print(f"   {error_msg}")
        traceback.print_exception(exc_type, exc_value, traceback_obj)
        return  # Don't show error dialog for painting errors
    
    # ✅ For other errors, log and show dialog
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
    errorbox.exec()


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
ret = app.exec()
controller.write_setting()
sys.exit(ret)
