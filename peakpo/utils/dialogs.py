from qtpy import QtGui, QtWidgets, QtCore
import os.path
from .fileutils import extract_extension


class _HideParamFoldersProxyModel(QtCore.QSortFilterProxyModel):
    def __init__(self, *args, **kwargs):
        super(_HideParamFoldersProxyModel, self).__init__(*args, **kwargs)
        self._hide_param_dirs = True

    def set_hide_param_dirs(self, hide_param_dirs):
        self._hide_param_dirs = bool(hide_param_dirs)
        self.invalidateFilter()

    def filterAcceptsRow(self, source_row, source_parent):
        model = self.sourceModel()
        if model is None:
            return True

        index = model.index(source_row, 0, source_parent)
        if not index.isValid():
            return True

        try:
            is_dir = bool(model.isDir(index))
        except AttributeError:
            is_dir = False
        if not is_dir:
            return True

        if not self._hide_param_dirs:
            return True

        folder_name = str(model.fileName(index) or "")
        return not folder_name.lower().endswith("-param")


def _attach_hide_param_checkbox(dialog, proxy, default_checked=False):
    checkbox = QtWidgets.QCheckBox(
        "Hide *-param folders in file chooser", dialog)
    checkbox.setChecked(bool(default_checked))
    checkbox.toggled.connect(proxy.set_hide_param_dirs)

    layout = dialog.layout()
    if isinstance(layout, QtWidgets.QGridLayout):
        row = layout.rowCount()
        layout.addWidget(checkbox, row, 0, 1, layout.columnCount())
    elif layout is not None:
        layout.addWidget(checkbox)

    return checkbox


def _exec_dialog(dialog):
    exec_fn = getattr(dialog, "exec", None)
    if exec_fn is None:
        exec_fn = dialog.exec_
    return bool(exec_fn())


def _build_open_dialog(
        obj, title, directory, file_filter, file_mode,
        default_hide_param_dirs=False):
    dialog = QtWidgets.QFileDialog(obj, title, directory, file_filter)
    dialog.setFileMode(file_mode)
    dialog.setOption(QtWidgets.QFileDialog.DontUseNativeDialog, True)

    proxy = _HideParamFoldersProxyModel(dialog)
    proxy.setRecursiveFilteringEnabled(False)
    dialog.setProxyModel(proxy)
    _attach_hide_param_checkbox(
        dialog, proxy, default_checked=default_hide_param_dirs)
    proxy.set_hide_param_dirs(default_hide_param_dirs)

    return dialog


def dialog_openfile_hide_param_dirs(
        obj, title, directory, file_filter, default_hide_param_dirs=False):
    dialog = _build_open_dialog(
        obj, title, directory, file_filter,
        QtWidgets.QFileDialog.ExistingFile,
        default_hide_param_dirs=default_hide_param_dirs)
    if _exec_dialog(dialog):
        files = dialog.selectedFiles()
        return (files[0] if files else ""), dialog.selectedNameFilter()
    return "", ""


def dialog_openfiles_hide_param_dirs(
        obj, title, directory, file_filter, default_hide_param_dirs=False):
    dialog = _build_open_dialog(
        obj, title, directory, file_filter,
        QtWidgets.QFileDialog.ExistingFiles,
        default_hide_param_dirs=default_hide_param_dirs)
    if _exec_dialog(dialog):
        return dialog.selectedFiles(), dialog.selectedNameFilter()
    return [], ""


def dialog_existing_directory_hide_param_dirs(
        obj, title, directory, default_hide_param_dirs=False):
    dialog = _build_open_dialog(
        obj, title, directory, "",
        QtWidgets.QFileDialog.Directory,
        default_hide_param_dirs=default_hide_param_dirs)
    dialog.setOption(QtWidgets.QFileDialog.ShowDirsOnly, True)
    if _exec_dialog(dialog):
        files = dialog.selectedFiles()
        return files[0] if files else ""
    return ""


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
