# Pinyon Shift 0.6.0 tools for RE:COPILE

This package contains source code and setup tools, not a compiled game. Supply
your own supported copy and follow the original project's requirements.

Pinyon Shift is developed by arcanite24 and its contributors, under BSD-2-Clause.
Its name, authors, license and support links are retained. Original sources are
pinned to `9331e453e9850d0fcc1c1606dee95db834a9d317` (v0.6.0):
https://github.com/arcanite24/pinyon-shift/tree/9331e453e9850d0fcc1c1606dee95db834a9d317

In RE:COPILE, install Pinyon Shift's tools, review the original README and BSD
license, then use the setup panel to select your own supported ISO or extracted
folder. The hub invokes the original setup and launch CLI directly. Setup may
download the original project's compiler and dependencies. Python 3 is required
by the upstream setup workflow. The separate graphical Pinyon launcher is not
required by this integration.

For standalone use, extract the package and run:

```sh
python3 PinyonShift-Recopile.py --help
python3 PinyonShift-Recopile.py setup --iso /path/to/your-supported-copy.iso --json
python3 PinyonShift-Recopile.py launch
```

`UPSTREAM-LICENSE` and the embedded source `LICENSE` contain Pinyon's BSD terms.
The standalone bridge is RE:COPILE code under GPL-3.0-only; `RECOPILE-LICENSE`
contains that license. Package provenance and hashes are recorded in
`package.json`. The payload file selection follows the pinned original launcher
packager. Two save-testing helpers are added, with their changes described in
`SOURCE-CHANGES.md`; the game engine and renderer sources are unchanged.

Linux validation used private copies of existing 0.4 saves: driving on both
profiles, saving/reloading, and direct launch through RE:COPILE passed locally.
This does not qualify all dumps, distributions, races, audio or upscalers.
The official supported-dump catalog remains unchanged. Keep your old port and
make an independent copy of both `user` and `user-modded` before migration.
This tools package does not automatically import or overwrite old saves.
