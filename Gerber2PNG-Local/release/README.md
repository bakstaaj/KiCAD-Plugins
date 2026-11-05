# Gerber2PNG Local for KiCad — Windows installer

1. Extract this folder from the release ZIP.
2. Run `Install-Gerber2PNG-Local.cmd` and approve the administrator prompt.
3. Select your KiCad 10.0 `3rdparty\plugins` folder when asked. The installer includes and installs its own 64-bit Python 3.13 runtime; a separate Python installation is not needed.
4. Wait for the installer to report that `http://127.0.0.1:4172/` is responding, then restart KiCad.

This installs the `Gerber2PNGLocalServer` Windows service and the modified Gerber2PNG PCB Editor action plugin. The service starts automatically and listens only on the local computer at port 4172. Logs are in `C:\Program Files\Gerber2PNG Local Server\logs`.

After loading Gerber files, use **Stencil DXF** in the output panel to export the top or bottom solder-paste apertures together with the board edge. The DXF uses millimeters and separates the geometry onto `STENCIL_APERTURES` and `BOARD_EDGE` layers.

Use **Drill G-code** to convert loaded KiCad Excellon drill files into one NC file. Coordinates use top-side orientation, with the lower-left of the Edge.Cuts outline at X0 Y0. Drill tools are sorted from smallest to largest and each size has a manual M0 tool-change pause. The dialog lets you set drill depth, safe Z, tool-change Z, plunge feed, spindle speed, and dwell. Routed slots encoded with Excellon G85 are not supported.

In normal PNG generation, bottom-side layer exports are mirrored horizontally about the Y axis while top-side exports are unchanged. The existing Cubiko-specific flip behavior is retained.

Run `Uninstall-Gerber2PNG-Local.cmd` to remove the service. It asks before deleting the plugin and service files; timestamped backups of any previous plugin installation are kept.

If installation reports that port 4172 is in use, close the other program using that port and run the installer again. See the service error log if Windows reports that the service failed to start.

NSSM version 2.24-101-g897c7ad is bundled under its public-domain terms. See `NOTICE-NSSM.md`.

The bundled Python 3.13.17 embeddable runtime is distributed under the PSF license. Its original `LICENSE.txt` is included in `PythonRuntime\python-3.13.17-embed-amd64.zip`; the archive SHA-256 is `9e35319bffedab8b36ad44d8f377cb4f1733bcec257a0b6d04d94f01486ddb38`.
