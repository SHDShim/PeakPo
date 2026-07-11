import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from qtpy import QtWidgets

from peakpo.view.mainwidget import MainWindow


_APP = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


def test_cake_integration_tables_have_similar_heights():
    window = MainWindow()
    window.resize(1800, 1200)
    window.show()
    window.tabWidget.setCurrentWidget(window.tab_Cake1)
    window.tabWidget_2.setCurrentWidget(window.tabWidget_2Page2)
    _APP.processEvents()

    roi_height = window.tableWidget_DiffImgAzi.height()
    chi_height = window.tableWidget_AziChiList.height()

    window.close()
    _APP.processEvents()

    assert abs(roi_height - chi_height) <= 12
