from qtpy import QtWidgets, QtCore
import os.path
import re
import glob
import fnmatch
from .fileutils import extract_extension

_FILECHOOSER_JCPDS_FILTER_SETTING = "filechooser/jcpds_filter_mode"


class _HideParamFoldersProxyModel(QtCore.QSortFilterProxyModel):
    JCPDS_FILTER_ALL = "all"
    JCPDS_FILTER_WITH = "with_jcpds"
    JCPDS_FILTER_WITHOUT = "without_jcpds"

    def __init__(self, *args, **kwargs):
        super(_HideParamFoldersProxyModel, self).__init__(*args, **kwargs)
        self._hide_param_dirs = True
        self._jcpds_filter_mode = self.JCPDS_FILTER_ALL

    @staticmethod
    def _natural_sort_key(text):
        parts = re.split(r"(\d+)", str(text or "").lower())
        key = []
        for part in parts:
            if not part:
                continue
            if part.isdigit():
                key.append((0, int(part)))
            else:
                key.append((1, part))
        return tuple(key)

    def set_hide_param_dirs(self, hide_param_dirs):
        self._hide_param_dirs = bool(hide_param_dirs)
        self.invalidateFilter()

    def set_jcpds_filter_mode(self, mode):
        valid_modes = {
            self.JCPDS_FILTER_ALL,
            self.JCPDS_FILTER_WITH,
            self.JCPDS_FILTER_WITHOUT,
        }
        self._jcpds_filter_mode = mode if mode in valid_modes else self.JCPDS_FILTER_ALL
        self.invalidateFilter()

    def _chi_has_jcpds(self, file_path):
        path, filename = os.path.split(file_path)
        stem = os.path.splitext(filename)[0]
        param_dir = os.path.join(path, stem + "-param")
        jcpds_file = os.path.join(param_dir, "pkpo_jcpds.json")
        return os.path.exists(jcpds_file)

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

        if self._jcpds_filter_mode != self.JCPDS_FILTER_ALL:
            if is_dir:
                # Param folder hiding is controlled by the Hide *-param checkbox
                if self._hide_param_dirs:
                    folder_name = str(model.fileName(index) or "")
                    if folder_name.lower().endswith("-param"):
                        return False
                # Allow non-param directories for navigation
                return True

            # In JCPDS filter modes, only CHI files participate.
            file_path = model.filePath(index)
            if not file_path.lower().endswith('.chi'):
                return False
            has_jcpds = self._chi_has_jcpds(file_path)
            if self._jcpds_filter_mode == self.JCPDS_FILTER_WITH:
                return has_jcpds
            if self._jcpds_filter_mode == self.JCPDS_FILTER_WITHOUT:
                return not has_jcpds

        if not is_dir:
            return True

        if not self._hide_param_dirs:
            return True

        folder_name = str(model.fileName(index) or "")
        return not folder_name.lower().endswith("-param")

    def lessThan(self, left, right):
        model = self.sourceModel()
        if (model is not None) and (left.column() == 0) and (right.column() == 0):
            try:
                left_name = model.fileName(left)
                right_name = model.fileName(right)
            except AttributeError:
                left_name = left.data(QtCore.Qt.DisplayRole)
                right_name = right.data(QtCore.Qt.DisplayRole)
            return self._natural_sort_key(left_name) < self._natural_sort_key(right_name)
        return super(_HideParamFoldersProxyModel, self).lessThan(left, right)


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


def _attach_jcpds_filter_combo(dialog, proxy, default_mode=None):
    combo = QtWidgets.QComboBox(dialog)
    combo.addItem("All CHI files", _HideParamFoldersProxyModel.JCPDS_FILTER_ALL)
    combo.addItem("CHI with JCPDS", _HideParamFoldersProxyModel.JCPDS_FILTER_WITH)
    combo.addItem("CHI without JCPDS", _HideParamFoldersProxyModel.JCPDS_FILTER_WITHOUT)

    if default_mode is not None:
        idx = combo.findData(default_mode)
        if idx >= 0:
            combo.setCurrentIndex(idx)

    combo.currentIndexChanged.connect(
        lambda idx: proxy.set_jcpds_filter_mode(combo.itemData(idx)))

    layout = dialog.layout()
    if isinstance(layout, QtWidgets.QGridLayout):
        row = layout.rowCount()
        layout.addWidget(combo, row, 0, 1, layout.columnCount())
    elif layout is not None:
        layout.addWidget(combo)

    return combo


def _resolve_jcpds_filter_mode(default_jcpds_only=False, default_jcpds_filter_mode=None):
    if default_jcpds_filter_mode is not None:
        return default_jcpds_filter_mode
    if default_jcpds_only:
        return _HideParamFoldersProxyModel.JCPDS_FILTER_WITH
    return _HideParamFoldersProxyModel.JCPDS_FILTER_ALL


def _valid_jcpds_filter_mode(mode):
    valid_modes = {
        _HideParamFoldersProxyModel.JCPDS_FILTER_ALL,
        _HideParamFoldersProxyModel.JCPDS_FILTER_WITH,
        _HideParamFoldersProxyModel.JCPDS_FILTER_WITHOUT,
    }
    return mode if mode in valid_modes else _HideParamFoldersProxyModel.JCPDS_FILTER_ALL


def _file_filter_includes_chi(file_filter):
    return ".chi" in str(file_filter or "").lower()


def _read_saved_jcpds_filter_mode(default_mode):
    settings = QtCore.QSettings("DS", "PeakPo")
    mode = str(settings.value(_FILECHOOSER_JCPDS_FILTER_SETTING, default_mode))
    return _valid_jcpds_filter_mode(mode)


def _write_saved_jcpds_filter_mode(mode):
    settings = QtCore.QSettings("DS", "PeakPo")
    settings.setValue(
        _FILECHOOSER_JCPDS_FILTER_SETTING,
        _valid_jcpds_filter_mode(str(mode)))


def _exec_dialog(dialog):
    exec_fn = getattr(dialog, "exec", None)
    if exec_fn is None:
        exec_fn = dialog.exec_
    return bool(exec_fn())


def _dispose_file_dialog(dialog):
    """Destroy a file dialog and its QFileSystemModel worker immediately."""
    if dialog is None:
        return
    try:
        dialog.close()
    except Exception:
        pass
    try:
        dialog.setParent(None)
    except Exception:
        pass
    try:
        dialog.deleteLater()
    except Exception:
        return

    app = QtCore.QCoreApplication.instance()
    if app is None:
        return
    deferred_delete = getattr(QtCore.QEvent, "DeferredDelete", None)
    if deferred_delete is None:
        event_type = getattr(QtCore.QEvent, "Type", None)
        if event_type is not None:
            deferred_delete = getattr(event_type, "DeferredDelete", None)
    try:
        if deferred_delete is not None:
            QtCore.QCoreApplication.sendPostedEvents(None, deferred_delete)
        app.processEvents()
    except Exception:
        pass


def _extract_name_filter_patterns(name_filter):
    # Example: "CHI files (*.chi *.dat)"
    m = re.search(r"\(([^)]*)\)", str(name_filter or ""))
    if not m:
        return []
    parts = [p.strip() for p in m.group(1).split() if p.strip()]
    return [p for p in parts if p != "*"]


def _matches_name_filter(path, patterns):
    if not patterns:
        return True
    base = os.path.basename(path)
    return any(fnmatch.fnmatch(base, pat) for pat in patterns)


def _expand_selected_files(dialog, selected_files):
    """
    Expand wildcard tokens typed into the filename field (e.g., map2_*).
    """
    if not selected_files:
        return []

    current_dir = dialog.directory().absolutePath()
    patterns = _extract_name_filter_patterns(dialog.selectedNameFilter())
    out = []
    seen = set()
    for item in selected_files:
        token = str(item or "").strip()
        if not token:
            continue
        has_glob = any(ch in token for ch in ("*", "?", "["))
        if has_glob:
            query = token if os.path.isabs(token) else os.path.join(current_dir, token)
            for match in sorted(glob.glob(query)):
                if (not os.path.isfile(match)) or (not _matches_name_filter(match, patterns)):
                    continue
                if match not in seen:
                    seen.add(match)
                    out.append(match)
            continue
        path = token if os.path.isabs(token) else os.path.join(current_dir, token)
        if os.path.isfile(path) and _matches_name_filter(path, patterns):
            if path not in seen:
                seen.add(path)
                out.append(path)
    return out


class _OpenFileDialog(QtWidgets.QFileDialog):
    def __init__(self, *args, **kwargs):
        super(_OpenFileDialog, self).__init__(*args, **kwargs)
        self._expanded_selected_files = None
        self._persist_jcpds_filter_mode = False
        self._jcpds_filter_combo = None

    def _save_persistent_state(self):
        if not self._persist_jcpds_filter_mode:
            return
        combo = self._jcpds_filter_combo
        if combo is None:
            return
        _write_saved_jcpds_filter_mode(combo.currentData())

    def accept(self):
        if self.fileMode() == QtWidgets.QFileDialog.ExistingFiles:
            expanded = _expand_selected_files(self, self.selectedFiles())
            if expanded:
                self._expanded_selected_files = expanded
                self._save_persistent_state()
                self.done(QtWidgets.QDialog.Accepted)
                return
        self._save_persistent_state()
        super(_OpenFileDialog, self).accept()


def _add_macos_volumes_sidebar_url(dialog):
    import sys
    if sys.platform != 'darwin':
        return
    if not os.path.isdir("/Volumes"):
        return

    volumes_url = QtCore.QUrl.fromLocalFile("/Volumes")
    try:
        urls = list(dialog.sidebarUrls())
    except AttributeError:
        return
    if volumes_url not in urls:
        dialog.setSidebarUrls(urls + [volumes_url])


def _build_open_dialog(
        obj, title, directory, file_filter, file_mode,
        default_hide_param_dirs=False,
        default_jcpds_only=False,
        default_jcpds_filter_mode=None):
    dialog = _OpenFileDialog(obj, title, directory, file_filter)
    dialog.setFileMode(file_mode)
    dialog.setOption(QtWidgets.QFileDialog.DontUseNativeDialog, True)
    jcpds_filter_mode = _resolve_jcpds_filter_mode(
        default_jcpds_only=default_jcpds_only,
        default_jcpds_filter_mode=default_jcpds_filter_mode)
    remember_jcpds_filter_mode = (
        default_jcpds_filter_mode is None and
        _file_filter_includes_chi(file_filter))
    if remember_jcpds_filter_mode:
        jcpds_filter_mode = _read_saved_jcpds_filter_mode(jcpds_filter_mode)

    proxy = _HideParamFoldersProxyModel(dialog)
    proxy.setRecursiveFilteringEnabled(False)
    dialog.setProxyModel(proxy)
    _add_macos_volumes_sidebar_url(dialog)
    _attach_hide_param_checkbox(
        dialog, proxy, default_checked=default_hide_param_dirs)
    combo = _attach_jcpds_filter_combo(
        dialog, proxy, default_mode=jcpds_filter_mode)
    dialog._persist_jcpds_filter_mode = remember_jcpds_filter_mode
    dialog._jcpds_filter_combo = combo
    proxy.set_hide_param_dirs(default_hide_param_dirs)
    proxy.set_jcpds_filter_mode(jcpds_filter_mode)

    return dialog


def dialog_openfile_hide_param_dirs(
        obj, title, directory, file_filter, default_hide_param_dirs=False,
        default_jcpds_only=False,
        default_jcpds_filter_mode=None):
    dialog = _build_open_dialog(
        obj, title, directory, file_filter,
        QtWidgets.QFileDialog.ExistingFile,
        default_hide_param_dirs=default_hide_param_dirs,
        default_jcpds_only=default_jcpds_only,
        default_jcpds_filter_mode=default_jcpds_filter_mode)
    try:
        if _exec_dialog(dialog):
            files = dialog.selectedFiles()
            return (files[0] if files else ""), dialog.selectedNameFilter()
        return "", ""
    finally:
        _dispose_file_dialog(dialog)


def dialog_openfiles_hide_param_dirs(
        obj, title, directory, file_filter, default_hide_param_dirs=False,
        default_jcpds_only=False,
        default_jcpds_filter_mode=None):
    dialog = _build_open_dialog(
        obj, title, directory, file_filter,
        QtWidgets.QFileDialog.ExistingFiles,
        default_hide_param_dirs=default_hide_param_dirs,
        default_jcpds_only=default_jcpds_only,
        default_jcpds_filter_mode=default_jcpds_filter_mode)
    try:
        if _exec_dialog(dialog):
            files = getattr(dialog, "_expanded_selected_files", None)
            if files is None:
                files = _expand_selected_files(dialog, dialog.selectedFiles())
            return files, dialog.selectedNameFilter()
        return [], ""
    finally:
        _dispose_file_dialog(dialog)


def dialog_existing_directory_hide_param_dirs(
        obj, title, directory, default_hide_param_dirs=False):
    dialog = _build_open_dialog(
        obj, title, directory, "",
        QtWidgets.QFileDialog.Directory,
        default_hide_param_dirs=default_hide_param_dirs)
    dialog.setOption(QtWidgets.QFileDialog.ShowDirsOnly, True)
    try:
        if _exec_dialog(dialog):
            files = dialog.selectedFiles()
            return files[0] if files else ""
        return ""
    finally:
        _dispose_file_dialog(dialog)


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
