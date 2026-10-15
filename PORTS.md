# RE:COPILE port and project list

Generated from `data/registry.json`. This list is updated with catalog changes.
Packages are declared by catalog entries; package availability is separate from tested gameplay.
Read each project's original README and license inside the launcher before downloading.

| Project | Author | Linux | Windows | Channel / status | Links |
| --- | --- | --- | --- | --- | --- |
| Pinyon Shift Linux alternative | MASELKO-95 | Declared package | No declared package | Pre-release; unsupported / archived | [Project](https://github.com/MASELKO-95/pinyon-shift-Native-Linux-unofficial) · [Releases](https://github.com/MASELKO-95/pinyon-shift-Native-Linux-unofficial/releases) · [Guide](https://github.com/MASELKO-95/pinyon-shift-Native-Linux-unofficial#readme) |
| Pinyon Shift · RE:COPILE Edition | arcanite24 | Declared package | Declared package | Final catalog channel; see upstream status | [Project](https://github.com/arcanite24/pinyon-shift) · [Releases](https://github.com/arcanite24/pinyon-shift/releases) · [Guide](https://github.com/arcanite24/pinyon-shift/blob/main/docs/LINUX.md) |
| Skate 3 Recompiled | mchughalex | Declared package | Declared package | Catalogued project; check author documentation | [Project](https://github.com/mchughalex/skate3recomp) · [Releases](https://github.com/mchughalex/skate3recomp/releases) · [Guide](https://github.com/mchughalex/skate3recomp#linux) |
| Unleashed Recompiled | hedge-dev | Declared package | Declared package | Catalogued project; check author documentation | [Project](https://github.com/hedge-dev/UnleashedRecomp) · [Releases](https://github.com/hedge-dev/UnleashedRecomp/releases) · [Guide](https://github.com/hedge-dev/UnleashedRecomp#how-to-install) |
| PCSX2 | PCSX2 | Declared package | Declared package | Emulator; per-game compatibility varies | [Project](https://github.com/PCSX2/pcsx2) · [Releases](https://github.com/PCSX2/pcsx2/releases) · [Guide](https://pcsx2.net/docs/category/setup/) |
| RPCS3 | RPCS3 | Declared package | Declared package | Emulator; per-game compatibility varies | [Project](https://github.com/RPCS3/rpcs3-binaries-linux) · [Releases](https://github.com/RPCS3/rpcs3-binaries-linux/releases) · [Guide](https://rpcs3.net/quickstart) |
| Wanderer | MASELKO-95 | Declared package | No declared package | Catalogued project; check author documentation | [Project](https://github.com/MASELKO-95/Wanderer-dice-farkle-game) · [Releases](https://github.com/MASELKO-95/Wanderer-dice-farkle-game/releases) · [Guide](https://github.com/MASELKO-95/Wanderer-dice-farkle-game) |
| SCP | MASELKO-95 | Declared package | No declared package | Catalogued project; check author documentation | [Project](https://github.com/MASELKO-95/SCP-Vulkan-edition) · [Releases](https://github.com/MASELKO-95/SCP-Vulkan-edition/releases) · [Guide](https://github.com/MASELKO-95/SCP-Vulkan-edition) |
| Ratchet & Clank: Up Your Arsenal (Ratchet & Clank 3) · RE:COPILE Edition | MASELKO-95 | Experiment only; no package | No declared package | In development; gameplay unverified | [Project](https://github.com/MASELKO-95/ratchet-3-recopile-edition) · [Releases](https://github.com/MASELKO-95/ratchet-3-recopile-edition/releases) · [Guide](https://github.com/MASELKO-95/ratchet-3-recopile-edition#requirements-and-build) |
| Minecraft PS3 own-disc / ISO integration | MASELKO-95 (planned integration) | No declared package | No declared package | Planned; no ready port | No public release · [Guide](https://www.minecraft.net/en-us/eula) |
| Forza Horizon 2 Recompiled (original) | fabioap-cpu | No declared package | Experiment only; no package | In development; gameplay unverified | [Project](https://github.com/fabioap-cpu/Forza-Horizon-2-Recomp) · [Releases](https://github.com/fabioap-cpu/Forza-Horizon-2-Recomp/releases) · [Guide](https://github.com/fabioap-cpu/Forza-Horizon-2-Recomp#readme) |
| Forza Horizon 2 Recompiled (fork) | ShreyashDesai | No declared package | Experiment only; no package | In development; gameplay unverified | [Project](https://github.com/ShreyashDesai/Forza-Horizon-2-Recomp) · [Releases](https://github.com/ShreyashDesai/Forza-Horizon-2-Recomp/releases) · [Guide](https://github.com/ShreyashDesai/Forza-Horizon-2-Recomp#readme) |
| Forza Horizon 2 Recompiled (research fork) | MASELKO-95 | No declared package | Experiment only; no package | In development; gameplay unverified | [Project](https://github.com/MASELKO-95/Forza-Horizon-2-Recomp) · [Releases](https://github.com/MASELKO-95/Forza-Horizon-2-Recomp/releases) · [Guide](https://github.com/MASELKO-95/Forza-Horizon-2-Recomp#readme) |

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

MASELKO-95 research fork: created from fabioap-cpu on 2026-10-15, with no
independent fixes or game tests yet. It retains the same limitations. No game
files are available for local gameplay validation. Creating a fork does not
establish working gameplay.

## Adding a project

Use the launcher's publisher form, export the entry, then run:

```sh
python3 tools/register_game.py recopile-game-entry.json
python3 tools/update_port_list.py --check
```

Publish the changed catalog and port list with a release or catalog update.
Updates to a listed game come from its original author's GitHub Releases; its
binaries do not need to be copied into the launcher repository.
