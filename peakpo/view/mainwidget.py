import os
from PyQt5 import QtWidgets
from .qtd import Ui_MainWindow
from utils import SpinBoxFixStyle
exec(open(os.path.join(os.path.curdir, 'version.py')).read())
exec(open(os.path.join(os.path.curdir, 'citation.py')).read())


class MainWindow(QtWidgets.QMainWindow, Ui_MainWindow):
    """
    Main window
    """

    def __init__(self, parent=None):
        # initialization of the superclass
        super(MainWindow, self).__init__(parent)
        self.setupUi(self)  # setup the GUI --> function generated by pyuic5
        self.setWindowTitle("PeakPo ver. " + str(__version__))
        self.about()
        self.shortcutkeys()
        #
        self.build_ui()
        self.connect_channel()
        # the two lines needs to be considred for move from this widget file
        self.actionCiting_PeakPo.triggered.connect(self.about)
        self.actionShortcut_keys.triggered.connect(self.shortcutkeys)

    def build_ui(self):
        # self.pushButton_MakeBasePtn.setEnabled(False)
        self.doubleSpinBox_Pressure.setKeyboardTracking(False)
        self.doubleSpinBox_Pressure.setStyle(SpinBoxFixStyle())
        self.doubleSpinBox_Temperature.setKeyboardTracking(False)
        self.doubleSpinBox_Temperature.setStyle(SpinBoxFixStyle())
        self.doubleSpinBox_WaterfallGaps.setKeyboardTracking(False)
        self.doubleSpinBox_WaterfallGaps.setStyle(SpinBoxFixStyle())
        self.spinBox_BGParam0.setKeyboardTracking(False)
        self.spinBox_BGParam1.setKeyboardTracking(False)
        self.spinBox_BGParam2.setKeyboardTracking(False)
        self.spinBox_BGParam0.setStyle(SpinBoxFixStyle())
        self.spinBox_BGParam1.setStyle(SpinBoxFixStyle())
        self.spinBox_BGParam2.setStyle(SpinBoxFixStyle())
        self.doubleSpinBox_Background_ROI_max.setKeyboardTracking(False)
        self.doubleSpinBox_Background_ROI_min.setKeyboardTracking(False)
        self.doubleSpinBox_Background_ROI_max.setStyle(SpinBoxFixStyle())
        self.doubleSpinBox_Background_ROI_min.setStyle(SpinBoxFixStyle())
        self.doubleSpinBox_SetWavelength.setKeyboardTracking(False)
        self.doubleSpinBox_SetWavelength.setStyle(SpinBoxFixStyle())
        # navigation toolbar modification
        self.ntb_WholePtn = QtWidgets.QPushButton()
        self.ntb_WholePtn.setText("ZoomOut")
        self.mpl.ntb.addWidget(self.ntb_WholePtn)
        """
        self.ntb_toPkFt = QtWidgets.QPushButton()
        self.ntb_toPkFt.setText("toPkFt")
        self.mpl.ntb.addWidget(self.ntb_toPkFt)
        self.ntb_fromPkFt = QtWidgets.QPushButton()
        self.ntb_fromPkFt.setText("fromPkFt")
        self.mpl.ntb.addWidget(self.ntb_fromPkFt)
        self.ntb_ResetY = QtWidgets.QCheckBox()
        self.ntb_ResetY.setCheckable(True)
        self.ntb_ResetY.setChecked(False)
        self.ntb_ResetY.setText("AutoYScale")
        self.mpl.ntb.addWidget(self.ntb_ResetY)
        self.ntb_Bgsub = QtWidgets.QCheckBox()
        self.ntb_Bgsub.setCheckable(True)
        self.ntb_Bgsub.setChecked(True)
        self.ntb_Bgsub.setText("BgSub")
        self.mpl.ntb.addWidget(self.ntb_Bgsub)
        self.ntb_NightView = QtWidgets.QCheckBox()
        self.ntb_NightView.setCheckable(True)
        self.ntb_NightView.setChecked(True)
        self.ntb_NightView.setText("Night")
        self.mpl.ntb.addWidget(self.ntb_NightView)
        """

    def closeEvent(self, event):
        self.deleteLater()
        event.accept()

    def connect_channel(self):
        self.pushButton_RoomT.clicked.connect(
            lambda: self.set_temperature(300))
        self.pushButton_1000K.clicked.connect(
            lambda: self.set_temperature(1000))
        self.pushButton_1500K.clicked.connect(
            lambda: self.set_temperature(1500))
        self.pushButton_2000K.clicked.connect(
            lambda: self.set_temperature(2000))
        self.pushButton_2500K.clicked.connect(
            lambda: self.set_temperature(2500))
        self.pushButton_3000K.clicked.connect(
            lambda: self.set_temperature(3000))
        self.pushButton_3500K.clicked.connect(
            lambda: self.set_temperature(3500))
        self.pushButton_4000K.clicked.connect(
            lambda: self.set_temperature(4000))
        self.pushButton_4500K.clicked.connect(
            lambda: self.set_temperature(4500))
        self.pushButton_5000K.clicked.connect(
            lambda: self.set_temperature(5000))
        self.radioButton_P01.clicked.connect(self.set_pstep)
        self.radioButton_P1.clicked.connect(self.set_pstep)
        self.radioButton_P10.clicked.connect(self.set_pstep)
        self.radioButton_P100.clicked.connect(self.set_pstep)
        self.radioButton_T1.clicked.connect(self.set_tstep)
        self.radioButton_T10.clicked.connect(self.set_tstep)
        self.radioButton_T100.clicked.connect(self.set_tstep)
        self.radioButton_T1000.clicked.connect(self.set_tstep)

    def set_temperature(self, temperature=None):
        self.doubleSpinBox_Temperature.setValue(temperature)

    def set_pstep(self, value):
        if self.radioButton_P01.isChecked():
            value = 0.1
        elif self.radioButton_P10.isChecked():
            value = 10.
        elif self.radioButton_P100.isChecked():
            value = 100.
        else:
            value = 1.
        self.doubleSpinBox_Pressure.setSingleStep(value)

    def set_tstep(self, value):
        if self.radioButton_T1.isChecked():
            value = 1.
        elif self.radioButton_T10.isChecked():
            value = 10.
        elif self.radioButton_T1000.isChecked():
            value = 1000.
        else:
            value = 100.
        self.doubleSpinBox_Temperature.setSingleStep(value)

    def about(self):
        self.textEdit_about.setText(
            'PeakPo<br><br>' +
            'A Visual Diffraction Analysis Tool<br><br>' +
            'by S.-H. Dan Shim, SHDShim@gmail.com<br>' +
            'Arizona State University<br><br>' +
            'where to find updates: https://github.com/SHDShim/peakpo-v7 <br><br>' +
            'how to cite: ' + str(__citation__) + '<br><br>'
            'WARNING. Use at your own risk. ' +
            'This is a free software and no support is provided.<br>' +
            'You may report bugs or send comments to SHDShim@gmail.com.')

    def shortcutkeys(self):
        self.textEdit_shortcuts.setText(
            '** Shortcut Keys ** <br><br>' +
            'To activate shortcut keys, make sure no mpl buttons are in press. <br>'
            'Save session: s<br>' +
            'Rescale vertical: v<br>' +
            'Whole spectrum: w<br>' +
            'Home or Reset: H or R<br>' +
            'Back: left arrow<br>' +
            'Forward: right arrow<br>' +
            'Pan: p<br>' +
            'Zoom: o<br>' +
            'Peak position read: i<br>' +
            'Constrain pan/zoom to x axis: hold x when panning/zooming<br>' +
            'Constrain pan/zoom to y axis: hold y when panning/zooming<br>' +
            'Preserve aspect ratio: hold CTRL when panning/zooming<br>' +
            'Toggle x scale (log/lin): L or k when mouse is over an axes<br>' +
            'Toggle y scale (log/lin): l when mouse is over an axes<br>')
