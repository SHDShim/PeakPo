import os
import sys

if sys.platform == 'darwin':
    os.environ['QT_MAC_WANTS_LAYER'] = '1'

from PyQt5.QtWidgets import QApplication, QLabel

app = QApplication(sys.argv)
label = QLabel("Hello World")
label.show()
print("✅ Window created successfully")
sys.exit(app.exec_())