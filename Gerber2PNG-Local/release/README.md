# Gerber2PNG Local for KiCad — Windows installer

1. Extract this folder from the release ZIP.
2. Run `Install-Gerber2PNG-Local.cmd` and approve the administrator prompt.
3. Select your KiCad 10.0 `3rdparty\plugins` folder when asked. The installer includes and installs its own 64-bit Python 3.13 runtime; a separate Python installation is not needed.
4. Wait for the installer to report that `http://127.0.0.1:4172/` is responding, then restart KiCad.

This installs the `Gerber2PNGLocalServer` Windows service and the modified Gerber2PNG PCB Editor action plugin. The service starts automatically and listens only on the local computer at port 4172. Logs are in `C:\Program Files\Gerber2PNG Local Server\logs`.

Run `Uninstall-Gerber2PNG-Local.cmd` to remove the service. It asks before deleting the plugin and service files; timestamped backups of any previous plugin installation are kept.

If installation reports that port 4172 is in use, close the other program using that port and run the installer again. See the service error log if Windows reports that the service failed to start.

NSSM version 2.24-101-g897c7ad is bundled under its public-domain terms. See `NOTICE-NSSM.md`.

The bundled Python 3.13.17 embeddable runtime is distributed under the PSF license. Its original `LICENSE.txt` is included in `PythonRuntime\python-3.13.17-embed-amd64.zip`; the archive SHA-256 is `9e35319bffedab8b36ad44d8f377cb4f1733bcec257a0b6d04d94f01486ddb38`.
