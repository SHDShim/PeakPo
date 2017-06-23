import sys
from PyQt5 import QtWidgets
import qdarkstyle
#from mainwidget import MainWindow
from maincontroller import MainController

# create the GUI application
app = QtWidgets.QApplication(sys.argv)
# dmw = MainWindow()
app.setStyleSheet(qdarkstyle.load_stylesheet_pyqt5())
# app.setStyleSheet('fusion')
# dmw.show()
controller = MainController()
controller.show_window()
# start the Qt main loop execution, exiting from this script
# with the same return code of Qt application
ret = app.exec_()
# dmw.memorize_state()
sys.exit(ret)
# before system save function addition
# sys.exit(app.exec_())
