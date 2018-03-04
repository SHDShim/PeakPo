from PyQt5 import QtGui, QtWidgets, QtCore
import os.path
from .fileutils import extract_extension


def dialog_savefile(obj, default_filename):
    """
    :return: "" if the user choose not to overwrite or save
    """
    extension = extract_extension(default_filename)
    extension_to_search = "(*." + extension + ")"
    reply = QtWidgets.QMessageBox.question(
        obj, 'Question',
        'Do you want to save in default filename, %s ?' % default_filename,
        QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
        QtWidgets.QMessageBox.Yes)
    if reply == QtWidgets.QMessageBox.No:
        new_filename = QtWidgets.QFileDialog.getSaveFileName(
            obj, "Choose different filename.",
            default_filename, extension_to_search)[0]
        return str(new_filename)
    else:
        if os.path.exists(default_filename):
            reply = QtWidgets.QMessageBox.question(
                obj, 'Question',
                'The file already exist.  Do you want to overwrite?',
                QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
                QtWidgets.QMessageBox.No)
            if reply == QtWidgets.QMessageBox.No:
                return ''
            else:
                return default_filename
        else:
            return default_filename


class ErrorMessageBox(QtWidgets.QDialog):
    """
    If possible merge with InformationBox below
    """

    def __init__(self, *args, **kwargs):
        super(ErrorMessageBox, self).__init__(*args, **kwargs)
        self.setWindowTitle("Error report")

        self.text_lbl = QtWidgets.QLabel()
        self.text_lbl.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
        self.scroll_area = QtWidgets.QScrollArea()

        self.scroll_area.setWidget(self.text_lbl)
        self.scroll_area.setWidgetResizable(True)
        self.ok_btn = QtWidgets.QPushButton('OK')

        _layout = QtWidgets.QGridLayout()
        _layout.addWidget(self.scroll_area, 0, 0, 1, 10)
        _layout.addWidget(self.ok_btn, 1, 9)

        self.setLayout(_layout)
        self.ok_btn.clicked.connect(self.close)

    def setText(self, text_str):
        self.text_lbl.setText(text_str)


class InformationBox(QtWidgets.QDialog):
    def __init__(self, title="Information", *args, **kwargs):
        super(InformationBox, self).__init__(*args, **kwargs)
        self.setWindowTitle(title)

        self.text_lbl = QtWidgets.QLabel()
        self.text_lbl.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
        self.scroll_area = QtWidgets.QScrollArea()

        self.scroll_area.setWidget(self.text_lbl)
        self.scroll_area.setWidgetResizable(True)
        self.ok_btn = QtWidgets.QPushButton('OK')

        _layout = QtWidgets.QGridLayout()
        _layout.addWidget(self.scroll_area, 0, 0, 1, 10)
        _layout.addWidget(self.ok_btn, 1, 9)

        self.setLayout(_layout)
        self.ok_btn.clicked.connect(self.close)

    def setText(self, text_str):
        self.text_lbl.setText(text_str)
