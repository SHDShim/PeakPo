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


def test_cake_config_has_readonly_poni_and_summary_tables():
    window = MainWindow()
    window.resize(1800, 1200)
    window.show()
    window.tabWidget.setCurrentWidget(window.tab_Cake1)
    window.tabWidget_2.setCurrentWidget(window.tabWidget_2Page1)
    _APP.processEvents()

    assert window.groupBox_CakePoniTable.title() == "PONI contents"
    assert window.groupBox_CakeSummary.title() == "Cake information"
    assert window.tableWidget_CakePoniInfo.columnCount() == 2
    assert window.tableWidget_CakeSummary.columnCount() == 2
    assert window.tableWidget_CakePoniInfo.editTriggers() == (
        QtWidgets.QAbstractItemView.NoEditTriggers)
    assert window.tableWidget_CakeSummary.editTriggers() == (
        QtWidgets.QAbstractItemView.NoEditTriggers)

    window.close()
    _APP.processEvents()
