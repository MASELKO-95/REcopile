# Optional game settings

Open an installed game's details and choose **Game settings**. **Play** starts
the connected game directly; using this panel is optional.

Each integration supplies its supported controls. All directly managed games
can store additional launch arguments, one argument per line. A Windows program
connected on Linux can also choose its Proton version or Wine. These choices
apply only to that game and never change the original installation metadata.
Steam shortcuts keep their settings in Steam.

Pinyon Shift 0.6 uses the original `pinyon.py config` and `hardware` commands:
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
