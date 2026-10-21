# Optional game settings

Open an installed game's details and choose **Game settings**. Using settings
is optional.

On Linux, prepared Pinyon Shift 0.6 installations offer **Play now** and
**Original Pinyon Shift launcher** when pressing **Play**. The optional
**Remember my choice** checkbox skips the question next time. **Launch options**
in the game's details always reopens the question, so a remembered choice can
be changed or forgotten. Closing the question launches nothing. If the original
launcher is missing, direct play remains available and the tools can be updated.

For this integration, **Game settings** opens the original Avalonia launcher
from the pinned upstream project, with a source-location adapter. It uses the
same build, game files, saves and configuration directory as direct play.
The original launcher includes its graphics, DLC, saves and other panels;
additional graphics/input options remain in-game with F6. Opening its window is
not recorded as game time. Games started within that window are not separately
timed by RE:COPILE. The original launcher's update check is disabled during this
managed handoff; the hub updates the reviewed tools package.

Other integrations keep direct **Play** and their optional settings panel.
The new original-launcher handoff is validated on Linux; it does not add an
untested Windows launcher adapter.

Each integration supplies its supported controls. All directly managed games
can store additional launch arguments, one argument per line. A Windows program
connected on Linux can also choose its Proton version or Wine. These choices
apply only to that game and never change the original installation metadata.
Steam shortcuts keep their settings in Steam.

The Pinyon settings backend retains the original `pinyon.py config` and `hardware` commands:
internal resolution, bilinear/CAS/FSR 1/FSR 2/FSR 3/DLSS output, Treasure Map,
game and resolution presets, anisotropic filtering, FXAA, presentation/render
FPS limits, bloom, motion blur, depth of field, and hardware recommendations.
Save, defaults and restore use upstream's configuration backups and schema
checks. More display and input controls remain available in-game with F6, as in
the original desktop launcher. The adapter writes the same state directory
used for launching and preserves existing saves.

FSR 2/3 and DLSS require the corresponding runtime libraries and supported
hardware. The menu exposes upstream choices; it does not certify that those
features are available on a particular machine. There is no separate frame
generation switch in this upstream launcher CLI.

For the owner's archived 0.4 Linux installation, the adapter can use its
existing `linux_support.py graphics` patch. Its controls remain limited to that
version, including FSR 1, controller/keyboard-and-mouse modes and the trainer.
It does not add FSR 2/3 to the old renderer or overwrite the archive.

The connected local FH2 experiment has resolution scale, anisotropic filtering,
vertical sync and FXAA controls supported by its current runtime. Gameplay and
FSR support are not asserted. Other ports retain their own available controls;
undocumented graphics settings are never invented or written into their files.

Settings writes are blocked during a running game or an active installation or
build. Reading settings never launches a game. Test the real port commands in
disposable profiles with:

```sh
python3 tools/check_game_settings.py --pinyon-source /path/to/pinyon-shift
```

The optional `--legacy-source` argument also checks the archived Linux patch.
