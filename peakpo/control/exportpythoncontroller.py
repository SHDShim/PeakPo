import os
import json
import datetime
import numpy as np
from qtpy import QtWidgets
from matplotlib.collections import LineCollection as MplLineCollection


class ExportPythonController(object):
    """Export current on-screen figure into a reproducible Python package."""

    def __init__(self, model, widget, plot_ctrl=None):
        self.model = model
        self.widget = widget
        self.plot_ctrl = plot_ctrl

    def export_current_view(self, fig=None, folder_prefix=None):
        if isinstance(fig, bool):
            fig = None
        if fig is None:
            if not hasattr(self.widget, "mpl") or (not hasattr(self.widget.mpl, "canvas")):
                QtWidgets.QMessageBox.warning(self.widget, "Warning", "Plot canvas is not available.")
                return
            fig = self.widget.mpl.canvas.fig

        # Capture exactly what is currently visible on screen.
        try:
            fig.canvas.draw()
        except Exception:
            try:
                self.widget.mpl.canvas.draw()
            except Exception:
                pass

        out_root = QtWidgets.QFileDialog.getExistingDirectory(
            self.widget,
            "Choose output folder for Python export",
            self.model.chi_path if getattr(self.model, "chi_path", "") else "",
            QtWidgets.QFileDialog.ShowDirsOnly,
        )
        if out_root in (None, ""):
            return

        stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        if folder_prefix is None:
            chi_path = str(getattr(self.model, "chi_path", "") or "")
            chi_name = os.path.splitext(os.path.basename(chi_path))[0].strip()
            if chi_name == "":
                chi_name = "peakpo"
            folder_prefix = f"{chi_name}-pkpo-exports"
        export_dir = os.path.join(out_root, f"{folder_prefix}-{stamp}")
        os.makedirs(export_dir, exist_ok=True)

        payload, arrays = self._capture_figure(fig)

        npz_path = os.path.join(export_dir, "data_arrays.npz")
        json_path = os.path.join(export_dir, "snapshot.json")
        script_path = os.path.join(export_dir, "replot_peakpo_export.py")
        preview_png = os.path.join(export_dir, "preview.png")
        preview_pdf = os.path.join(export_dir, "preview.pdf")

        np.savez_compressed(npz_path, **arrays)
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)

        with open(script_path, "w", encoding="utf-8") as f:
            f.write(self._script_template())

        try:
            fig.savefig(
                preview_png, dpi=fig.dpi,
                facecolor=fig.get_facecolor(),
                edgecolor=fig.get_edgecolor(),
            )
            fig.savefig(
                preview_pdf, dpi=fig.dpi,
                facecolor=fig.get_facecolor(),
                edgecolor=fig.get_edgecolor(),
            )
        except Exception:
            pass

        QtWidgets.QMessageBox.information(
            self.widget,
            "Python Export Complete",
            "Current view was exported.\n\n"
            f"Folder:\n{export_dir}\n\n"
            "Run:\npython replot_peakpo_export.py",
        )

    def _capture_figure(self, fig):
        arrays = {}
        counter = {"i": 0}

        def put_array(arr):
            key = f"a_{counter['i']:05d}"
            counter["i"] += 1
            arrays[key] = np.asarray(arr)
            return key

        def color_to_json(c):
            if c is None:
                return None
            if isinstance(c, str):
                return c
            try:
                vals = list(c)
                if len(vals) >= 3:
                    return [float(v) for v in vals[:4]]
            except Exception:
                pass
            return str(c)

        def cap_line(line):
            x = np.asarray(line.get_xdata())
            y = np.asarray(line.get_ydata())
            return {
                "x": put_array(x),
                "y": put_array(y),
                "color": color_to_json(line.get_color()),
                "label": str(line.get_label()),
                "linestyle": str(line.get_linestyle()),
                "linewidth": float(line.get_linewidth()),
                "marker": str(line.get_marker()),
                "markersize": float(line.get_markersize()),
                "alpha": None if line.get_alpha() is None else float(line.get_alpha()),
                "zorder": float(line.get_zorder()),
            }

        def pick_tick_color(axis_obj, default="black"):
            labels = axis_obj.get_ticklabels()
            for lab in labels:
                if lab.get_visible():
                    return color_to_json(lab.get_color())
            lines = axis_obj.get_ticklines()
            for ln in lines:
                if ln.get_visible():
                    return color_to_json(ln.get_color())
            return default

        def cap_image(img):
            data = img.get_array()
            if np.ma.isMaskedArray(data):
                arr = np.asarray(data.filled(np.nan), dtype=float)
            else:
                arr = np.asarray(data)
            extent = img.get_extent()
            vmin, vmax = img.get_clim()
            return {
                "data": put_array(arr),
                "origin": str(getattr(img, "origin", "lower")),
                "extent": [float(v) for v in extent],
                "aspect": str(getattr(img, "get_aspect", lambda: "auto")()),
                "cmap": str(img.get_cmap().name),
                "vmin": None if vmin is None else float(vmin),
                "vmax": None if vmax is None else float(vmax),
                "zorder": float(img.get_zorder()),
            }

        def cap_text(ax, txt):
            trans = txt.get_transform()
            coord = "data"
            if trans == ax.transAxes:
                coord = "axes"
            return {
                "x": float(txt.get_position()[0]),
                "y": float(txt.get_position()[1]),
                "coord": coord,
                "text": str(txt.get_text()),
                "color": color_to_json(txt.get_color()),
                "fontsize": float(txt.get_fontsize()),
                "ha": str(txt.get_ha()),
                "va": str(txt.get_va()),
                "rotation": float(txt.get_rotation()),
                "alpha": None if txt.get_alpha() is None else float(txt.get_alpha()),
                "zorder": float(txt.get_zorder()),
            }

        def cap_patch_rect(rect):
            return {
                "kind": "rectangle",
                "xy": [float(rect.get_x()), float(rect.get_y())],
                "width": float(rect.get_width()),
                "height": float(rect.get_height()),
                "angle": float(rect.get_angle()),
                "facecolor": color_to_json(rect.get_facecolor()),
                "edgecolor": color_to_json(rect.get_edgecolor()),
                "linewidth": float(rect.get_linewidth()),
                "linestyle": str(rect.get_linestyle()),
                "alpha": None if rect.get_alpha() is None else float(rect.get_alpha()),
                "fill": bool(rect.get_fill()),
                "zorder": float(rect.get_zorder()),
            }

        def cap_collection(col):
            ctype = type(col).__name__
            info = {"type": ctype}
            if ctype == "LineCollection":
                ls_val = col.get_linestyle()
                safe_ls = None
                if isinstance(ls_val, str):
                    safe_ls = ls_val
                seg = col.get_segments()
                info.update({
                    "segments": put_array(np.asarray(seg, dtype=float)),
                    "colors": put_array(np.asarray(col.get_colors(), dtype=float)),
                    "linewidths": put_array(np.asarray(col.get_linewidths(), dtype=float)),
                    "label": str(col.get_label()),
                    "linestyles": safe_ls,
                    "alpha": None if col.get_alpha() is None else float(col.get_alpha()),
                    "zorder": float(col.get_zorder()),
                })
            elif ctype == "PolyCollection":
                verts = [np.asarray(p.vertices, dtype=float) for p in col.get_paths()]
                info.update({
                    "verts": put_array(np.asarray(verts, dtype=object)),
                    "facecolors": put_array(np.asarray(col.get_facecolors(), dtype=float)),
                    "edgecolors": put_array(np.asarray(col.get_edgecolors(), dtype=float)),
                    "linewidths": put_array(np.asarray(col.get_linewidths(), dtype=float)),
                    "alpha": None if col.get_alpha() is None else float(col.get_alpha()),
                    "zorder": float(col.get_zorder()),
                })
            else:
                return None
            return info

        axes_payload = []
        for ax in fig.axes:
            # Skip hidden axes
            if not ax.get_visible():
                continue
            apos = ax.get_position().bounds
            axis = {
                "id": str(getattr(ax, "get_label", lambda: "")() or ""),
                "position": [float(v) for v in apos],
                "xlim": [float(v) for v in ax.get_xlim()],
                "ylim": [float(v) for v in ax.get_ylim()],
                "xscale": str(ax.get_xscale()),
                "yscale": str(ax.get_yscale()),
                "xlabel": str(ax.get_xlabel()),
                "ylabel": str(ax.get_ylabel()),
                "title": str(ax.get_title()),
                "facecolor": color_to_json(ax.get_facecolor()),
                "xlabel_color": color_to_json(ax.xaxis.label.get_color()),
                "ylabel_color": color_to_json(ax.yaxis.label.get_color()),
                "title_color": color_to_json(ax.title.get_color()),
                "xtick_color": pick_tick_color(ax.xaxis, default="black"),
                "ytick_color": pick_tick_color(ax.yaxis, default="black"),
                "spines": {
                    name: {
                        "visible": bool(sp.get_visible()),
                        "color": color_to_json(sp.get_edgecolor()),
                        "linewidth": float(sp.get_linewidth()),
                        "linestyle": str(sp.get_linestyle()),
                    } for name, sp in ax.spines.items()
                },
                "lines": [cap_line(l) for l in ax.lines if l.get_visible()],
                "images": [cap_image(im) for im in ax.images if im.get_visible()],
                "texts": [cap_text(ax, t) for t in ax.texts if t.get_visible() and (t.get_text() != "")],
                "patches": [],
                "collections": [],
                "legend": None,
                "show_xticklabels": any(
                    [bool(lbl.get_visible()) for lbl in ax.get_xticklabels()]),
            }
            for p in ax.patches:
                if not p.get_visible():
                    continue
                ptype = type(p).__name__
                if ptype == "Rectangle":
                    axis["patches"].append(cap_patch_rect(p))
            for c in ax.collections:
                if not c.get_visible():
                    continue
                ci = cap_collection(c)
                if ci is not None:
                    axis["collections"].append(ci)
            leg = ax.get_legend()
            if leg is not None and leg.get_visible():
                legend_labels = []
                legend_text_colors = []
                legend_entries = []
                for txt in leg.get_texts():
                    legend_labels.append(str(txt.get_text()))
                    legend_text_colors.append(color_to_json(txt.get_color()))
                handles = getattr(leg, "legend_handles", None)
                if handles is None:
                    handles = getattr(leg, "legendHandles", [])
                for h, lab in zip(handles, legend_labels):
                    h_color = None
                    if hasattr(h, "get_color"):
                        try:
                            h_color = color_to_json(h.get_color())
                        except Exception:
                            h_color = None
                    if (h_color is None) and isinstance(h, MplLineCollection):
                        try:
                            cols = h.get_colors()
                            if len(cols) > 0:
                                h_color = color_to_json(cols[0])
                        except Exception:
                            h_color = None
                    if h_color is None:
                        h_color = "black"
                    legend_entries.append({
                        "label": str(lab),
                        "color": h_color,
                    })
                axis["legend"] = {
                    "labels": legend_labels,
                    "text_colors": legend_text_colors,
                    "entries": legend_entries,
                    "loc": str(leg._loc),
                    "frameon": bool(leg.get_frame_on()),
                    "facecolor": color_to_json(leg.get_frame().get_facecolor()),
                    "edgecolor": color_to_json(leg.get_frame().get_edgecolor()),
                    "fontsize": float(leg.get_texts()[0].get_fontsize()) if leg.get_texts() else 10.0,
                }
            axes_payload.append(axis)

        suptitle = ""
        suptitle_color = "black"
        st = getattr(fig, "_suptitle", None)
        if st is not None:
            suptitle = str(st.get_text())
            suptitle_color = st.get_color()

        payload = {
            "version": 1,
            "created_at": datetime.datetime.now().isoformat(timespec="seconds"),
            "figure": {
                "figsize": [float(v) for v in fig.get_size_inches()],
                "dpi": float(fig.dpi),
                "facecolor": color_to_json(fig.get_facecolor()),
                "edgecolor": color_to_json(fig.get_edgecolor()),
                "suptitle": suptitle,
                "suptitle_color": color_to_json(suptitle_color),
            },
            "axes": axes_payload,
        }
        return payload, arrays

    def _script_template(self):
        return r'''#!/usr/bin/env python3
import json
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection, PolyCollection
from matplotlib.patches import Rectangle
from matplotlib.lines import Line2D


def load_export(snapshot_file="snapshot.json", npz_file="data_arrays.npz"):
    with open(snapshot_file, "r", encoding="utf-8") as f:
        snap = json.load(f)
    arr = np.load(npz_file, allow_pickle=True)
    return snap, arr


def to_color(value):
    return value


def safe_collection_linestyle(value):
    if not isinstance(value, str):
        return "solid"
    allowed = {
        "-", "--", "-.", ":",
        "solid", "dashed", "dashdot", "dotted", "None", "none", ""
    }
    if value in allowed:
        return value if value not in ("", "None", "none") else "solid"
    return "solid"


def draw_from_snapshot(snap, arr):
    fig_cfg = snap["figure"]
    fig_face = to_color(fig_cfg.get("facecolor", "white"))
    fig_edge = to_color(fig_cfg.get("edgecolor", fig_face))
    fig = plt.figure(
        figsize=tuple(fig_cfg.get("figsize", [12, 8])),
        dpi=float(fig_cfg.get("dpi", 100.0)),
        facecolor=fig_face,
    )
    fig.patch.set_facecolor(fig_face)
    fig.patch.set_edgecolor(fig_edge)
    st = str(fig_cfg.get("suptitle", ""))
    if st != "":
        fig.suptitle(st, color=to_color(fig_cfg.get("suptitle_color", "black")))

    for ax_cfg in snap.get("axes", []):
        ax = fig.add_axes(ax_cfg["position"])
        ax.set_facecolor(to_color(ax_cfg.get("facecolor", "white")))
        ax.set_xlim(ax_cfg["xlim"])
        ax.set_ylim(ax_cfg["ylim"])
        ax.set_xscale(ax_cfg.get("xscale", "linear"))
        ax.set_yscale(ax_cfg.get("yscale", "linear"))
        ax.set_xlabel(ax_cfg.get("xlabel", ""))
        ax.set_ylabel(ax_cfg.get("ylabel", ""))
        ax.set_title(ax_cfg.get("title", ""))
        ax.xaxis.label.set_color(to_color(ax_cfg.get("xlabel_color", "black")))
        ax.yaxis.label.set_color(to_color(ax_cfg.get("ylabel_color", "black")))
        ax.title.set_color(to_color(ax_cfg.get("title_color", "black")))
        x_tick_color = ax_cfg.get("xtick_color", "black")
        y_tick_color = ax_cfg.get("ytick_color", "black")
        ax.tick_params(axis="x", colors=to_color(x_tick_color))
        ax.tick_params(axis="y", colors=to_color(y_tick_color))
        if not bool(ax_cfg.get("show_xticklabels", True)):
            ax.tick_params(axis="x", labelbottom=False)
        for name, sp_cfg in ax_cfg.get("spines", {}).items():
            if name not in ax.spines:
                continue
            sp = ax.spines[name]
            sp.set_visible(bool(sp_cfg.get("visible", True)))
            sp.set_linewidth(float(sp_cfg.get("linewidth", 1.0)))
            sp.set_linestyle(sp_cfg.get("linestyle", "-"))
            sp.set_color(to_color(sp_cfg.get("color", "black")))

        for l in ax_cfg.get("lines", []):
            x = np.asarray(arr[l["x"]])
            y = np.asarray(arr[l["y"]])
            marker = l.get("marker", "None")
            if marker in ("None", "none", ""):
                marker = None
            label = l.get("label", "")
            if label in ("_nolegend_", "_child0", "_child1"):
                label = None
            ax.plot(
                x, y,
                color=to_color(l.get("color", "k")),
                label=label,
                linestyle=l.get("linestyle", "-"),
                linewidth=float(l.get("linewidth", 1.0)),
                marker=marker,
                markersize=float(l.get("markersize", 6.0)),
                alpha=l.get("alpha", None),
                zorder=float(l.get("zorder", 2.0)),
            )

        for im in ax_cfg.get("images", []):
            data = np.asarray(arr[im["data"]])
            ax.imshow(
                data,
                origin=im.get("origin", "lower"),
                extent=im.get("extent", None),
                aspect=im.get("aspect", "auto"),
                cmap=im.get("cmap", "viridis"),
                vmin=im.get("vmin", None),
                vmax=im.get("vmax", None),
                zorder=float(im.get("zorder", 1.0)),
            )

        for p in ax_cfg.get("patches", []):
            if p.get("kind") != "rectangle":
                continue
            rect = Rectangle(
                tuple(p.get("xy", [0.0, 0.0])),
                float(p.get("width", 1.0)),
                float(p.get("height", 1.0)),
                angle=float(p.get("angle", 0.0)),
                facecolor=to_color(p.get("facecolor", "none")),
                edgecolor=to_color(p.get("edgecolor", "k")),
                linewidth=float(p.get("linewidth", 1.0)),
                linestyle=p.get("linestyle", "-"),
                alpha=p.get("alpha", None),
                fill=bool(p.get("fill", True)),
                zorder=float(p.get("zorder", 1.0)),
            )
            ax.add_patch(rect)

        for c in ax_cfg.get("collections", []):
            ctype = c.get("type", "")
            if ctype == "LineCollection":
                segments = np.asarray(arr[c["segments"]], dtype=float)
                colors = np.asarray(arr[c["colors"]], dtype=float)
                linewidths = np.asarray(arr[c["linewidths"]], dtype=float)
                lc = LineCollection(
                    segments,
                    colors=colors,
                    linewidths=linewidths,
                    label=c.get("label", "_nolegend_"),
                    linestyles=safe_collection_linestyle(c.get("linestyles", "solid")),
                    alpha=c.get("alpha", None),
                    zorder=float(c.get("zorder", 2.0)),
                )
                ax.add_collection(lc)
            elif ctype == "PolyCollection":
                verts = np.asarray(arr[c["verts"]], dtype=object)
                facecolors = np.asarray(arr[c["facecolors"]], dtype=float)
                edgecolors = np.asarray(arr[c["edgecolors"]], dtype=float)
                linewidths = np.asarray(arr[c["linewidths"]], dtype=float)
                pc = PolyCollection(
                    verts,
                    facecolors=facecolors,
                    edgecolors=edgecolors,
                    linewidths=linewidths,
                    alpha=c.get("alpha", None),
                    zorder=float(c.get("zorder", 2.0)),
                )
                ax.add_collection(pc)

        for t in ax_cfg.get("texts", []):
            trans = ax.transAxes if t.get("coord", "data") == "axes" else ax.transData
            ax.text(
                float(t.get("x", 0.0)),
                float(t.get("y", 0.0)),
                t.get("text", ""),
                transform=trans,
                color=to_color(t.get("color", "k")),
                fontsize=float(t.get("fontsize", 10.0)),
                ha=t.get("ha", "left"),
                va=t.get("va", "baseline"),
                rotation=float(t.get("rotation", 0.0)),
                alpha=t.get("alpha", None),
                zorder=float(t.get("zorder", 3.0)),
            )
        leg_cfg = ax_cfg.get("legend", None)
        if isinstance(leg_cfg, dict):
            handles, labels = ax.get_legend_handles_labels()
            if (not labels) and leg_cfg.get("entries", []):
                handles = []
                labels = []
                for ent in leg_cfg.get("entries", []):
                    handles.append(Line2D([0], [0], color=to_color(ent.get("color", "black")), lw=2.0))
                    labels.append(str(ent.get("label", "")))
            if labels:
                loc_raw = leg_cfg.get("loc", "best")
                try:
                    loc_val = int(loc_raw)
                except Exception:
                    loc_val = "best"
                leg = ax.legend(
                    handles, labels,
                    loc=loc_val,
                    frameon=bool(leg_cfg.get("frameon", True)),
                    fontsize=float(leg_cfg.get("fontsize", 10.0)),
                )
                if leg is not None:
                    leg.get_frame().set_facecolor(to_color(
                        leg_cfg.get("facecolor", "white")))
                    leg.get_frame().set_edgecolor(to_color(
                        leg_cfg.get("edgecolor", "black")))
                    src_text_colors = leg_cfg.get("text_colors", [])
                    for i, txt in enumerate(leg.get_texts()):
                        src = src_text_colors[i] if i < len(src_text_colors) else "black"
                        txt.set_color(to_color(src))

    return fig


def main():
    snap, arr = load_export()
    fig = draw_from_snapshot(snap, arr)
    fig_cfg = snap.get("figure", {})
    face = to_color(fig_cfg.get("facecolor", fig.get_facecolor()))
    edge = to_color(fig_cfg.get("edgecolor", fig.get_edgecolor()))
    fig.savefig("reproduced.png", dpi=fig.dpi, facecolor=face, edgecolor=edge)
    fig.savefig("reproduced.pdf", dpi=fig.dpi, facecolor=face, edgecolor=edge)
    plt.show()


if __name__ == "__main__":
    main()
'''
