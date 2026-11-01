# Gerber to SVG Converter

Convert Gerber files into SVG format, enabling users to download them as PNG images. This React + Vite application offers intuitive layer toggling, top and bottom side viewing, and support for double-sided PCB milling.

---

## Table of Contents

- [Installation](#installation)
- [Usage](#usage)
  - [Development Server](#running-the-development-server)
  - [Production Build](#building-for-production)
  - [Serving the Production Build](#serving-the-production-build)
  - [Accessing the Hosted Application](#accessing-the-hosted-application)
- [Features](#features)
- [Dependencies](#dependencies)
- [Contributing](#contributing)
- [License](#license)
- [Acknowledgments](#acknowledgments)
- [Contact](#contact)

---

## Installation

```bash
git clone https://github.com/MidlajN/react-gerber-converter.git
cd react-gerber-converter
npm install
```

## Usage

#### Running the Development Server

```bash
npm run dev
```

Access the application at `http://localhost:5173`.

#### Building for Production

```bash
npm run build
```

This generates a production-ready build.

#### Serving the Production Build

```bash
npm run preview
```

Serves the production build locally at `http://127.0.0.1:4172`.

### Send PNGs to LightBurn

Build the app with `npm run build`, then run `start-gerber2png-local.cmd` to start the local UI and LightBurn API bridge at `http://127.0.0.1:4172`. The bridge requires LightBurn 2.2 or newer. Choosing Connect launches the newest detected LightBurn installation if it is closed, then asks you to approve the upload permission. In the PNG list, choose the LightBurn button, connect, then enter the desired X/Y workspace coordinates in millimeters and select the point of the image to place there. If LightBurn is installed in a nonstandard location, set the `LIGHTBURN_EXE` environment variable to its `LightBurn.exe` path before starting the server.

To start the Gerber2PNG local server when you sign in to Windows, run `install-startup-tasks.ps1` from PowerShell in this folder. The server provides the web UI and LightBurn API bridge; the exporter launches LightBurn when needed. Run `powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\install-startup-tasks.ps1 -Uninstall` to remove the startup task. Set `PYTHONW_EXE` before installing if Python's `pythonw.exe` is not at `C:\msys64\ucrt64\bin\pythonw.exe`.

### Accessing the Hosted Application

Hosted version available at [gerber2png.fablabkerala.in](https://gerber2png.fablabkerala.in/).

## Features

- **Gerber to SVG Conversion**: Convert Gerber files into SVG format.
- **Download as PNG**: Export SVG images as PNG files.
- **Layer Toggle**: Toggle visibility of individual layers.
- **Top and Bottom Side View**: Switch between top and bottom sides of the PCB.
- **Support for Double-Sided PCB Milling**: Handles PNG images for double-sided PCB milling.

## Dependencies

- `PCBStackup`: Library for handling PCB stack-up data.
- `gerberToSvg`: NPM package for converting Gerber files to SVG.
- `jszip`: JavaScript library for creating, reading, and editing ZIP files.

## Contributing

Contributions are welcome! Fork the repository and submit pull requests.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

<br>

> *If there any known bugs found or run into any issues please let me know. Please enjoy and feel free to share your opinion, constructive criticism, or comments. Email: 👉 midlaj4n@gmail.com  Thank you!*

---
