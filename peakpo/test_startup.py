# test_startup.py
import os
import sys

print("=" * 60)
print("STARTUP DEBUG TEST")
print("=" * 60)

if sys.platform == 'darwin':
    os.environ['QT_MAC_WANTS_LAYER'] = '1'
    os.environ['MPLBACKEND'] = 'Qt5Agg'

print("Step 1: Configuring matplotlib...")
import matplotlib
matplotlib.use('Qt5Agg')
print("   ✓ Matplotlib configured")

print("Step 2: Importing PyQt5...")
from PyQt5.QtCore import Qt, QCoreApplication
from PyQt5 import QtCore, QtWidgets
print("   ✓ PyQt5 imported")

if sys.platform == 'darwin':
    QCoreApplication.setAttribute(Qt.AA_ShareOpenGLContexts, True)

print("Step 3: Creating QApplication...")
app = QtWidgets.QApplication(sys.argv)
app.setStyle('Fusion')
print("   ✓ QApplication created")

print("Step 4: Importing MainController...")
sys.path.insert(0, os.path.dirname(__file__))
from control import MainController
print("   ✓ MainController imported")

print("Step 5: Creating MainController instance...")
controller = MainController()
print("   ✓ Controller created")

print("Step 6: Calling show_window()...")
controller.show_window()
print("   ✓ show_window() called")

print("Step 7: Starting event loop...")
print("=" * 60)
sys.exit(app.exec_())