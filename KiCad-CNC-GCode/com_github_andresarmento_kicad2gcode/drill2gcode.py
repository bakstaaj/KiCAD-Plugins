#!/usr/bin/env python3
# drill2gcode.py
# KiCad Action Plugin: reads through-hole pads and generates GRBL 1.1
# G-code for drilling, without exporting Excellon files.
#
# Hole positions retain the KiCad board origin.  X is preserved and
# Y is inverted because KiCad's internal board coordinates are Y-down
# while the generated GRBL coordinates use the conventional Y-up axis.

import os

import pcbnew
import wx

from gcode_common import (
    get_drill_holes,
    agrupar_por_diametro,
    ordenar_vizinho_mais_proximo,
    gerar_gcode_furacao,
    open_in_gsender,
    mirror_xy,
)

PLUGIN_NAME = "Drill to G-code"

# ============================================================
# OPTIONS
# ============================================================
DEFAULTS = {
    "TOOL_DIAMETER":        2.0,
    "DRILL_DEPTH":           -2.1,
    "SAFE_Z":                 3.0,
    "FEED_Z":               300.0,
    "SPINDLE_RPM":           900,
    "END_Z":                 25.0,
    "TOOLCHANGE_Z":          25.0,
    "DWELL":                   3,
    "PROBE_FEED":            50.0,
    "MIRROR_AXIS":          "None",
    "INCLUDE_PTH":           True,
    "INCLUDE_VIAS":          True,
    "INCLUDE_NPTH":          True,
    "OUTPUT_DIR":            "G:\\",
}

LABELS = {
    "TOOL_DIAMETER":         "Tool diameter (mm) — retained for compatibility",
    "DRILL_DEPTH":           "Drill depth (mm, negative)",
    "SAFE_Z":                "Safe Z height (mm)",
    "FEED_Z":                "Plunge feed rate (mm/min)",
    "SPINDLE_RPM":           "Spindle RPM",
    "END_Z":                 "End Z height (probe travel adds 1 mm)",
    "TOOLCHANGE_Z":          "Tool change Z height (mm)",
    "DWELL":                 "Spindle dwell (s)",
    "PROBE_FEED":            "Probe feed rate (mm/min)",
    "MIRROR_AXIS":           "Mirror output across",
    "INCLUDE_PTH":           "Include PTH holes",
    "INCLUDE_VIAS":          "Include through vias",
    "INCLUDE_NPTH":          "Include NPTH holes",
    "OUTPUT_DIR":            "Output folder",
}

INT_KEYS = {"SPINDLE_RPM", "DWELL"}
BOOL_KEYS = {"INCLUDE_PTH", "INCLUDE_NPTH", "INCLUDE_VIAS"}
MIRROR_CHOICES = ("None", "X axis", "Y axis")


# ============================================================
# OPTIONS DIALOG
# ============================================================
class DrillOptionsDialog(wx.Dialog):
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
            elif key in BOOL_KEYS:
                ctrl = wx.CheckBox(self)
                ctrl.SetValue(DEFAULTS[key])
            elif key == "OUTPUT_DIR":
                ctrl = wx.DirPickerCtrl(
                    self,
                    path=DEFAULTS[key],
                    message="Choose where the Drill G-code file will be saved",
                    size=(330, -1),
                    style=wx.DIRP_USE_TEXTCTRL,
                )
            else:
                ctrl = wx.TextCtrl(self, value=str(DEFAULTS[key]), size=(110, -1))
            grid.Add(ctrl, 1, wx.EXPAND)
            self._fields[key] = ctrl

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

    def get_options(self):
        opts = {}
        for key, ctrl in self._fields.items():
            if key == "MIRROR_AXIS":
                opts[key] = ctrl.GetStringSelection()
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
class Drill2GcodePlugin(pcbnew.ActionPlugin):
    def defaults(self):
        self.name = PLUGIN_NAME
        self.category = "Manufacturing"
        self.description = "Generate GRBL 1.1 G-code for drilling (no Excellon export needed)"
        self.show_toolbar_button = True
        icon_path = os.path.join(os.path.dirname(__file__), "icon_drill.png")
        self.icon_file_name = icon_path if os.path.isfile(icon_path) else ""

    def Run(self):
        board = pcbnew.GetBoard()

        dlg = DrillOptionsDialog(None)
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
            furos = get_drill_holes(
                board,
                include_pth=opts["INCLUDE_PTH"],
                include_vias=opts["INCLUDE_VIAS"],
                include_npth=opts["INCLUDE_NPTH"],
            )
            furos = [
                (diameter, *mirror_xy(x, y, opts["MIRROR_AXIS"]))
                for diameter, x, y in furos
            ]
            grupos = agrupar_por_diametro(furos)

            # sort holes in each group by nearest neighbour;
            # each group starts from the last hole of the previous group
            pos_inicio = (0.0, 0.0)
            grupos_ordenados = []
            for diameter, lista in grupos:
                lista_ord = ordenar_vizinho_mais_proximo(lista, pos_inicio)
                grupos_ordenados.append((diameter, lista_ord))
                if lista_ord:
                    pos_inicio = lista_ord[-1]

            gcode = gerar_gcode_furacao(grupos_ordenados, opts)

            board_file = board.GetFileName()
            base = os.path.splitext(os.path.basename(board_file))[0] if board_file else "board"
            output_dir = opts["OUTPUT_DIR"]
            if not output_dir or not os.path.isdir(output_dir):
                raise ValueError(f"Output folder does not exist or is unavailable: {output_dir!r}")
            output_file = os.path.join(output_dir, base + "_drill.nc")

            with open(output_file, "w") as f:
                f.write(gcode)

            try:
                open_in_gsender(output_file)
                open_status = "\n\nOpened in gSender."
            except OSError as e:
                open_status = f"\n\nFile saved, but could not open in gSender: {e}"

            total = sum(len(lista) for _, lista in grupos_ordenados)
            resumo = ", ".join(
                f"{len(lista)}x{d:.3f}mm" for d, lista in grupos_ordenados
            )
            wx.MessageBox(
                f"{total} holes ({resumo})\n\nG-code saved to:\n{output_file}{open_status}",
                f"{PLUGIN_NAME} — Done",
                wx.OK | wx.ICON_INFORMATION,
            )

        except Exception as e:
            wx.MessageBox(str(e), f"{PLUGIN_NAME} — Error", wx.OK | wx.ICON_ERROR)
