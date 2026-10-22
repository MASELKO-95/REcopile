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
