import os
import sys
import faulthandler
import signal

# Enable detailed faulthandler output
faulthandler.enable(file=sys.stderr, all_threads=True)

# Register handler for segfault
faulthandler.register(signal.SIGUSR1, file=sys.stderr, all_threads=True)

if sys.platform == 'darwin':
    os.environ['QT_MAC_WANTS_LAYER'] = '1'

print("Step 1: Importing PyQt5.QtCore")
from PyQt5 import QtCore
print("✓ QtCore imported")

print("Step 2: Importing PyQt5.QtWidgets")
from PyQt5 import QtWidgets
print("✓ QtWidgets imported")

print("Step 3: Importing PyQt5.QtGui")
from PyQt5.QtGui import QPalette, QColor
print("✓ QtGui imported")

print("Step 4: Creating QApplication")
app = QtWidgets.QApplication(sys.argv)
print("✓ QApplication created")

print("Step 5: Setting style")
app.setStyle('Fusion')
print("✓ Style set")

print("Step 6: Creating palette")
palette = QPalette()
print("✓ Palette created")

print("Step 7: Setting palette")
app.setPalette(palette)
print("✓ Palette set")

print("\n✅ All steps completed successfully!")
sys.exit(0)