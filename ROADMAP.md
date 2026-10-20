# RE:COPILE roadmap

Current preview: Linux / Windows desktop architecture, Steam-style libraries,
Xbox 360 / Xbox One / PS2 / PS3 metadata, on-demand artwork, independent game descriptions,
host-specific package filtering, editable sources, installed Steam discovery and
client launch handoffs, local programs with Proton / Wine,
profiles, issue drafts, compatibility data, collections and local mod templates.

The current interface has **English, Polish and Hungarian**.
**Japanese, Chinese and French are planned**, not available yet.

Before an official release: validate installers on Linux and Windows, exercise
launcher updates with an actual release, qualify each supported port with its
author's instructions and user-owned data, publish approved compatibility reports,
and verify release packaging includes the required GPLv3 source and notices.

Xbox One is currently a metadata catalog, with no shipped launch integration.

Later: **Android**, **PlayStation 4**, **PSP**, **PS Vita**, more game collections and
port-specific workshop adapters. Desktop ports do not automatically run on Android.
Optional Android ads need explicit choice and the applicable consent flow.

Ratchet & Clank 3 is an experimental local project; full gameplay is unverified.
Minecraft PS3 from a user's own disc image is a planned integration, not a released
playable ISO port. No release dates are promised for planned features.

Measurements now supports local hardware detection, timed direct game launches
using an installed MangoHud (Linux) or console PresentMon (Windows), and local
CSV import. Summaries include actual FPS, frame times, duration, the game/port
version and manually entered graphics settings. Windows capture still needs
qualification on a real Windows system. Steam / Flatpak handoffs use log import.
Players choose whether to export results or include selected results in a
a catalog update. No measurements are uploaded in the background.


Per-game hours and launch counts are available for directly tracked programs
launched from RE:COPILE. Optional Steam collection matching is off by default.
After a player enables it, local manifest checks run only for PC editions declared
in RE:COPILE collections; unrelated Steam games are not imported. The choice is
remembered, with startup checks only while enabled, rescanning and extra library
folders. Disabling disconnects automatic links while retaining manual paths and
profile history. It does not import the full owned-games account inventory.
Launch in Steam delegates to the client without timing its forwarding process.
Steam session tracking, hour imports and achievements require a separate
integration and validation on both desktop platforms.
Later: connect supported game / store achievement sources to each
game's player card. Unknown achievement counts remain unavailable; launcher
activity badges are separate. Other store-client adapters and achievement
synchronization need their own integration and validation.
