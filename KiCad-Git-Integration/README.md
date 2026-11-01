# KiCad Git Integration

Modified version of the [adamws/kicad-git](https://github.com/adamws/kicad-git)
PCB Editor action. It opens Git Gui for the board's repository and offers to
initialize a repository in the board folder if none exists. Repository
initialization does not stage or commit files.

## Install

1. Install Git for Windows (Git Gui included) or MSYS2 Git.
2. Close KiCad.
3. Copy `com_github_adamws_kicad-git` into KiCad's PCB Editor plugin directory,
   usually `%APPDATA%\kicad\10.0\3rdparty\plugins` on Windows.
4. Check `config.ini` in the plugin folder. Its included paths point to
   `C:\msys64\usr\bin\git.exe`; change them if Git is installed elsewhere.
5. Restart KiCad and open a board.

The upstream GPL-3.0 license is included in `LICENSE`.
