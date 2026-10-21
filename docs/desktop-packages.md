# Desktop packages

Version 0.2.2-beta.3 has public beta Linux x86-64 packages in [GitHub Releases](https://github.com/MASELKO-95/recopile/releases/tag/v0.2.2-beta.3), built in `artifacts/desktop/`:

- `Recopile-0.2.2-beta.3-linux-x64.pkg.tar.xz`: Arch / Manjaro package, installed by
  the system package manager with an application menu entry.
- `Recopile-0.2.2-beta.3-linux-amd64.deb`: Debian / Ubuntu package, installed by the
  system package manager with an application menu entry.
- `Recopile-0.2.2-beta.3-linux-x86_64.AppImage`: executable portable Linux application.
- `Recopile-0.2.2-beta.3-source.zip`: explicit source/build inputs, notices, licenses
  and a SHA-256 inventory. It excludes game data, local state and cover caches.

The bundled Linux runtime requires glibc 2.38 or later, GTK 3 and a desktop
graphics environment. A DEB is not an Arch package. Use the package for the
distribution or the AppImage; the AppImage also needs an available FUSE 2 runtime
or its supported extract-and-run mode. Players do not need Python or Node.

Packaged startup checks use isolated local state and disable network updates.
Extracting and starting a package does not qualify every target distribution or
perform an operating-system installation. Actual Windows installation and capture
need testing on Windows. The Windows NSIS configuration remains in
`desktop/package.json`; a Linux service must never be included in a Windows build.

Game catalog updates download `data/registry.json`; they do not replace the
application or require an installer. Game programs update from their own project
Releases after notice and prior consent, with a fresh review if the license changes.
New launcher features require a launcher version update. AppImage / Windows
automatic self-updates need published installer metadata and prior consent;
DEB / pacman application updates are applied through the system package manager.

Build the frontend, freeze the backend using the intended Python environment,
then run desktop packaging. `--publish never` keeps the build local. For Linux,
the build used Python Build Standalone 3.13.15 through uv, PyInstaller 6.22.3,
Pillow 12.3.0, py7zr 1.1.4, Electron 44.7.0 and electron-builder 26.15.3.
Bundled GCC libraries account for the glibc 2.38 baseline. See the lockfiles and
requirements files for dependencies. `tools/package_source.py` generates the
source archive using an explicit set of public inputs.

The player packages contain no owner publishing application, publication UI or
publication service. Catalog metadata updates are downloaded independently.
