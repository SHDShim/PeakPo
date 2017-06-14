from PyQt5 import QtGui, QtWidgets
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
