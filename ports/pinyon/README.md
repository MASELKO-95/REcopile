# Pinyon Shift 0.6.0 tools for RE:COPILE

This package contains source code, setup tools and the original Linux desktop
launcher, with a small source-location adapter for RE:COPILE. Supply
your own supported copy and follow the original project's requirements.

Pinyon Shift is developed by arcanite24 and its contributors, under BSD-2-Clause.
Its name, authors, license and support links are retained. Original sources are
pinned to `9331e453e9850d0fcc1c1606dee95db834a9d317` (v0.6.0):
https://github.com/arcanite24/pinyon-shift/tree/9331e453e9850d0fcc1c1606dee95db834a9d317

In RE:COPILE, install Pinyon Shift's tools, review the original README and BSD
license, then use the setup panel to select your own supported ISO or extracted
folder. The hub invokes the original setup and launch CLI directly. Setup may
download the original project's compiler and dependencies. Python 3 is required
by the upstream setup workflow.

After preparation, **Play** asks whether to play immediately or open the original
Pinyon Shift launcher. **Remember my choice** is optional. Change it later with
**Launch options** in the game's details. **Game settings** opens the same
original launcher; it keeps its upstream graphics, DLC, saves and other panels.
Remaining in-game settings are available with F6, as in the original launcher.
Both launch choices use the same prepared game and state directory. Opening
the launcher does not copy game files or count as a RE:COPILE play session.
Sessions started inside that launcher are not separately timed by the hub.
Managed launcher updates are provided by the reviewed RE:COPILE tools package;
the standalone launcher's automatic update check is disabled for this handoff.

For standalone use, extract the package and run:

```sh
python3 PinyonShift-Recopile.py --help
python3 PinyonShift-Recopile.py setup --iso /path/to/your-supported-copy.iso --json
python3 PinyonShift-Recopile.py launch
```

`UPSTREAM-LICENSE` and the embedded source `LICENSE` contain Pinyon's BSD terms.
The standalone bridge is RE:COPILE code under GPL-3.0-only; `RECOPILE-LICENSE`
contains that license. `launcher-notices/` retains the compiled launcher's runtime
and UI dependency notices. Package provenance and hashes are recorded in
`package.json`. The source payload includes the launcher sources and the exact
source-location adapter, alongside the pinned game's setup inputs. The adapter
and two save-testing helpers are described in `SOURCE-CHANGES.md`; the game
engine and renderer sources are unchanged. No compiled game is included.

Linux validation used private copies of existing 0.4 saves: driving on both
profiles, saving/reloading, and direct launch through RE:COPILE passed locally.
This does not qualify all dumps, distributions, races, audio or upscalers.
The official supported-dump catalog remains unchanged. Keep your old port and
make an independent copy of both `user` and `user-modded` before migration.
This tools package does not automatically import or overwrite old saves.
