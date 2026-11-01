# KiCad CNC G-code Tools

Modified KiCad PCB Editor actions for generating drill and board-edge G-code.
The package registers two toolbar actions: **Drill to G-code** and **Edge Cuts
to G-code**.

## Install

1. Close KiCad.
2. Copy the `com_github_andresarmento_kicad2gcode` folder from this package into
   KiCad's PCB Editor plugin directory. The usual Windows user location is
   `%APPDATA%\kicad\10.0\3rdparty\plugins`; use your configured plugin folder
   if you have a custom location.
3. Start KiCad and open the PCB Editor. The two actions appear as toolbar
   buttons.

The plugins use KiCad's bundled Python, `pcbnew`, and `wxPython`. They have no
additional Python package dependency. Generated files are saved in the chosen
output folder; the configured gSender Edge executable is opened when available.

## Attribution

The CNC tools are based on André Sarmento's [kicad2gcode](https://github.com/andresarmento/kicad2gcode)
plugin, whose project README identifies the project as MIT licensed. This
package contains Jim's modifications for the described workflow. The upstream
repository currently does not include a separate LICENSE file.
