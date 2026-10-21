# Changes to the pinned Pinyon Shift source payload

2026-10-20, MASELKO-95:

- Add `tools/create-render-seed.py` with an explicit `--allow-cold-cache`
  option for older Linux states. The default still requires shader catalogs.
  Copy and hash all independent `user-*` profiles alongside the base user.
  Refuse to replace an existing seed. This helper is for private test snapshots;
  the setup process does not import saves automatically.
- Add `tests/test_cold_render_seed.py` covering the strict default, explicit
  cold cache, both profiles, unchanged originals and overwrite refusal.

2026-10-21, MASELKO-95:

- Include the original Linux Avalonia launcher sources from the same pinned
  revision and its self-contained Linux x86-64 executable.
- In `launcher/PinyonShift.Launcher.Desktop/Installation.cs`, accept the explicit
  `PINYON_SHIFT_SOURCE_ROOT` supplied by RE:COPILE after checking the original
  source-root requirements. Retain the original source-payload/build readiness
  checks. This avoids extracting a second source tree and reconnects the
  original UI to the prepared build, game directory and existing state.
- The original launcher UI and its game-setting behavior are unchanged. The
  hub passes the original state/game/install environment overrides and disables
  the standalone update check; launcher updates arrive with reviewed tools.
- The full launcher project and shared sources are in the embedded source zip.
  Build the desktop project using .NET SDK 8, `dotnet publish -c Release -r
  linux-x64 --self-contained true -p:Version=0.6.0 -p:FileVersion=0.6.0.0
  -p:DebugType=none -p:PathMap=/path/to/source=/src/pinyon-shift`.
  Replace `/path/to/source` with the absolute source folder. Debug symbols are
  omitted and source paths normalized so private build locations are not shipped.
  This does not build or embed the game. Preserve `launcher-notices/` when
  redistributing the resulting launcher.

These modified files retain Pinyon Shift's BSD-2-Clause license. All other embedded
source files come from the pinned upstream Git revision. No game data,
generated guest C++, compiled guest binaries, local state or captures are
included. The original dump compatibility checks are unchanged.
