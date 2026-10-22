# RE:COPILE port and project list

Generated from `data/registry.json`. This list is updated with catalog changes.
Packages are declared by catalog entries; package availability is separate from tested gameplay.
Read each project's original README and license inside the launcher before downloading.

| Project | Author | Linux | Windows | Channel / status | Links |
| --- | --- | --- | --- | --- | --- |
| Pinyon Shift Linux alternative | MASELKO-95 | Declared package | No declared package | Pre-release; unsupported / archived | [Project](https://github.com/MASELKO-95/pinyon-shift-Native-Linux-unofficial) · [Releases](https://github.com/MASELKO-95/pinyon-shift-Native-Linux-unofficial/releases) · [Guide](https://github.com/MASELKO-95/pinyon-shift-Native-Linux-unofficial#readme) |
| Pinyon Shift | arcanite24 | Declared package | Declared package | Final catalog channel; see upstream status | [Project](https://github.com/arcanite24/pinyon-shift) · [Releases](https://github.com/arcanite24/pinyon-shift/releases) · [Guide](https://github.com/arcanite24/pinyon-shift/blob/main/docs/LINUX.md) |
| Skate 3 Recompiled | mchughalex | Declared package | Declared package | Catalogued project; check author documentation | [Project](https://github.com/mchughalex/skate3recomp) · [Releases](https://github.com/mchughalex/skate3recomp/releases) · [Guide](https://github.com/mchughalex/skate3recomp#linux) |
| Unleashed Recompiled | hedge-dev | Declared package | Declared package | Catalogued project; check author documentation | [Project](https://github.com/hedge-dev/UnleashedRecomp) · [Releases](https://github.com/hedge-dev/UnleashedRecomp/releases) · [Guide](https://github.com/hedge-dev/UnleashedRecomp#how-to-install) |
| PCSX2 | PCSX2 | Declared package | Declared package | Emulator; per-game compatibility varies | [Project](https://github.com/PCSX2/pcsx2) · [Releases](https://github.com/PCSX2/pcsx2/releases) · [Guide](https://pcsx2.net/docs/category/setup/) |
| RPCS3 | RPCS3 | Declared package | Declared package | Emulator; per-game compatibility varies | [Project](https://github.com/RPCS3/rpcs3-binaries-linux) · [Releases](https://github.com/RPCS3/rpcs3-binaries-linux/releases) · [Guide](https://rpcs3.net/quickstart) |
| Wanderer | MASELKO-95 | Declared package | No declared package | Catalogued project; check author documentation | [Project](https://github.com/MASELKO-95/Wanderer-dice-farkle-game) · [Releases](https://github.com/MASELKO-95/Wanderer-dice-farkle-game/releases) · [Guide](https://github.com/MASELKO-95/Wanderer-dice-farkle-game) |
| Ratchet & Clank: Up Your Arsenal (Ratchet & Clank 3) · RE:COPILE Edition | MASELKO-95 | Experiment only; no package | No declared package | In development; gameplay unverified | [Project](https://github.com/MASELKO-95/ratchet-3-recopile-edition) · [Releases](https://github.com/MASELKO-95/ratchet-3-recopile-edition/releases) · [Guide](https://github.com/MASELKO-95/ratchet-3-recopile-edition#requirements-and-build) |
| Minecraft PS3 own-disc / ISO integration | MASELKO-95 (planned integration) | No declared package | No declared package | Planned; no ready port | No public release |
| Forza Horizon 2 Recompiled (original) | fabioap-cpu | No declared package | Experiment only; no package | In development; gameplay unverified | [Project](https://github.com/fabioap-cpu/Forza-Horizon-2-Recomp) · [Releases](https://github.com/fabioap-cpu/Forza-Horizon-2-Recomp/releases) · [Guide](https://github.com/fabioap-cpu/Forza-Horizon-2-Recomp#readme) |
| Forza Horizon 2 Recompiled (fork) | ShreyashDesai | No declared package | Experiment only; no package | In development; gameplay unverified | [Project](https://github.com/ShreyashDesai/Forza-Horizon-2-Recomp) · [Releases](https://github.com/ShreyashDesai/Forza-Horizon-2-Recomp/releases) · [Guide](https://github.com/ShreyashDesai/Forza-Horizon-2-Recomp#readme) |
| Forza Horizon 2 Recompiled (research fork) | MASELKO-95 | Experiment only; no package | Experiment only; no package | In development; gameplay unverified | [Project](https://github.com/MASELKO-95/Forza-Horizon-2-Recomp) · [Releases](https://github.com/MASELKO-95/Forza-Horizon-2-Recomp/releases) · [Guide](https://github.com/MASELKO-95/Forza-Horizon-2-Recomp#readme) |
| Azimuth | Almost There Games | Windows via Proton; unverified locally | Manual download from author | External wrapper; local gameplay unverified | [Author download](https://almost-there-games.itch.io/azimuth) · [Guide](https://almost-there-games.itch.io/azimuth) |

## Porting tools and emulators

| Tool | Platform | Type | Links |
| --- | --- | --- | --- |
| ShiftGlue SDK | Xbox 360 | Porting SDK | [Project](https://github.com/arcanite24/shiftglue-sdk) · [Guide](https://github.com/arcanite24/shiftglue-sdk) |
| Xenia | Xbox 360 | Emulator | [Project](https://github.com/xenia-project/xenia) · [Guide](https://github.com/xenia-project/xenia/wiki/Quickstart) |
| PS2Recomp | PlayStation 2 | Porting SDK | [Project](https://github.com/ran-j/PS2Recomp) · [Guide](https://github.com/ran-j/PS2Recomp) |
| PCSX2 | PlayStation 2 | Emulator | [Project](https://github.com/PCSX2/pcsx2) · [Guide](https://pcsx2.net/docs/category/setup/) |
| RPCS3 | PlayStation 3 | Emulator | [Project](https://github.com/RPCS3/rpcs3) · [Guide](https://rpcs3.net/quickstart) |

“Final” identifies the original default channel in this catalog; it does not
override the upstream release status. Unsupported forks are not automatic update sources.

Ratchet 3: Linux PAL SCES-52456 intro and title screen only; full gameplay and
Windows are unverified. Minecraft PS3 ISO support is planned. Neither entry
provides commercial game source code, game assets, ISO or BIOS files.

Forza Horizon 2 Recompiled: the original fabioap-cpu project and the ShreyashDesai
fork target the **Xbox 360** edition. Their reviewed READMEs describe a Windows AMD64
experiment that stalls at the loading screen; gameplay is unverified. Neither repository
has published releases or ready Linux / Windows packages. Linux build presets and
a CI workflow do not establish working gameplay. These sources are not assigned
to the Xbox One edition. The README declares BSD-3-Clause for project source and SDK;
the reviewed license file is `rexglue-sdk/LICENSE`, with no separate root LICENSE.

MASELKO-95 research fork: Linux manual driving and festival arrival observed
on 2026-10-22. An isolated profile test reaches car selection and the first race
start. Graphics artifacts, soft output, low frame rates and stutters remain.
The renderer uses the Xenia-derived Xenos Vulkan backend; FSR is disabled in
the tested build. Race completion, career progression and a complete save/reload
cycle remain unverified. No ready public game package is available.

Azimuth is a separate wrapper for the **Xbox One** edition, by Almost There Games.
RE:COPILE opens the official itch.io download page. Download and extract the
wrapper there, then connect `azimuth.exe` as a local program. Follow the author’s
instructions and terms; the wrapper and game files are not redistributed here.
The author lists Windows 10/11 and Linux through Proton; local gameplay is
unverified. FH2 1.0.0.64 requires the player’s game folder containing `era.vbi`,
`Mount/` and `EmbeddedXvd/`. Updates are obtained from the author.

## Catalog updates

Game metadata is maintained in `data/registry.json`. Players receive catalog updates
without replacing launcher code or reinstalling the application.
This project list and the author profile list are generated from that catalog.
Updates to game programs come from their authors' GitHub Releases or official
manual download pages. New launcher features require an application update.
