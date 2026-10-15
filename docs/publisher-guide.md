# Publishing RE:COPILE and adding ports

Profiles and play history stay on the player's device. GitHub hosts source,
releases and optional feedback. Discord is used for community discussion and
links that the publisher or player shares manually.

## Current desktop release process

The project repository is `MASELKO-95/recopile`; the Discord invite is configured
in `data/distribution.json`. Linux and Windows are the current targets.
Android builds and advertising are deferred. There is currently no GitHub
Actions release workflow in this workspace: a tag alone does not build or
publish installers.

1. Review the source tree and include the exact Corresponding Source, build
   instructions, GNU GPLv3, NOTICE and third-party terms with the release.
   Keep copyright and modification notices. Commercial distribution is allowed
   subject to GPLv3; see [license notes](licensing.md).
2. Exclude `.local/`, game libraries, ISO, BIOS, saves, generated guest code,
   proprietary assets and private local research archives. The desktop bundler
   also excludes artwork cached during development.
3. Run the backend tests and frontend production build described in the README.
   Freeze the Python service, then package the Electron application. Review
   resulting AppImage/DEB/NSIS packages on their actual target systems.
4. Publish reviewed installers, updater metadata, SHA-256 checksums and their
   matching source manually through GitHub Releases. Windows signing and
   Linux updater qualification require their own validation. An unsigned
   installer may show an operating-system prompt.

The identity publishing helper uploads only an explicit list of reviewed
public documents. It does not upload this workspace, game files or installers.

## Add a game project

1. In the game's repository, provide its README, actual LICENSE, platform
   requirements, exact gameplay status and optionally `.github/FUNDING.yml`.
   For a fork, retain upstream copyright and license notices and record changes.
2. Publish a built **port program** in Releases, for example `Game-Linux.tar.gz`
   or `Game-Windows.zip`, with checksums and required source. Players supply
   their own game data. Do not label a source archive as a ready game.
3. Enable publisher mode in RE:COPILE. Add the GitHub source, inspect Releases
   and enter the package and executable for each supported operating system.
   An empty system means no available package. Projects without packages can
   instead be catalogued as planned or experimental development sources.
4. In Sources, export the catalog entry and merge it into the publisher file:

   ```sh
   python3 tools/register_game.py recopile-game-entry.json
   python3 tools/register_game.py --check
   python3 tools/update_port_list.py --check
   ```

5. Review the generated PORTS.md, requirements and source links. Test the adapter
   with your own supported game copy before making gameplay claims. Publish
   the registry and port list. Clients can fetch `data/registry.json` from the
   configured launcher repository when checking for updates.

For another version of the same port, publish a new release in the **game
project's repository** with the same asset naming scheme. Keep existing tags
immutable and game/source identifiers stable. The launcher retains the actual
upstream README, license and funding links. Automatic updates need prior
consent and a visible notice; changed licenses need fresh review. Do not copy
independent upstream binaries into the hub's repository just to list a port.

## Local projects and RE:COPILE Edition

A player can connect a trusted built executable or a supported local project.
The source folder stays in place. Ratchet 3 / Up Your Arsenal is an experimental
Linux RE:COPILE Edition; its intro/title-screen progress does not establish full
gameplay. Forza Horizon uses Pinyon Shift's original tools through the hub's
setup panel. The independent FH2 development fork has no ready game package.
The [Xbox guide](how-to-play-xbox.md) explains the player-facing preparation.

## Compatibility reports

A player creates a local report with the port version, hardware and test result,
then reviews and submits a GitHub issue in their browser. A maintainer must
review public reports before adding them to `data/compatibility.json`.
No automatic issue-to-catalog workflow is included at present. Clients can
fetch that approved file alongside the registry. A report for one machine or
version does not guarantee another machine or later build.

## Workshop and support

Use Discord for descriptions and GitHub Releases for durable mod packages.
Include the manifest, README, license, checksums and declarative installer.
Activation needs an actual supported port adapter; a template does not prove
that a port supports mods. Announcements are not sent automatically.

Launcher support is optional: https://github.com/sponsors/MASELKO-95.
Each port's FUNDING.yml links support its own authors. Linux and Windows have
no ads. Optional AdMob/UMP integration is a deferred Android feature, disabled
by default; do not add desktop AdSense.
