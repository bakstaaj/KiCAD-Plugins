# KiCad Plugins

An index of Jim's KiCad PCB Editor plugins and modified plugin packages. Each
plugin has its own source folder, installation instructions, and versioned
release ZIP. Release ZIPs are also attached to the matching GitHub Releases.

| Plugin | What it does | Source and instructions | Latest package |
|---|---|---|---|
| [Gerber2PNG Local](Gerber2PNG-Local/README.md) | KiCad Gerber-to-PNG plugin with a local conversion service; includes solder-stencil DXF export. | [Gerber2PNG-Local](Gerber2PNG-Local/) | [Windows installer v1.2.4](https://github.com/bakstaaj/KiCAD-Plugins/releases/download/v1.2.4/Gerber2PNG-Local-v1.2.4-Windows.zip) |
| [KiCad CNC G-code Tools](KiCad-CNC-GCode/README.md) | PCB Editor actions for drilling and routing Edge.Cuts to GRBL G-code. | [KiCad-CNC-GCode](KiCad-CNC-GCode/) | [ZIP v1.0.0](https://github.com/bakstaaj/KiCAD-Plugins/releases/download/kicad-cnc-gcode-v1.0.0/KiCad-CNC-GCode-v1.0.0.zip) |
| [Move Selection Center to X/Y](KiCad-Move-Selection-Center/README.md) | Moves the selected objects so their bounding-box center lands at a typed coordinate. | [KiCad-Move-Selection-Center](KiCad-Move-Selection-Center/) | [ZIP v1.0.0](https://github.com/bakstaaj/KiCAD-Plugins/releases/download/kicad-move-selection-center-v1.0.0/KiCad-Move-Selection-Center-v1.0.0.zip) |
| [KiCad Git Integration](KiCad-Git-Integration/README.md) | Opens Git Gui for the board repository and offers to initialize a repository when missing. | [KiCad-Git-Integration](KiCad-Git-Integration/) | [ZIP v1.0.0](https://github.com/bakstaaj/KiCAD-Plugins/releases/download/kicad-git-integration-v1.0.0/KiCad-Git-Integration-v1.0.0.zip) |

## Installation

Open the plugin's README and follow its instructions. For manual installations,
copy the named plugin folder from the ZIP into KiCad's PCB Editor plugin
directory, then restart KiCad. The commonly used Windows user directory is
`%APPDATA%\kicad\10.0\3rdparty\plugins`; KiCad installations can use a
different version or configured location.

These packages are independent of KiCad and are not official KiCad releases.
