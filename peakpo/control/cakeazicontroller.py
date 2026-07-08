import json
import os

import numpy as np
from qtpy import QtCore, QtWidgets
from matplotlib.widgets import RectangleSelector
import matplotlib.patches as mpatches

from ..model.azimuthal_integration import (
    AZINT_FORMAT,
    default_setup_path,
    format_ranges,
    make_metadata,
    normalize_range,
    normalize_ranges,
    output_dir_for_source,
    provenance_for_chi,
    read_sidecar,
    sidecar_path_for_chi,
    source_label,
    source_ranges_label,
    unique_output_chi_path,
    write_sidecar,
)
from ..utils import (
    dialog_openfile_hide_param_dirs,
    get_temp_dir,
    make_filename,
    writechi,
)
from .cakemakecontroller import CakemakeController
from .mplcontroller import MplController


SETUP_FORMAT = "peakpo-azimuthal-integration-setup"


class CakeAziController(object):

    def __init__(self, model, widget):
        self.model = model
        self.widget = widget
        self.cakemake_ctrl = CakemakeController(self.model, self.widget)
        self.plot_ctrl = MplController(self.model, self.widget)
        self.last_integration_file = None
        self._selector_2d = None
        self._pending_rois = []
        self._pending_roi_artists = []
        self._derived_chi_entries = []
        self._selected_derived_chi_preview = []
        self._selected_derived_chi_path = None
        self._selected_derived_chi_shift = None
        self._selected_derived_chi_table_snapshot = None
        self._syncing_derived_chi_selection = False
        self.base_ptn_ctrl = None
        self.widget._cake_azi_pending_rois = self._pending_rois
        self.widget._cake_azi_selected_rois = self._selected_derived_chi_preview
        self.widget._cake_azi_selected_derived_chi_path = (
            self._selected_derived_chi_path)
        self.widget._cake_azi_selected_derived_chi_shift = (
            self._selected_derived_chi_shift)
        self._configure_ui()
        self.connect_channel()

    def set_helpers(self, base_ptn_ctrl=None):
        self.base_ptn_ctrl = base_ptn_ctrl

    def _configure_ui(self):
        table = self.widget.tableWidget_DiffImgAzi
        table.setColumnCount(5)
        table.setHorizontalHeaderLabels(
            ["Use", "Label", "Azi min", "Azi max", "Note"])
        table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        table.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        table.verticalHeader().setVisible(True)
        try:
            table.verticalHeader().setDefaultSectionSize(28)
            table.verticalHeader().setMinimumWidth(44)
        except Exception:
            pass
        header = table.horizontalHeader()
        header.setStretchLastSection(True)

        self.widget.pushButton_AddAzi.setText("Add ROI")
        self.widget.pushButton_AddAzi.setToolTip(
            "Add the pending Cake ROI azimuth range(s) to the table.")
        self.widget.pushButton_RemoveAzi.setText("Remove selected")
        self.widget.pushButton_RemoveAzi.setToolTip(
            "Remove highlighted azimuth ranges from the list.")
        self.widget.pushButton_ClearAziList.setText("Clear ranges")
        self.widget.pushButton_ClearAziList.setToolTip(
            "Clear all azimuth ranges from the list.")
        self.widget.pushButton_HighlightSelectedMarker.setCheckable(True)
        self._update_roi_button_state(False)
        self.widget.pushButton_InvertCakeBoxes.setText("Integrate only")
        self.widget.pushButton_InvertCakeBoxes.setToolTip(
            "Create the azimuth-integrated CHI without opening it as the active pattern.")
        self.widget.pushButton_IntegrateCake.setText("Integrate and open")
        self.widget.pushButton_IntegrateCake.setToolTip(
            "Create the azimuth-integrated CHI and open it for peak fitting.")
        self._configure_derived_chi_ui()

    def _configure_derived_chi_ui(self):
        table = getattr(self.widget, "tableWidget_AziChiList", None)
        if table is not None:
            table.setColumnCount(5)
            table.setHorizontalHeaderLabels(
                ["Active", "Type", "Label", "Azimuth ranges", "CHI file"])
            table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
            table.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
            table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
            table.verticalHeader().setVisible(True)
            try:
                table.verticalHeader().setDefaultSectionSize(24)
                table.verticalHeader().setMinimumWidth(44)
            except Exception:
                pass
            table.horizontalHeader().setStretchLastSection(True)
            sel_model = table.selectionModel()
            if sel_model is not None:
                sel_model.selectionChanged.connect(
                    self._on_derived_chi_selection_changed)
        self.refresh_derived_chi_ui()

    def connect_channel(self):
        """
        The primary Integrate and open button is connected in maincontroller.py.
        """
        self.widget.pushButton_AddAzi.clicked.connect(self._add_azi_to_list)
        self.widget.pushButton_RemoveAzi.clicked.connect(
            self._remove_azi_from_list)
        self.widget.pushButton_ClearAziList.clicked.connect(
            self._clear_azilist)
        self.widget.pushButton_InvertCakeBoxes.clicked.connect(
            self._integrate_only_clicked)
        self.widget.pushButton_HighlightSelectedMarker.clicked.connect(
            self._arm_roi_selection)
        self.widget.tableWidget_DiffImgAzi.itemSelectionChanged.connect(
            self._apply_changes_to_graph)
        if hasattr(self.widget, "pushButton_OpenSelectedAziChi"):
            self.widget.pushButton_OpenSelectedAziChi.clicked.connect(
                self._open_selected_azimuthal_chi)
        if hasattr(self.widget, "pushButton_OpenFullAziChi"):
            self.widget.pushButton_OpenFullAziChi.clicked.connect(
                self._open_full_azimuth_chi)
        if hasattr(self.widget, "pushButton_RemoveSelectedAziChi"):
            self.widget.pushButton_RemoveSelectedAziChi.clicked.connect(
                self._remove_selected_azimuthal_chi)
        if hasattr(self.widget, "pushButton_RefreshAziChiList"):
            self.widget.pushButton_RefreshAziChiList.clicked.connect(
                self.refresh_derived_chi_ui)
        table = getattr(self.widget, "tableWidget_AziChiList", None)
        if table is not None:
            table.itemSelectionChanged.connect(
                self._update_remove_azimuthal_chi_button)

    def _is_cake_tab_active(self):
        return hasattr(self.widget, "tab_Cake1") and \
            self.widget.tabWidget.currentWidget() == self.widget.tab_Cake1

    def _set_status(self, msg):
        text = str(msg or "")
        if hasattr(self.widget, "label_PlotHelp"):
            self.widget.label_PlotHelp.setText(text)
            self.widget.label_PlotHelp.setToolTip(text)

    def _update_roi_button_state(self, active):
        button = getattr(self.widget, "pushButton_HighlightSelectedMarker", None)
        if button is None:
            return
        button.setChecked(bool(active))
        if active:
            button.setText("ROI ON")
            button.setStyleSheet(
                "QPushButton { background-color: #d6a800; color: #1f1f1f; "
                "border: 1px solid #b8860b; }")
            button.setToolTip(
                "ROI selection is active. Draw one or more Cake ROIs, then click Add ROI.")
        else:
            button.setText("Set ROI")
            button.setStyleSheet(
                "QPushButton { background-color: #444444; color: #f0f0f0; "
                "border: 1px solid #d6a800; }"
                "QPushButton:hover { background-color: #505050; }"
                "QPushButton:pressed { background-color: #383838; }")
            button.setToolTip("Click to draw azimuthal ROI range(s) on the Cake plot.")

    def _selector_is_active(self, selector):
        if selector is None:
            return False
        get_active = getattr(selector, "get_active", None)
        if callable(get_active):
            return bool(get_active())
        return bool(getattr(selector, "active", False))

    def is_roi_selection_active(self):
        return self._selector_is_active(self._selector_2d)

    def deactivate_interactions(self):
        self._disable_roi_selector()

    def _arm_roi_selection(self):
        if not self._is_cake_tab_active():
            self._set_status("Open Cake tab first.")
            self._update_roi_button_state(False)
            return
        if not self.widget.checkBox_ShowCake.isChecked() or \
                not hasattr(self.widget.mpl.canvas, "ax_cake"):
            QtWidgets.QMessageBox.warning(
                self.widget, "Warning",
                "Show the Cake plot before selecting an azimuthal ROI.")
            self._update_roi_button_state(False)
            return
        if self.is_roi_selection_active():
            self.deactivate_interactions()
            self._set_status("Cake ROI selection canceled.")
            return
        self._disable_roi_selector()
        self._update_roi_button_state(True)
        self._selector_2d = self._make_rectangle_selector(
            self.widget.mpl.canvas.ax_cake,
            self._on_roi_2d_selected,
        )
        self._set_status(
            "Draw one or more Cake ROIs, then click Add ROI to add them to the table.")

    def _make_rectangle_selector(self, axes, callback):
        common_kwargs = {
            "useblit": True,
            "button": [1],
            "interactive": False,
            "drag_from_anywhere": False,
        }
        props = {
            "facecolor": "red",
            "edgecolor": "red",
            "alpha": 0.20,
            "fill": True,
            "linewidth": 1.2,
        }
        try:
            return RectangleSelector(
                axes, callback, props=props, **common_kwargs)
        except TypeError:
            return RectangleSelector(
                axes, callback, rectprops=props, **common_kwargs)

    def _disable_roi_selector(self):
        if self._selector_2d is not None:
            try:
                self._selector_2d.set_active(False)
            except Exception:
                pass
            self._release_selector_widgetlock(self._selector_2d)
            try:
                self._selector_2d.disconnect_events()
            except Exception:
                pass
            self._selector_2d = None
        self._update_roi_button_state(False)

    def _release_selector_widgetlock(self, selector):
        try:
            lock = self.widget.mpl.canvas.widgetlock
            if not lock.available(selector):
                lock.release(selector)
        except Exception:
            pass

    def _on_roi_2d_selected(self, eclick, erelease):
        if (eclick.ydata is None) or (erelease.ydata is None):
            return
        ymin = min(float(eclick.ydata), float(erelease.ydata))
        ymax = max(float(eclick.ydata), float(erelease.ydata))
        if ymax <= ymin:
            return
        idx = len(self._pending_rois) + 1
        self._pending_rois.append({
            "use": True,
            "label": f"ROI {idx}",
            "azi_min": ymin,
            "azi_max": ymax,
            "note": "pending ROI",
        })
        self.widget._cake_azi_pending_rois = self._pending_rois
        self._set_status(
            f"Cake ROI {idx}: azimuth [{ymin:.3f}, {ymax:.3f}]. "
            "Draw another ROI or click Add ROI.")
        self.refresh_roi_overlays()

    def _clear_pending_rois(self):
        self._pending_rois[:] = []
        self.widget._cake_azi_pending_rois = self._pending_rois
        self._clear_pending_roi_overlays()

    def _clear_pending_roi_overlays(self):
        changed = False
        for artist in self._pending_roi_artists:
            try:
                artist.remove()
                changed = True
            except Exception:
                pass
        self._pending_roi_artists = []
        if changed:
            try:
                self.widget.mpl.canvas.draw_idle()
            except Exception:
                pass

    def refresh_roi_overlays(self):
        self._clear_pending_roi_overlays()
        if not self._pending_rois:
            return
        if not self.widget.checkBox_ShowCake.isChecked() or \
                not hasattr(self.widget.mpl.canvas, "ax_cake"):
            return
        try:
            ax = self.widget.mpl.canvas.ax_cake
            x0, x1 = ax.get_xlim()
            xmin = min(x0, x1)
            xmax = max(x0, x1)
            for idx, roi in enumerate(self._pending_rois, start=1):
                ymin = float(roi["azi_min"])
                ymax = float(roi["azi_max"])
                rect = mpatches.Rectangle(
                    (xmin, ymin),
                    xmax - xmin,
                    ymax - ymin,
                    facecolor="red",
                    edgecolor="red",
                    alpha=0.20,
                    linewidth=1.2,
                )
                ax.add_patch(rect)
                self._pending_roi_artists.append(rect)
                text = ax.text(
                    xmax,
                    ymax,
                    f"ROI {idx}",
                    color="red",
                    ha="right",
                    va="bottom",
                )
                self._pending_roi_artists.append(text)
            self.widget.mpl.canvas.draw_idle()
        except Exception:
            self._pending_roi_artists = []

    def _base_chi_filename(self):
        if not self.model.base_ptn_exist():
            return None
        return self.model.get_base_ptn_filename()

    def _same_path(self, path_a, path_b):
        if not path_a or not path_b:
            return False
        return os.path.normcase(os.path.abspath(path_a)) == \
            os.path.normcase(os.path.abspath(path_b))

    def _current_provenance(self):
        getter = getattr(self.model, "get_active_pattern_provenance", None)
        if callable(getter):
            provenance = getter()
            if isinstance(provenance, dict):
                return provenance
        current_chi = self._base_chi_filename()
        if current_chi is None:
            return {}
        return provenance_for_chi(current_chi)

    def _current_source_chi(self):
        current_chi = self._base_chi_filename()
        if current_chi is not None:
            return os.path.abspath(current_chi)
        provenance = self._current_provenance()
        source_chi = provenance.get("source_chi")
        if provenance.get("source_kind") == "azimuthal_integration" and source_chi:
            return os.path.abspath(source_chi)
        return None

    def _display_chi_filename(self):
        getter = getattr(self.model, "get_display_ptn_filename", None)
        if callable(getter):
            filename = getter()
            if filename:
                return filename
        return self._base_chi_filename()

    def _readonly_item(self, text, tooltip=""):
        item = QtWidgets.QTableWidgetItem(str(text))
        item.setFlags(QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsSelectable)
        if tooltip:
            item.setToolTip(str(tooltip))
        return item

    def _set_current_chi_status(self):
        line = getattr(self.widget, "lineEdit_CurrentAziChiStatus", None)
        if line is None:
            return
        current_chi = self._display_chi_filename()
        if current_chi is None:
            line.setText("Current: no CHI loaded")
            line.setToolTip("")
            line.setStyleSheet("")
            return
        provenance = self._current_provenance()
        label = source_label(provenance)
        ranges = source_ranges_label(provenance)
        basename = os.path.basename(current_chi)
        if provenance.get("source_kind") == "azimuthal_integration":
            text = f"Current: {label}"
            if ranges:
                text += f" | {ranges}"
            text += f" | {basename}"
            source_chi = provenance.get("source_chi", "")
            tooltip = f"Displayed derived CHI: {current_chi}\nFull-azimuth source: {source_chi}"
            line.setStyleSheet(
                "QLineEdit { border: 1px solid #d6a800; color: #ffd76a; }")
        else:
            text = f"Current: Full azi CHI | {basename}"
            tooltip = f"Full-azimuth CHI: {current_chi}"
            line.setStyleSheet("")
        line.setText(text)
        line.setToolTip(tooltip)

    def _derived_chi_sidecar_paths(self, source_chi):
        if not source_chi:
            return []
        output_dir = output_dir_for_source(source_chi)
        if not os.path.isdir(output_dir):
            return []
        paths = []
        for name in os.listdir(output_dir):
            if name.endswith(".azint.json"):
                paths.append(os.path.join(output_dir, name))
        return sorted(paths)

    def _collect_derived_chi_entries(self):
        source_chi = self._current_source_chi()
        if source_chi is None:
            return []
        entries = [{
            "kind": "full",
            "type": "Full azi",
            "label": os.path.basename(source_chi),
            "ranges": "",
            "chi_path": os.path.abspath(source_chi),
            "source_chi": os.path.abspath(source_chi),
            "created_at": "",
            "azimuth_ranges": [],
            "azimuth_shift": None,
        }]
        for sidecar_path in self._derived_chi_sidecar_paths(source_chi):
            chi_path = sidecar_path[:-len(".azint.json")] + ".chi"
            if not os.path.exists(chi_path):
                continue
            metadata = read_sidecar(chi_path)
            if metadata is None:
                continue
            metadata_source = metadata.get("source_chi", "")
            if metadata_source and not self._same_path(metadata_source, source_chi):
                if os.path.basename(metadata_source) != os.path.basename(source_chi):
                    continue
            label = str(metadata.get("label", "") or "").strip()
            if not label:
                label = os.path.splitext(os.path.basename(chi_path))[0]
            entries.append({
                "kind": "derived",
                "type": "Azi-derived",
                "label": label,
                "ranges": format_ranges(
                    metadata.get("azimuth_ranges", []), precision=1),
                "azimuth_ranges": normalize_ranges(
                    metadata.get("azimuth_ranges", [])),
                "chi_path": os.path.abspath(chi_path),
                "source_chi": os.path.abspath(source_chi),
                "created_at": str(metadata.get("created_at", "")),
                "azimuth_shift": metadata.get("azimuth_shift"),
            })
        return [entries[0]] + sorted(
            entries[1:], key=lambda e: (e.get("created_at", ""), e["chi_path"]))

    def _set_selected_derived_chi_preview(self, entry):
        if entry is None or entry.get("kind") != "derived":
            self.clear_selected_derived_chi_preview(restore_table=False)
            return

        azimuth_ranges = normalize_ranges(entry.get("azimuth_ranges", []))
        if self._selected_derived_chi_table_snapshot is None:
            snapshot = self._read_azilist(checked_only=False, warn=False)
            if snapshot:
                self._selected_derived_chi_table_snapshot = snapshot
        self._selected_derived_chi_preview[:] = azimuth_ranges
        self._selected_derived_chi_path = entry.get("chi_path")
        self._selected_derived_chi_shift = entry.get("azimuth_shift")
        self.widget._cake_azi_selected_rois = self._selected_derived_chi_preview
        self.widget._cake_azi_selected_derived_chi_path = self._selected_derived_chi_path
        self.widget._cake_azi_selected_derived_chi_shift = self._selected_derived_chi_shift
        if azimuth_ranges:
            self._post_to_table(azimuth_ranges, clear=True)
        self._set_status(
            f"Previewing ROI ranges from {entry.get('label', 'selected derived CHI')}. "
            "Use Open selected to switch the active CHI.")
        self._apply_changes_to_graph()

    def clear_selected_derived_chi_preview(self, restore_table=False):
        if self._selected_derived_chi_table_snapshot is not None:
            snapshot = self._selected_derived_chi_table_snapshot
            self._selected_derived_chi_table_snapshot = None
            if restore_table:
                self._post_to_table(snapshot, clear=True)
        if hasattr(self.widget, "tableWidget_DiffImgAzi") and not restore_table:
            self.widget.tableWidget_DiffImgAzi.setRowCount(0)
        self._selected_derived_chi_preview[:] = []
        self._selected_derived_chi_path = None
        self._selected_derived_chi_shift = None
        self.widget._cake_azi_selected_rois = self._selected_derived_chi_preview
        self.widget._cake_azi_selected_derived_chi_path = None
        self.widget._cake_azi_selected_derived_chi_shift = None
        self._apply_changes_to_graph()

    def _on_derived_chi_selection_changed(self, *_args):
        if self._syncing_derived_chi_selection:
            return
        entry = self._selected_azimuthal_chi_entry()
        self._set_selected_derived_chi_preview(entry)

    def refresh_derived_chi_ui(self, select_path=None):
        self._set_current_chi_status()
        table = getattr(self.widget, "tableWidget_AziChiList", None)
        if table is None:
            return
        current_chi = self._display_chi_filename()
        entries = self._collect_derived_chi_entries()
        self._derived_chi_entries = entries

        old_state = table.blockSignals(True)
        try:
            table.clearContents()
            table.setRowCount(len(entries))
            selected_row = -1
            for row, entry in enumerate(entries):
                chi_path = entry["chi_path"]
                active = self._same_path(chi_path, current_chi)
                if active and selected_row < 0:
                    selected_row = row
                if select_path is not None and self._same_path(chi_path, select_path):
                    selected_row = row
                values = [
                    "Current" if active else "",
                    entry["type"],
                    entry["label"],
                    entry["ranges"],
                    os.path.basename(chi_path),
                ]
                for col, value in enumerate(values):
                    item = self._readonly_item(value, tooltip=chi_path)
                    item.setData(QtCore.Qt.UserRole, row)
                    table.setItem(row, col, item)
            if selected_row >= 0:
                table.selectRow(selected_row)
            table.resizeColumnsToContents()
        finally:
            table.blockSignals(old_state)

        if 0 <= selected_row < len(entries):
            entry = entries[selected_row]
            if select_path is not None:
                self._set_selected_derived_chi_preview(entry)
        elif select_path is not None:
            self._set_selected_derived_chi_preview(None)

        has_source = self._current_source_chi() is not None
        if hasattr(self.widget, "pushButton_OpenSelectedAziChi"):
            self.widget.pushButton_OpenSelectedAziChi.setEnabled(len(entries) > 0)
        if hasattr(self.widget, "pushButton_OpenFullAziChi"):
            self.widget.pushButton_OpenFullAziChi.setEnabled(has_source)
        self._update_remove_azimuthal_chi_button()

    def _selected_azimuthal_chi_entry(self):
        table = getattr(self.widget, "tableWidget_AziChiList", None)
        if table is None:
            return None
        rows = table.selectionModel().selectedRows()
        if rows == []:
            return None
        row = rows[0].row()
        if row < 0 or row >= len(self._derived_chi_entries):
            return None
        return self._derived_chi_entries[row]

    def _update_remove_azimuthal_chi_button(self):
        button = getattr(self.widget, "pushButton_RemoveSelectedAziChi", None)
        if button is None:
            return
        entry = self._selected_azimuthal_chi_entry()
        button.setEnabled(entry is not None and entry.get("kind") == "derived")

    def _remove_selected_azimuthal_chi(self):
        entry = self._selected_azimuthal_chi_entry()
        if entry is None:
            QtWidgets.QMessageBox.warning(
                self.widget, "Warning",
                "Highlight one row in the Azimuthal CHI list first.")
            return
        if entry.get("kind") != "derived":
            QtWidgets.QMessageBox.warning(
                self.widget, "Warning",
                "The full-azimuth CHI cannot be removed from this list.")
            return

        chi_path = entry.get("chi_path", "")
        sidecar_path = sidecar_path_for_chi(chi_path)
        source_chi = entry.get("source_chi", "")
        reply = QtWidgets.QMessageBox.question(
            self.widget,
            "Remove derived CHI?",
            "Remove the selected azimuth-derived CHI from the list?\n\n"
            "This deletes the derived CHI file and its azimuth metadata.",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
            QtWidgets.QMessageBox.No)
        if reply == QtWidgets.QMessageBox.No:
            return

        was_active = self._same_path(chi_path, self._display_chi_filename())
        errors = []
        for path in (chi_path, sidecar_path):
            if not path or not os.path.exists(path):
                continue
            try:
                os.remove(path)
            except OSError as exc:
                errors.append(f"{path}\n{exc}")
        if errors:
            QtWidgets.QMessageBox.warning(
                self.widget, "Warning",
                "Could not remove all selected azimuth-derived files:\n\n" +
                "\n\n".join(errors))

        if was_active and source_chi and os.path.exists(source_chi):
            self._open_chi_path(source_chi)
        else:
            self.refresh_derived_chi_ui(select_path=source_chi)

    def _open_chi_path(self, chi_path, display_derived=False):
        if self.base_ptn_ctrl is None:
            QtWidgets.QMessageBox.warning(
                self.widget, "Warning",
                "Cannot open CHI from this panel because the pattern loader is unavailable.")
            return
        if not chi_path or not os.path.exists(chi_path):
            QtWidgets.QMessageBox.warning(
                self.widget, "Warning", "Cannot find CHI file:\n" + str(chi_path))
            return
        self.base_ptn_ctrl._setshow_new_base_ptn(
            chi_path, display_derived=display_derived)
        self.refresh_derived_chi_ui(select_path=chi_path)

    def _open_selected_azimuthal_chi(self):
        entry = self._selected_azimuthal_chi_entry()
        if entry is None:
            QtWidgets.QMessageBox.warning(
                self.widget, "Warning",
                "Highlight one row in the Azimuthal CHI list first.")
            return
        if entry.get("kind") != "derived":
            self.clear_selected_derived_chi_preview()
        self._open_chi_path(
            entry["chi_path"], display_derived=entry.get("kind") == "derived")

    def _open_full_azimuth_chi(self):
        source_chi = self._current_source_chi()
        if source_chi is None:
            QtWidgets.QMessageBox.warning(
                self.widget, "Warning", "No full-azimuth source CHI is available.")
            return
        self.clear_selected_derived_chi_preview()
        self._open_chi_path(source_chi, display_derived=False)

    def _new_check_item(self, checked=True):
        item = QtWidgets.QTableWidgetItem()
        item.setFlags(
            QtCore.Qt.ItemIsUserCheckable |
            QtCore.Qt.ItemIsEnabled |
            QtCore.Qt.ItemIsSelectable)
        item.setCheckState(QtCore.Qt.Checked if checked else QtCore.Qt.Unchecked)
        return item

    def _new_text_item(self, text, editable=True):
        item = QtWidgets.QTableWidgetItem(str(text))
        flags = QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsSelectable
        if editable:
            flags |= QtCore.Qt.ItemIsEditable
        item.setFlags(flags)
        return item

    def _post_to_table(self, azi_list, clear=False):
        table = self.widget.tableWidget_DiffImgAzi
        if clear:
            table.setRowCount(0)
        for range_info in azi_list:
            azi = normalize_range(range_info)
            if azi is None:
                continue
            row = table.rowCount()
            table.insertRow(row)
            table.setItem(row, 0, self._new_check_item(azi["use"]))
            table.setItem(row, 1, self._new_text_item(azi["label"]))
            table.setItem(
                row, 2, self._new_text_item(f"{azi['azi_min']:.3f}"))
            table.setItem(
                row, 3, self._new_text_item(f"{azi['azi_max']:.3f}"))
            table.setItem(row, 4, self._new_text_item(azi["note"]))
        table.resizeColumnsToContents()

    def _read_azilist(self, checked_only=True, warn=True):
        table = self.widget.tableWidget_DiffImgAzi
        n_row = table.rowCount()
        if n_row == 0:
            return []
        azi_list = []
        for row in range(n_row):
            use_item = table.item(row, 0)
            use = True
            if use_item is not None:
                use = use_item.checkState() == QtCore.Qt.Checked
            if checked_only and not use:
                continue

            label_item = table.item(row, 1)
            min_item = table.item(row, 2)
            max_item = table.item(row, 3)
            note_item = table.item(row, 4)
            if min_item is None or max_item is None:
                if warn:
                    QtWidgets.QMessageBox.warning(
                        self.widget, "Warning",
                        "Cake integration row is incomplete. Fill azimuth "
                        "minimum and maximum values or remove the row.")
                return None
            try:
                azi_min = float(min_item.text())
                azi_max = float(max_item.text())
            except (TypeError, ValueError):
                if warn:
                    QtWidgets.QMessageBox.warning(
                        self.widget, "Warning",
                        "Cake integration row has invalid azimuth values.")
                return None
            normalized = normalize_range({
                "use": use,
                "label": "" if label_item is None else label_item.text(),
                "azi_min": azi_min,
                "azi_max": azi_max,
                "note": "" if note_item is None else note_item.text(),
            })
            if normalized is not None:
                azi_list.append(normalized)
        return azi_list

    def _save_cake_marker_file(self):
        filen = self._save_setup_file(show_message=True)
        return filen

    def _save_setup_file(self, show_message=False):
        source_chi = self._base_chi_filename()
        if source_chi is None:
            QtWidgets.QMessageBox.warning(
                self.widget, "Warning", "Open a CHI file before saving setup.")
            return None
        ranges = self._read_azilist(checked_only=False)
        if ranges is None:
            return None
        if ranges == []:
            QtWidgets.QMessageBox.warning(
                self.widget, "Warning", "No azimuthal ranges to save.")
            return None
        filen = default_setup_path(source_chi)
        setup_root = os.path.dirname(filen)
        try:
            stored_source_chi = os.path.relpath(os.path.abspath(source_chi), setup_root)
        except Exception:
            stored_source_chi = os.path.abspath(source_chi)
        setup = {
            "format": SETUP_FORMAT,
            "version": 1,
            "source_chi": stored_source_chi,
            "azimuth_shift": float(self.widget.spinBox_AziShift.value()),
            "azimuth_ranges": ranges,
        }
        with open(filen, "w") as handle:
            json.dump(setup, handle, indent=2, sort_keys=True)
            handle.write("\n")
        if show_message:
            QtWidgets.QMessageBox.information(
                self.widget, "Saved", "Azimuth setup saved to:\n" + filen)
        return filen

    def _load_cake_marker_file(self):
        source_chi = self._base_chi_filename()
        start_dir = self.model.chi_path
        if source_chi is not None:
            start_dir = output_dir_for_source(source_chi)
        filen = dialog_openfile_hide_param_dirs(
            self.widget, "Open an azimuth setup", start_dir,
            "Azimuth setup (*.json *.marker)")[0]
        if filen == "":
            return
        try:
            ranges = self._read_setup_or_legacy_marker(filen)
        except Exception as exc:
            QtWidgets.QMessageBox.warning(
                self.widget, "Warning",
                "Could not load azimuth setup:\n" + str(exc))
            return
        if ranges == []:
            QtWidgets.QMessageBox.warning(
                self.widget, "Warning", "No azimuthal ranges found.")
            return
        self._post_to_table(ranges, clear=True)
        self._apply_changes_to_graph()

    def _read_setup_or_legacy_marker(self, filen):
        if filen.lower().endswith(".marker"):
            return self._read_legacy_marker(filen)
        with open(filen) as handle:
            payload = json.load(handle)
        if isinstance(payload, list):
            return normalize_ranges(payload)
        if payload.get("format") in (SETUP_FORMAT, AZINT_FORMAT):
            return normalize_ranges(payload.get("azimuth_ranges", []))
        return normalize_ranges(payload.get("ranges", []))

    def _read_legacy_marker(self, filen):
        ranges = []
        with open(filen) as handle:
            for line in handle:
                if not line.strip():
                    continue
                values = [x.strip() for x in line.split(",")]
                if len(values) < 5:
                    continue
                ranges.append({
                    "use": True,
                    "label": values[0],
                    "azi_min": values[2],
                    "azi_max": values[4],
                    "note": "loaded from legacy marker",
                })
        return normalize_ranges(ranges)

    def _add_azi_to_list(self):
        if not self._pending_rois:
            QtWidgets.QMessageBox.warning(
                self.widget, "Warning",
                "Click Set ROI and draw one or more Cake azimuthal ROIs first.")
            return
        start_row = self.widget.tableWidget_DiffImgAzi.rowCount()
        ranges = []
        for idx, roi in enumerate(self._pending_rois, start=1):
            ranges.append({
                "use": True,
                "label": f"ROI {start_row + idx}",
                "azi_min": roi["azi_min"],
                "azi_max": roi["azi_max"],
                "note": "",
            })
        self._post_to_table(ranges)
        self._clear_pending_rois()
        self.deactivate_interactions()
        self._set_status(f"Added {len(ranges)} Cake ROI range(s) to the table.")
        self._apply_changes_to_graph()

    def _remove_azi_from_list(self):
        rows = self.widget.tableWidget_DiffImgAzi.selectionModel().selectedRows()
        if rows == []:
            QtWidgets.QMessageBox.warning(
                self.widget, "Warning", "Highlight the row to remove first.")
            return
        reply = QtWidgets.QMessageBox.question(
            self.widget, "Message",
            "Remove the highlighted azimuth range(s) from the list?",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
            QtWidgets.QMessageBox.Yes)
        if reply == QtWidgets.QMessageBox.No:
            return
        for row in sorted([r.row() for r in rows], reverse=True):
            self.widget.tableWidget_DiffImgAzi.removeRow(row)
        self._apply_changes_to_graph()

    def _clear_azilist(self):
        self.widget.tableWidget_DiffImgAzi.setRowCount(0)
        self._clear_pending_rois()
        self._apply_changes_to_graph()

    def _read_azi_from_plot(self):
        tth_range, azi_range = self.plot_ctrl.get_cake_range()
        if tth_range is None:
            return None, None
        return tth_range, azi_range

    def _integrate_only_clicked(self):
        filen = self.integrate_to_1d(show_message=True)
        if filen is not None:
            self.refresh_derived_chi_ui(select_path=filen)
            self._apply_changes_to_graph()

    def _display_to_raw_azimuth_range(self, azi_min, azi_max):
        mid_angle = self.widget.spinBox_AziShift.value()
        if mid_angle <= 180:
            azi_conv = [azi_min - mid_angle, azi_max - mid_angle]
        else:
            azi_conv = [azi_min + 360 - mid_angle, azi_max + 360 - mid_angle]
        azi_real = []
        for value in azi_conv:
            if value < -180:
                azi_real.append(360 + value)
            elif value > 180:
                azi_real.append(value - 360)
            else:
                azi_real.append(value)
        return azi_real

    def _combined_label(self, ranges):
        labels = [r["label"] for r in ranges if r.get("label", "").strip()]
        if len(labels) == 1:
            return labels[0]
        if len(labels) > 1 and len(labels) == len(ranges):
            return "_".join(labels[:3])
        return f"{len(ranges)} azimuth ranges"

    def _source_twotheta_range(self):
        x = getattr(getattr(self.model, "base_ptn", None), "x", None)
        if x is None or len(x) == 0:
            return None
        return (float(np.nanmin(x)), float(np.nanmax(x)))

    def _source_twotheta_grid(self):
        x = getattr(getattr(self.model, "base_ptn", None), "x", None)
        if x is None or len(x) == 0:
            return None
        x = np.asarray(x, dtype=float)
        x = x[np.isfinite(x)]
        if x.size == 0:
            return None
        return x

    def _cake_loaded_matches_source(self, source_chi):
        diff_img = getattr(self.model, "diff_img", None)
        if diff_img is None:
            return False
        intensity, tth, chi = diff_img.get_cake()
        if intensity is None or tth is None or chi is None:
            return False
        img_filename = getattr(diff_img, "img_filename", None)
        if not img_filename:
            return False
        img_root = os.path.splitext(os.path.basename(img_filename))[0]
        source_root = os.path.splitext(os.path.basename(source_chi))[0]
        return img_root == source_root or img_root.startswith(source_root + "__")

    def _image_candidates_for_chi(self, chi_path):
        exts = ("tif", "tiff", "mar3450", "cbf", "h5")
        candidates = []
        for ext in exts:
            for original in (True, False):
                filen = make_filename(chi_path, ext, original=original)
                if filen not in candidates:
                    candidates.append(filen)
        return candidates

    def _ensure_cake_loaded_for_source(self, source_chi):
        if self._cake_loaded_matches_source(source_chi):
            return True
        if not hasattr(self.model, "reset_diff_img"):
            return False
        self.model.reset_diff_img()
        temp_dir = get_temp_dir(source_chi)
        for candidate in self._image_candidates_for_chi(source_chi):
            self.model.diff_img.img_filename = candidate
            if self.model.diff_img.read_cake_from_tempfile(temp_dir=temp_dir):
                return True
        return False

    def _oriented_cake_arrays(self):
        diff_img = getattr(self.model, "diff_img", None)
        if diff_img is None:
            return None
        intensity, tth, chi = diff_img.get_cake()
        if intensity is None or tth is None or chi is None:
            return None
        tth = np.asarray(tth, dtype=float).ravel()
        chi = np.asarray(chi, dtype=float).ravel()
        arr = np.asarray(intensity, dtype=float)
        if arr.ndim != 2 or tth.size == 0 or chi.size == 0:
            return None
        if arr.shape == (chi.size, tth.size):
            cake = arr
        elif arr.shape == (tth.size, chi.size):
            cake = arr.T
        else:
            return None

        tth_order = np.argsort(tth)
        chi_order = np.argsort(chi)
        tth = tth[tth_order]
        chi = chi[chi_order]
        cake = cake[chi_order, :][:, tth_order]
        cake = np.ma.masked_invalid(cake)
        cake = np.ma.masked_where(cake == 0, cake)
        return cake, tth, chi

    def _wrap_to_cake_axis(self, values, chi_axis):
        values = np.asarray(values, dtype=float)
        axis_min = float(np.nanmin(chi_axis))
        axis_max = float(np.nanmax(chi_axis))
        if axis_min < 0.0 and axis_max <= 180.5:
            return ((values + 180.0) % 360.0) - 180.0
        return values % 360.0

    def _cake_row_mask_for_display_range(self, chi_axis, azi_min, azi_max):
        low = min(float(azi_min), float(azi_max))
        high = max(float(azi_min), float(azi_max))
        displayed_chi = self._wrap_to_cake_axis(
            chi_axis + float(self.widget.spinBox_AziShift.value()), chi_axis)
        mask = (displayed_chi >= low) & (displayed_chi <= high)
        if np.any(mask):
            return mask

        center = 0.5 * (low + high)
        if chi_axis.size > 1:
            step = float(np.nanmedian(np.abs(np.diff(np.sort(chi_axis)))))
        else:
            step = 1.0
        nearest = int(np.nanargmin(np.abs(displayed_chi - center)))
        if abs(displayed_chi[nearest] - center) <= max(step, 0.5 * (high - low) + step):
            mask[nearest] = True
        return mask

    def _interpolate_profile_to_source_grid(self, tth_cake, profile):
        target_tth = self._source_twotheta_grid()
        if target_tth is None or target_tth.size < 2:
            return tth_cake, profile
        finite = np.isfinite(tth_cake) & np.isfinite(profile)
        if np.count_nonzero(finite) < 2:
            return tth_cake, profile
        y = np.interp(
            target_tth,
            tth_cake[finite],
            profile[finite],
            left=0.0,
            right=0.0,
        )
        return target_tth, y

    def _integrate_cake_ranges_to_1d(self, ranges, source_chi):
        if not self._ensure_cake_loaded_for_source(source_chi):
            QtWidgets.QMessageBox.warning(
                self.widget, "Warning",
                "No Cake data are available for this CHI.\n\n"
                "Open/show the Cake once or load an existing Cake cache, then "
                "run azimuthal integration again. The original detector image "
                "is not required when cached Cake files are available.")
            return None, None
        arrays = self._oriented_cake_arrays()
        if arrays is None:
            QtWidgets.QMessageBox.warning(
                self.widget, "Warning",
                "Loaded Cake data could not be interpreted for azimuthal integration.")
            return None, None
        cake, tth_cake, chi_cake = arrays
        merged = None
        missing = []
        for azi in ranges:
            mask = self._cake_row_mask_for_display_range(
                chi_cake, azi["azi_min"], azi["azi_max"])
            if not np.any(mask):
                missing.append(format_ranges([azi], precision=2))
                continue
            profile = np.ma.mean(cake[mask, :], axis=0).filled(0.0)
            if merged is None:
                merged = np.asarray(profile, dtype=float)
            else:
                merged += np.asarray(profile, dtype=float)
        if merged is None:
            QtWidgets.QMessageBox.warning(
                self.widget, "Warning",
                "No Cake azimuth rows matched the selected range(s):\n" +
                "\n".join(missing))
            return None, None
        return self._interpolate_profile_to_source_grid(tth_cake, merged)

    def integrate_to_1d(self, show_message=False):
        ranges = self._read_azilist(checked_only=True)
        if ranges is None:
            return None
        if ranges == []:
            QtWidgets.QMessageBox.warning(
                self.widget, "Warning", "No checked azimuthal ranges in the queue.")
            return None

        source_chi = self._current_source_chi()
        if source_chi is None:
            QtWidgets.QMessageBox.warning(
                self.widget, "Warning", "Open a CHI file before integration.")
            return None
        tth_output, intensity_output = self._integrate_cake_ranges_to_1d(
            ranges, source_chi)
        if tth_output is None or intensity_output is None:
            return None

        label = self._combined_label(ranges)
        filen_chi = unique_output_chi_path(source_chi, ranges, label=label)
        tth_range = [float(np.nanmin(tth_output)), float(np.nanmax(tth_output))]
        src_text = (
            "# source chi: " + os.path.basename(source_chi) +
            "; integration source: cached cake\n"
        )
        azi_text = "# azimuthal ranges: " + format_ranges(ranges, precision=3) + "\n"
        preheader = src_text + azi_text + "2-theta\n"
        writechi(filen_chi, tth_output, intensity_output, preheader=preheader)

        metadata = make_metadata(
            source_chi=source_chi,
            derived_chi=filen_chi,
            ranges=ranges,
            azimuth_shift=float(self.widget.spinBox_AziShift.value()),
            tth_range=tth_range,
            source_image=getattr(self.model.diff_img, "img_filename", None),
            poni=getattr(self.model, "poni", None),
            label=label,
        )
        metadata["integration_source"] = "cached_cake"
        write_sidecar(filen_chi, metadata)
        self._save_setup_file(show_message=False)
        self.last_integration_file = filen_chi
        self.refresh_derived_chi_ui(select_path=filen_chi)

        if show_message:
            QtWidgets.QMessageBox.information(
                self.widget, "Integrated",
                "Azimuth-integrated CHI saved to:\n" + filen_chi)
        return filen_chi

    def _apply_changes_to_graph(self):
        self.plot_ctrl.update()
        QtCore.QTimer.singleShot(0, self.refresh_roi_overlays)
        QtCore.QTimer.singleShot(80, self.refresh_roi_overlays)

    def _zoom_out_graph(self):
        self.plot_ctrl.zoom_out_graph()
