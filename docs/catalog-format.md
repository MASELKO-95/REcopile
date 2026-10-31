# Catalog metadata

The player launcher reads `data/registry.json` from its configured GitHub
repository during update checks. Catalog updates do not replace application code,
require reinstalling the launcher or trigger application license onboarding.
Downloaded metadata remains available after an offline restart. Player-added
sources, installations, saves and profile data retain their local settings.

Schema version 1 contains `sources` and `featured` arrays. Sources declare stable
IDs, GitHub repositories, source platform, project type, supported package names,
relative executable paths and documentation. An entry without a package can
describe a planned or experimental project. Package availability is separate
from verified gameplay. Catalog data never contains executable installer commands.

Featured entries identify games by stable platform/match pairs. They can contain
descriptions with source attribution, tags, declared technologies, text test notes
and explicitly selected hardware measurement reports. Tags and technologies accept
up to 40 unique, printable names of 1–60 characters. Known technology identifiers
have friendly labels; custom names are displayed as supplied. Undeclared features
remain unknown. A measurement describes that capture and does not prove full
gameplay support.

`catalog_version`, `catalog_notes` and `catalog_updated_at` describe the metadata
update. Public `PORTS.md` and `REPOSITORIES.md` are generated from the same registry.
Entries with `public_listing:false` are omitted from those public project lists.
No game images, ISO, BIOS, saves, profile records or raw performance logs belong in
the registry.

Game programs update separately from the original projects' GitHub Releases.
Automatic installation requires prior consent and a visible update notice;
changed or missing licenses pause unattended updates. New launcher functionality
requires an application update.

## Community project lists

`tracked_lists` stores snapshots of the supported public Xbox 360 project
lists, with original page links and project repository references. The player
checks them during normal update checks when `track_catalog_lists` is enabled.
Sources shows each list, local search, pagination and whether a project has a
source attached to a game. An offline or unreadable response retains the last
successful snapshot. These requests fetch text metadata, never artwork or games.

New source references use `development_status: "listed"` and
`discover_packages: true`. Their operating-system packages and gameplay remain
unverified. When the player chooses Install port, the service can resolve a
single matching release asset for the current operating system. AppImages,
archives and Windows setup EXEs use the existing document review and license
hash checks. Multiple matching packages or executable entry points require
explicit source configuration. Discovery never runs instructions from a README.
Resolved packages remain available after restarting offline. A maintained
catalog can later replace a reference with a reviewed per-title integration.

`adapter: "installer"` stages an author's original Windows setup executable.
It can run through the player's existing Proton/Wine on Linux when selected
as a Windows compatibility package. It does not mark the resulting game ready or locate an arbitrary installation
elsewhere on the computer. The player supplies their own game data to the
author's setup and can connect the resulting executable. Normal archive-based
integrations keep their existing configuration and ready-state workflow.

Linux prefers a declared native package. When only a Windows package is
available, the normal download flow clearly labels it as Windows and uses the
player's installed Proton or Wine for setup and launch. The compatibility
prefix is local to the game and persists between versions. Downloading or
opening setup does not establish Linux gameplay compatibility. The existing
per-game settings choose the runner and Proton version; no runtime is silently
downloaded. Existing local executable bindings and their runner choices survive
package updates.

`scan_releases` selects compatible assets across recent releases, including
non-SemVer port tags. `allow_prerelease` permits beta assets; it does not enable
automatic installation. Publisher catalog versions older than the bundled or
already downloaded dated catalog do not roll source metadata back.

## Official manual downloads

`origin: "external"` describes software distributed on an author's own page.
It requires `download_page` (a permanent HTTPS page without credentials or
query tokens), `author`, `manual_systems` and `auto_update: false`. GitHub
asset patterns and release routing are empty. RE:COPILE opens the author's
page; the player reviews its terms, downloads and extracts the program there,
then connects the executable. These sources never enter the automatic
GitHub installer or update queue. Windows downloads appear as manual options
on Windows and through Proton/Wine on Linux, without claiming tested gameplay.
The wrapper does not provide the player's commercial game data.

## Separate component releases

`repos_by_system` can select a package host for each operating system.
`release_tags_by_system` optionally pins that system to an immutable release tag
instead of the host repository's latest application release. Other systems keep
their existing release selection. `documentation_repo` and an immutable
`documentation_ref` retain the actual upstream README, license and authors.
Pinyon Shift's Linux source-tools archive uses these fields; its game code is
built locally from the player's supported data.
