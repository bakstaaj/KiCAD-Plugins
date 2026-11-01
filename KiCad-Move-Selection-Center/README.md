# Move Selection Center to X/Y

KiCad PCB Editor action that moves the selected objects so the selection's
bounding-box center lands at a typed X/Y coordinate in millimeters.

## Install

1. Close KiCad.
2. Copy `com_github_bakstaaj_move_selection_center` into KiCad's PCB Editor
   plugin directory, usually `%APPDATA%\kicad\10.0\3rdparty\plugins` on
   Windows.
3. Restart KiCad and open the PCB Editor. Use the **Move Selection Center to
   X/Y** toolbar action.

Save the board before using the action. It moves selected objects directly and
may not be undoable by KiCad.
