# Gerber2PNG Local for KiCad

This package combines Jim's modified Gerber2PNG KiCad action plugin with a local build of the Gerber2PNG web application and its local LightBurn bridge. The web app listens only on `127.0.0.1:4172`.

The local app can export loaded KiCad Excellon drill files as NC G-code. It uses the top-side orientation and moves the board Edge.Cuts lower-left corner to X0 Y0. Holes are grouped by drill diameter in ascending order, with a manual M0 tool-change pause for each size. Set safe Z, drill depth, plunge feed, spindle, and tool-change height in the export dialog. Routed slots encoded with Excellon G85 are not currently supported.

## Install from the release ZIP

1. Extract the ZIP to a regular folder.
2. Run `Install-Gerber2PNG-Local.cmd` and approve the Windows administrator prompt. The installer asks for the KiCad `3rdparty\plugins` folder.
3. The installer installs its bundled 64-bit Python 3.13 runtime for the local service. You do not need to install Python separately.
4. Wait for the installer to confirm that the local page answers at `http://127.0.0.1:4172/`, then restart KiCad.
5. In PCB Editor, use the Gerber2PNG toolbar action. The plugin exports the board files and opens the local app.

The service is installed as the Windows service `Gerber2PNGLocalServer` and starts automatically. It runs under the Windows Local System account. The installer backs up an existing copy of the plugin folder with a timestamp before installing the new files. The service log files are in `C:\Program Files\Gerber2PNG Local Server\logs`.

The installer sets the machine environment variables `GERBER2PNG_SERVER_ROOT` and `GERBER2PNG_PYTHON` for the plugin. The bundled Python runtime is installed under `C:\Program Files\Gerber2PNG Local Server\Python`. Restart KiCad after installation so it reads those values.

## Remove

Run `Uninstall-Gerber2PNG-Local.cmd` as an administrator. It removes the service and asks before removing the selected plugin and service files. Timestamped plugin backups are left in place.

## Manual paths

- Service files: `C:\Program Files\Gerber2PNG Local Server`
- Service URL: `http://127.0.0.1:4172/`
- KiCad plugin folder: selected during installation
- Logs: `C:\Program Files\Gerber2PNG Local Server\logs\service-out.log` and `service-error.log`

If port 4172 is already in use, stop the process using it and run the installer again. The plugin can also start the local server itself if the Windows service is stopped.

## Source layout

- `server/source/` contains the working source snapshot used for this build.
- `plugin/` contains the KiCad plugin source.
- `installer/` contains the PowerShell installers.
- `release/` is the self-contained folder included at the root of the downloadable release ZIP.

The web application is based on [Fab Lab Kerala's Gerber2PNG](https://github.com/fablabkerala/gerber2png). The local modifications and plugin are maintained in this repository. NSSM attribution and archive hash are in [NOTICE-NSSM.md](NOTICE-NSSM.md).
