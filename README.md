# RE:COPILE

**A desktop game library for console games recompiled to run natively on PC.**

RE:COPILE brings game lists, project documentation, installation, updates and launch settings into one place. Emulator and local game entries provide alternatives when a native port is unavailable. Developed by [MASELKO-95](https://github.com/MASELKO-95).

**Public beta 0.2.2-beta.1.** [Download Linux packages](https://github.com/MASELKO-95/recopile/releases/tag/v0.2.2-beta.1) or the matching source archive. Linux is the current validation platform. Windows packaging still needs a Windows build and validation. Android is deferred.

## Languages

The interface currently has three languages: **English, Polish and Hungarian**.
**Japanese, Chinese and French are planned**, and are not available yet. Project READMEs and licenses are always shown in their original language.

## Your library

- Search an offline Xbox 360, Xbox One, PlayStation 2 and PlayStation 3 metadata catalog. Xbox One entries have no launch integration unless a port or local installation is assigned.
- Read game descriptions independently of artwork. Covers download for visible search results, **Download covers** for the current page / selected game, and the first game representing each visible collection tile. Text and artwork are cached locally; catalog browsing does not download new covers. Wikipedia descriptions currently use English source text.
- Keep a **recompilations only** view, or include emulation and other local games.
- Install project releases from their authors' GitHub repositories. Edit each source or follow its manual installation instructions.
- See separate **Linux / Windows package** labels and **device compatibility** reports. A downloadable program does not guarantee a working game.
- See declared technologies on search cards and game details. Undeclared graphics features remain unknown.
- Use **Measurements** to detect local CPU/GPU/RAM information, record a timed direct game session with MangoHud (Linux) or console PresentMon (Windows), or import their CSV logs. Summaries show measured FPS, frame times, duration, game version and the graphics settings you enter. Results remain local until you choose to export or publish a report.
- Use **On this PC** to filter declared packages and local executables for the host system. Linux also lists Windows packages with an explicit **Proton / Wine · untested** label; these packages can be installed manually and linked as local games.
- Add existing programs like a non-Steam game. On Linux, select an installed **Proton** version or **Wine** for Windows executables. Each game gets a separate compatibility prefix; an installed UMU launcher can also be used.
- Optionally connect installed **Steam** PC games from RE:COPILE collections. This feature is **off by default**: enable it in **Collections** or Settings. Only declared collection App IDs are checked, including registered libraries on other drives; unrelated Steam titles are not imported. While enabled, startup checks and **Scan Steam** refresh the matches, and Settings accepts an extra SteamLibrary folder. Linux (including Flatpak) and Windows discovery are supported. Scanning leaves game files in place and does not download artwork or require Steam sign-in. **Launch in Steam** delegates to the installed client. Steam hours and achievements are not synchronized, and the client handoff is not counted as a game session.
- Open Forza and Ratchet & Clank collections from first-game cover tiles. Each series lists its console projects and official PC releases together in release order. Prepare a port or connect an existing PC installation, then launch a ready game with **Play**. Store links retain availability labels; projects in development retain their own status.
- Keep profiles, per-game hours and launch counts, play history and launcher activity badges local. Sessions are recorded for the profile selected when the program starts. Each game's player card can reopen its details or launch its connected installation. In-game achievement integration is planned and has no reported count yet. Export a summary image to share yourself, for example on Discord.
- Review mod packages with a manifest, README, license and file hashes. Activation requires an explicit mod folder or adapter supported by the port. Creator templates and the package builder provide Linux / Windows installation helpers.

## Sources and updates

**A port supplies software; you supply your own game data.** RE:COPILE does not distribute console game images, BIOS files, firmware, copyrighted game assets or unpublished commercial game source code. Follow each project's instructions to prepare your own copy. There is no universal automatic “ISO to native game” conversion.

Before downloading, the launcher presents the project's actual **README, license, release information and author support links**. Open the License tab and accept its terms separately from the README acknowledgment. Installation is blocked if the license is unavailable. Documentation and the accepted license hash stay with the installed version. Automatic updates require prior consent; a changed license requires fresh acceptance. Updates are checked at startup, announced, then approved updates are downloaded at the next startup. Previous port versions and user data are retained.

Game additions and metadata edits update a single runtime file, `data/registry.json`.
The launcher fetches this catalog without replacing application code or reinstalling.
Generated public project lists follow the same catalog.

The launcher's own license appears automatically on first launch and after a
launcher version update. Acceptance is remembered for ordinary restarts.
An unchanged game license with prior automatic-update consent needs an update
notification; it does not repeatedly open the license dialog. Changes or missing
license documents pause automatic installation.

The in-app **How to play** page explains the shared Xbox 360 / PS2 workflow:
choose a project, review its README and accept its license, prepare your own copy,
configure or build, then launch. It includes separate Xbox 360 console / USB
and PS2 DVD instructions. [Read the guide](docs/how-to-play.md).

**From disc to game** links to porting tools, including ShiftGlue SDK and
PS2Recomp, and to emulator documentation. Each game's details retain its actual
source, README, license and compatibility status. Supported integrations use
RE:COPILE's own setup panel and direct launch while retaining upstream software,
licenses and saves.

Project authors: [GitHub profiles](REPOSITORIES.md).
Project sources, availability and status: [PORTS.md](PORTS.md).

PCSX2 and RPCS3 are managed separately. Their BIOS / firmware instructions and per-game compatibility apply. Xbox 360 emulation can use a user-configured local adapter; an emulator is not included just because a title appears in the catalog.

GitHub accounts are **optional**. Sign in on GitHub in your external browser to review and submit an issue. RE:COPILE does not collect your GitHub password, account token or browser session. Public downloads work without an account. Compatibility reports start as local drafts. Public reports require maintainer approval; the initial database is empty.

Optional support: [GitHub Sponsors](https://github.com/sponsors/MASELKO-95). Each game project keeps its own authors and funding links. Linux and Windows contain no advertising. Optional ads are a future Android feature only, requiring an explicit choice and the applicable consent flow.

## Steam-style folders

Choose one or more libraries, including libraries on other drives:

```text
RecopileLibrary/
  recopileapps/
    common/Game title (Platform)/
      versions/source-version/
        Recopile-project-info/README.md, LICENSE, project.json
      current/                 # Linux; current.json on Windows
      content/                 # your prepared project data
      gamefiles/               # reference to your own copy
      mods/
    engines/
    downloading/
    discimages/
    appmanifest_*.json
  userdata/local/              # saves, settings, compatibility prefixes
```

A new default library affects future installations. Existing installations retain their locations. Local shortcuts leave the original files in place.

## Development

Python 3.11 or later and Node 22 or later are recommended for building. The packaged hub does not require Python or Node. Individual port setup tools may require their own dependencies.

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-build.txt
cd frontend
npm ci
npm run build
cd ..
./start.sh
```

The development UI uses a loopback service at `127.0.0.1` to access the library and filesystem. It is not a game server and is not exposed to the network. The Electron window chooses an available local port itself.

```sh
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python tools/freeze_backend.py
cd desktop
npm ci
npm run package
```

Build the backend on the target operating system. Linux packaging produces an
AppImage, a Debian/Ubuntu DEB and an Arch/Manjaro pacman package; the current
bundled Linux runtime requires x86-64 and glibc 2.38 or later. Windows NSIS needs
a Windows backend build. See [desktop packages](docs/desktop-packages.md).
Launcher self-updates between public releases remain unqualified; catalog updates are independent. Beta installers are marked as pre-release on GitHub.

See the [catalog format](docs/catalog-format.md), [roadmap](ROADMAP.md), [privacy](PRIVACY.md) and [third-party notices](THIRD_PARTY_NOTICES.md). Distribution and Discord settings live in `data/distribution.json`. An unset Discord invite is shown as unconfigured.

The console catalog combines Libretro metadata (Xbox 360 / PS2 / PS3) and attributed Wikipedia game lists (Xbox One), including regional variants, repeated titles and announced entries. Its entry count is not a count of unique, released or playable games. Source URLs and hashes are retained in `data/catalog.json.gz`. “No port assigned” means no confirmed entry in this catalog; it does not establish that no port exists elsewhere.

## License

Copyright (C) 2026 **MASELKO-95**. Original RE:COPILE code and materials use [GNU GPLv3](LICENSE) (`GPL-3.0-only`). Preserve copyright and license notices, mark distributed modifications with their date, and provide the Corresponding Source when distributing executables as required by GPLv3. Commercial use is allowed. Third-party components and downloaded ports retain their own terms. See [NOTICE](NOTICE) and [license notes](docs/licensing.md).

Game names and trademarks belong to their respective owners. RE:COPILE is not affiliated with console or game publishers.
