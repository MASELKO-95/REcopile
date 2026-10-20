# Changes to the pinned Pinyon Shift source payload

2026-10-20, MASELKO-95:

- Add `tools/create-render-seed.py` with an explicit `--allow-cold-cache`
  option for older Linux states. The default still requires shader catalogs.
  Copy and hash all independent `user-*` profiles alongside the base user.
  Refuse to replace an existing seed. This helper is for private test snapshots;
  the setup process does not import saves automatically.
- Add `tests/test_cold_render_seed.py` covering the strict default, explicit
  cold cache, both profiles, unchanged originals and overwrite refusal.

These files retain Pinyon Shift's BSD-2-Clause license. All other embedded
source files come from the pinned upstream Git revision. No game data,
generated guest C++, compiled guest binaries, local state or captures are
included. The original dump compatibility checks are unchanged.
