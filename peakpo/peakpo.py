import sys
from PyQt5 import QtWidgets
import qdarkstyle
from maincontroller import MainController

app = QtWidgets.QApplication(sys.argv)
app.setStyleSheet(qdarkstyle.load_stylesheet_pyqt5())
# app.setStyleSheet('fusion')
controller = MainController()
controller.show_window()
ret = app.exec_()
sys.exit(ret)
