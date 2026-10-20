# Third-party components and notices

GNU GPLv3 covers original RE:COPILE code and materials. Independent components,
projects, games, trademarks and data retain their own rights and terms.
Related repositories: [REPOSITORIES.md](REPOSITORIES.md).

- React: MIT, https://github.com/facebook/react/blob/main/LICENSE
- Phosphor Icons: MIT, https://github.com/phosphor-icons/react/blob/master/LICENSE
- Electron: MIT and Chromium licenses. Electron includes LICENSE,
  LICENSES.chromium.html and its dependency notices.
- electron-builder / electron-updater: MIT,
  https://github.com/electron-userland/electron-builder/blob/master/LICENSE
- Python: PSF, https://docs.python.org/3/license.html
- Chaquopy: MIT, https://github.com/chaquo/chaquopy/blob/master/LICENSE
- Pillow: HPND, https://github.com/python-pillow/Pillow/blob/main/LICENSE
- py7zr: LGPL-2.1, https://github.com/miurahr/py7zr/blob/master/LICENSE
- Inter and Barlow Condensed: SIL Open Font License. Full texts are included in
  `frontend/public/assets/fonts/*-LICENSE.txt` and the frontend build.
- Google Mobile Ads / UMP: Google's terms; only a future Android variant
  configured for advertising. https://developers.google.com/admob/android/privacy

Ports and emulators are downloaded from their configured GitHub Releases.
Pinyon Shift 0.6.0 Linux source tools are hosted in RE:COPILE Releases, pinned
to arcanite24/pinyon-shift commit 9331e453e9850d0fcc1c1606dee95db834a9d317.
Pinyon Shift and the two included save-test helpers retain BSD-2-Clause terms;
see `ports/pinyon/UPSTREAM-LICENSE`, the package's `UPSTREAM-LICENSE`, and its
embedded source `LICENSE`. `SOURCE-CHANGES.md` records the added helpers.
The launcher retrieves the actual README and LICENSE for the selected release,
shows them before downloading the program, keeps them in `Recopile-project-info`
and displays funding links declared in FUNDING.yml. It does not repackage ISO,
BIOS or original game assets. Original upstream project names are retained.

Catalog metadata is based on public Libretro/libretro-database data:
https://github.com/libretro/libretro-database. Provenance, file revisions,
dates and source hashes are recorded in `data/catalog.json.gz` and the catalog
information shown in the application. Metadata rights are separate from rights
to the games themselves.

Xbox One entries come from English Wikipedia's “List of Xbox One games (A–L)”
and “(M–Z)”. Attribution: Wikipedia contributors, CC BY-SA 4.0.
Source URLs and retrieved-content hashes are stored in `data/catalog.json.gz`.
Descriptions requested from Wikipedia stay in their original English and are
accompanied by an article link, contributor attribution and CC BY-SA 4.0 label.
https://en.wikipedia.org/wiki/List_of_Xbox_One_games_(A%E2%80%93L)
https://en.wikipedia.org/wiki/List_of_Xbox_One_games_(M%E2%80%93Z)
https://creativecommons.org/licenses/by-sa/4.0/

Artwork cached in the local preview comes from Wikipedia, Libretro thumbnails
and xlenore/ps2-covers. Illustrations remain the property of their respective
creators/publishers. Default packaging excludes this local artwork collection:
downloading a cover does not grant redistribution rights. Public distributions
should use original artwork or appropriately licensed materials. The interface
provides a placeholder when no cover is available.

New images from Wikipedia/Wikimedia are downloaded for visible search
results, an explicit player request or the first game on a visible collection
tile. Whole-series artwork is not fetched by opening a collection. The `covers/` cache in local application
data is not part of a release. Article links identify image provenance;
Wikipedia's text license does not automatically license a game publisher's art.

Standalone builds include binary dependencies with their original licenses.
Distributors must retain the required notices and provide source for components
whose licenses require it. Use of Xbox, PlayStation or a game title does not
imply affiliation with or endorsement by its publisher.
