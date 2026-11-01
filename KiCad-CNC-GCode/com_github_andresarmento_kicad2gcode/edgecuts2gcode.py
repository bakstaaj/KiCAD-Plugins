#!/usr/bin/env python3
# edgecuts2gcode.py
# KiCad Action Plugin: reads Edge Cuts layer and generates GRBL 1.1
# G-code for board cutting, without exporting Gerber files.

import os

import pcbnew
import wx

from gcode_common import (
    get_board_contours,
    get_npth_routing_paths,
    separar_e_offsetar,
    calcular_profundidades,
    calcular_segmentos,
    gerar_gcode_corte,
    open_in_gsender,
    mirror_path,
)

PLUGIN_NAME = "Edge Cuts to G-code"

# ============================================================
# OPTIONS
# ============================================================
DEFAULTS = {
    "TOOL_DIAMETER": 2.0,
    "CUT_DEPTH":     -2.4,
    "MULTI_DEPTH":    0.5,
    "SAFE_Z":         5.0,
    "FEED_XY":      200.0,
    "FEED_Z":       100.0,
    "SPINDLE_RPM": 13500,
    "END_Z":         25.0,
    "DWELL":            3,
    "PROBE_FEED":    50.0,
    "GAP_SIZE":       1.0,
    "NUM_GAPS":         2,
    "TAB_PLACEMENT": "Automatic",
    "TAB_POSITIONS": "",
    "ROUTE_NPTH": False,
    "MIRROR_AXIS": "None",
    "OUTPUT_DIR": "G:\\",
}

LABELS = {
    "TOOL_DIAMETER": "Tool diameter (mm)",
    "CUT_DEPTH":     "Cut depth (mm, negative)",
    "MULTI_DEPTH":   "Depth per pass (mm, positive)",
    "SAFE_Z":        "Safe Z height (mm)",
    "FEED_XY":       "XY feed rate (mm/min)",
    "FEED_Z":        "Plunge feed rate (mm/min)",
    "SPINDLE_RPM":   "Spindle RPM",
    "END_Z":         "End Z height (probe travel adds 1 mm)",
    "DWELL":         "Spindle dwell (s)",
    "PROBE_FEED":    "Probe feed rate (mm/min)",
    "GAP_SIZE":      "Tab size (mm)",
    "NUM_GAPS":      "Number of tabs",
    "TAB_PLACEMENT": "Tab placement",
    "TAB_POSITIONS": "Manual tab centers (X,Y mm; one per line)",
    "ROUTE_NPTH":   "Route circular NPTH holes ≥ tool diameter",
    "MIRROR_AXIS":   "Mirror output across",
    "OUTPUT_DIR":    "Output folder",
}

INT_KEYS = {"SPINDLE_RPM", "DWELL", "NUM_GAPS"}
BOOL_KEYS = {"ROUTE_NPTH"}
MIRROR_CHOICES = ("None", "X axis", "Y axis")
TAB_PLACEMENT_CHOICES = ("Automatic (evenly spaced)", "Manual (coordinates)")


# ============================================================
# OPTIONS DIALOG
# ============================================================
class CutOptionsDialog(wx.Dialog):
    def __init__(self, parent):
        super().__init__(parent, title=f"{PLUGIN_NAME} — Options",
                         style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)

        grid = wx.FlexGridSizer(cols=2, vgap=6, hgap=12)
        grid.AddGrowableCol(1)

        self._fields = {}
        for key, label in LABELS.items():
            grid.Add(wx.StaticText(self, label=label), 0, wx.ALIGN_CENTER_VERTICAL)
            if key == "MIRROR_AXIS":
                ctrl = wx.Choice(self, choices=list(MIRROR_CHOICES), size=(110, -1))
                ctrl.SetStringSelection(DEFAULTS[key])
            elif key == "TAB_PLACEMENT":
                ctrl = wx.Choice(self, choices=list(TAB_PLACEMENT_CHOICES), size=(250, -1))
                ctrl.SetSelection(0)
                ctrl.Bind(wx.EVT_CHOICE, self._on_tab_placement_changed)
            elif key == "TAB_POSITIONS":
                ctrl = wx.TextCtrl(
                    self,
                    value=DEFAULTS[key],
                    size=(250, 70),
                    style=wx.TE_MULTILINE,
                )
            elif key in BOOL_KEYS:
                ctrl = wx.CheckBox(self, label="")
                ctrl.SetValue(DEFAULTS[key])
            elif key == "OUTPUT_DIR":
                ctrl = wx.DirPickerCtrl(
                    self,
                    path=DEFAULTS[key],
                    message="Choose where the Edge Cuts G-code file will be saved",
                    size=(330, -1),
                    style=wx.DIRP_USE_TEXTCTRL,
                )
            else:
                ctrl = wx.TextCtrl(self, value=str(DEFAULTS[key]), size=(110, -1))
            grid.Add(ctrl, 1, wx.EXPAND)
            self._fields[key] = ctrl

        self._fields["TAB_POSITIONS"].Enable(False)

        hint = wx.StaticText(
            self,
            label=(
                "Enter exactly Number of tabs points. Coordinates are G-code X,Y "
                "in mm from the drill/place origin (Y up, before mirroring); each "
                "point snaps to the nearest outer cut path. Example: 10.0, 20.0"
            ),
        )
        hint.Wrap(430)
        grid.Add(hint, 0, wx.EXPAND)
        grid.Add((0, 0), 0)

        btn_sizer = self.CreateButtonSizer(wx.OK | wx.CANCEL)

        main = wx.BoxSizer(wx.VERTICAL)
        main.Add(grid, 1, wx.ALL | wx.EXPAND, 12)
        probe_note = wx.StaticText(
            self,
            label=("Probe requires a working GRBL probe input. Travel is End Z height "
                   "+ 1 mm from machine Z0; contact becomes Z0 with no plate offset."),
        )
        probe_note.Wrap(440)
        main.Add(probe_note, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 12)
        main.Add(btn_sizer, 0, wx.ALL | wx.ALIGN_RIGHT, 8)
        self.SetSizerAndFit(main)

    def _on_tab_placement_changed(self, _event):
        manual = self._fields["TAB_PLACEMENT"].GetSelection() == 1
        self._fields["TAB_POSITIONS"].Enable(manual)

    def get_options(self):
        opts = {}
        for key, ctrl in self._fields.items():
            if key == "MIRROR_AXIS":
                opts[key] = ctrl.GetStringSelection()
                continue
            if key == "TAB_PLACEMENT":
                opts[key] = "Manual" if ctrl.GetSelection() == 1 else "Automatic"
                continue
            if key == "TAB_POSITIONS":
                opts[key] = ctrl.GetValue().strip()
                continue
            if key in BOOL_KEYS:
                opts[key] = ctrl.GetValue()
                continue
            if key == "OUTPUT_DIR":
                opts[key] = ctrl.GetPath().strip()
                continue
            text = ctrl.GetValue().strip().replace(",", ".")
            try:
                opts[key] = int(text) if key in INT_KEYS else float(text)
            except ValueError:
                raise ValueError(f"Invalid value for '{LABELS[key]}': {text!r}")
        return opts


# ============================================================
# ACTION PLUGIN
# ============================================================
class EdgeCuts2GcodePlugin(pcbnew.ActionPlugin):
    def defaults(self):
        self.name = PLUGIN_NAME
        self.category = "Manufacturing"
        self.description = "Generate GRBL 1.1 G-code for board cutting (no Gerber export needed)"
        self.show_toolbar_button = True
        icon_path = os.path.join(os.path.dirname(__file__), "icon_cut.png")
        self.icon_file_name = icon_path if os.path.isfile(icon_path) else ""

    def Run(self):
        board = pcbnew.GetBoard()

        dlg = CutOptionsDialog(None)
        if dlg.ShowModal() != wx.ID_OK:
            dlg.Destroy()
            return

        try:
            opts = dlg.get_options()
        except ValueError as e:
            wx.MessageBox(str(e), f"{PLUGIN_NAME} — Error", wx.OK | wx.ICON_ERROR)
            dlg.Destroy()
            return
        finally:
            dlg.Destroy()

        try:
            contornos = get_board_contours(board)
            raio = opts["TOOL_DIAMETER"] / 2.0
            externo, furos = separar_e_offsetar(contornos, raio)
            if opts["ROUTE_NPTH"]:
                npth_paths = get_npth_routing_paths(board, opts["TOOL_DIAMETER"])
                if not npth_paths:
                    raise ValueError(
                        "No circular NPTH holes with drill diameter at least "
                        f"{opts['TOOL_DIAMETER']:.3f} mm were found. Smaller holes "
                        "and non-circular slots are skipped."
                    )
                furos.extend(npth_paths)
            manual_points = None
            if opts["TAB_PLACEMENT"] == "Manual":
                manual_points = []
                raw_points = opts["TAB_POSITIONS"].replace("\n", ";")
                for entry in raw_points.split(";"):
                    entry = entry.strip()
                    if not entry:
                        continue
                    coordinates = entry.replace(",", " ").split()
                    if len(coordinates) != 2:
                        raise ValueError(
                            "Enter each manual tab point as X,Y; separate points with semicolons or new lines."
                        )
                    try:
                        manual_points.append((float(coordinates[0]), float(coordinates[1])))
                    except ValueError as e:
                        raise ValueError(f"Invalid manual tab point: {entry!r}") from e

            furos = [mirror_path(furo, opts["MIRROR_AXIS"]) for furo in furos]

            profundidades = calcular_profundidades(opts["CUT_DEPTH"], opts["MULTI_DEPTH"])
            segs = calcular_segmentos(
                externo,
                opts["GAP_SIZE"],
                opts["TOOL_DIAMETER"],
                opts["NUM_GAPS"],
                manual_points,
            )
            segs = [mirror_path(seg, opts["MIRROR_AXIS"]) for seg in segs]
            gcode = gerar_gcode_corte(segs, furos, profundidades, opts)

            board_file = board.GetFileName()
            base = os.path.splitext(os.path.basename(board_file))[0] if board_file else "board"
            output_dir = opts["OUTPUT_DIR"]
            if not output_dir or not os.path.isdir(output_dir):
                raise ValueError(f"Output folder does not exist or is unavailable: {output_dir!r}")
            output_file = os.path.join(output_dir, base + "_cut.nc")

            with open(output_file, "w") as f:
                f.write(gcode)

            try:
                open_in_gsender(output_file)
                open_status = "\n\nOpened in gSender."
            except OSError as e:
                open_status = f"\n\nFile saved, but could not open in gSender: {e}"

            wx.MessageBox(
                f"G-code saved to:\n{output_file}{open_status}",
                f"{PLUGIN_NAME} — Done",
                wx.OK | wx.ICON_INFORMATION,
            )

        except Exception as e:
            wx.MessageBox(str(e), f"{PLUGIN_NAME} — Error", wx.OK | wx.ICON_ERROR)
