#!/usr/bin/env python3
"""KiCad PCB Editor action: place the selected bounding-box center at X/Y."""

import pcbnew
import wx


PLUGIN_NAME = "Move Selection Center to X/Y"


class TargetPositionDialog(wx.Dialog):
    def __init__(self, parent, center_x_mm, center_y_mm):
        super().__init__(parent, title=PLUGIN_NAME)
        grid = wx.FlexGridSizer(cols=2, vgap=8, hgap=12)
        grid.AddGrowableCol(1)

        self.x_ctrl = wx.TextCtrl(self, value=f"{center_x_mm:.3f}", size=(130, -1))
        self.y_ctrl = wx.TextCtrl(self, value=f"{center_y_mm:.3f}", size=(130, -1))
        for label, ctrl in (("Target X (mm):", self.x_ctrl), ("Target Y (mm):", self.y_ctrl)):
            grid.Add(wx.StaticText(self, label=label), 0, wx.ALIGN_CENTER_VERTICAL)
            grid.Add(ctrl, 1, wx.EXPAND)

        note = wx.StaticText(
            self,
            label=(
                "Moves the selection's bounding-box center to these PCB coordinates. "
                "Y follows KiCad's PCB Editor coordinates. Save first; this action "
                "may not be undoable."
            ),
        )
        note.Wrap(390)

        main = wx.BoxSizer(wx.VERTICAL)
        main.Add(grid, 0, wx.ALL | wx.EXPAND, 12)
        main.Add(note, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 12)
        main.Add(self.CreateButtonSizer(wx.OK | wx.CANCEL), 0, wx.ALL | wx.ALIGN_RIGHT, 8)
        self.SetSizerAndFit(main)

    def get_target_mm(self):
        try:
            x = float(self.x_ctrl.GetValue().strip().replace(",", "."))
            y = float(self.y_ctrl.GetValue().strip().replace(",", "."))
        except ValueError as error:
            raise ValueError("Enter valid numeric X and Y coordinates in millimeters.") from error
        return x, y


def _selection_bounds(items):
    boxes = [item.GetBoundingBox() for item in items]
    left = min(box.GetLeft() for box in boxes)
    top = min(box.GetTop() for box in boxes)
    right = max(box.GetRight() for box in boxes)
    bottom = max(box.GetBottom() for box in boxes)
    return left, top, right, bottom


class MoveSelectionCenterPlugin(pcbnew.ActionPlugin):
    def defaults(self):
        self.name = PLUGIN_NAME
        self.category = "Placement"
        self.description = "Move selected PCB objects so their bounding-box center is at a typed X/Y."
        self.show_toolbar_button = True
        self.icon_file_name = ""

    def Run(self):
        items = list(pcbnew.GetCurrentSelection())
        if not items:
            wx.MessageBox(
                "Select one or more PCB objects first.",
                PLUGIN_NAME,
                wx.OK | wx.ICON_INFORMATION,
            )
            return

        # If a footprint and one of its children are both in the selection,
        # move only the footprint to avoid moving the child twice.
        selected_footprints = [item for item in items if isinstance(item, pcbnew.FOOTPRINT)]
        move_items = []
        for item in items:
            parent = item.GetParentFootprint() if hasattr(item, "GetParentFootprint") else None
            if parent is not None and any(parent == footprint for footprint in selected_footprints):
                continue
            if not callable(getattr(item, "Move", None)):
                wx.MessageBox(
                    f"A selected object ({type(item).__name__}) cannot be moved by this plugin.",
                    f"{PLUGIN_NAME} — Error",
                    wx.OK | wx.ICON_ERROR,
                )
                return
            move_items.append(item)

        if not move_items:
            wx.MessageBox("The selection contains no movable objects.", PLUGIN_NAME, wx.OK | wx.ICON_INFORMATION)
            return

        left, top, right, bottom = _selection_bounds(move_items)
        center_x = (left + right) // 2
        center_y = (top + bottom) // 2
        dialog = TargetPositionDialog(None, pcbnew.ToMM(center_x), pcbnew.ToMM(center_y))
        try:
            if dialog.ShowModal() != wx.ID_OK:
                return
            try:
                target_x_mm, target_y_mm = dialog.get_target_mm()
            except ValueError as error:
                wx.MessageBox(str(error), f"{PLUGIN_NAME} — Error", wx.OK | wx.ICON_ERROR)
                return
        finally:
            dialog.Destroy()

        delta = pcbnew.VECTOR2I(
            pcbnew.FromMM(target_x_mm) - center_x,
            pcbnew.FromMM(target_y_mm) - center_y,
        )
        if delta.x == 0 and delta.y == 0:
            return

        try:
            for item in move_items:
                item.Move(delta)
            pcbnew.GetBoard().SetModified()
            pcbnew.UpdateUserInterface()
        except Exception as error:
            wx.MessageBox(
                f"Could not move the entire selection: {error}",
                f"{PLUGIN_NAME} — Error",
                wx.OK | wx.ICON_ERROR,
            )
