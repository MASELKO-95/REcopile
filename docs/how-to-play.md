# How to play in RE:COPILE

**Choose a game → prepare your own copy → configure → play.**

This is a guide to the program for Xbox 360 and PlayStation 2, available in
English, Polish and Hungarian in the app. The selected project's documentation
in each game's details specifies supported editions, requirements and commands.

1. **Find a game and choose how to run it.** Open Library, select the console
   and search for the title. Check port sources, Linux / Windows packages and
   compatibility. Turn off **Recompilations only** to include emulator entries.
2. **Review and install the project.** In the game details, choose a source,
   read its actual README and separately accept its license before downloading.
   Automatic updates are an optional separate choice. A catalog entry or source
   repository alone does not supply a playable game.
3. **Prepare your own game data.** Follow the PS2 DVD or Xbox 360 USB instructions
   below. Keep a complete image or extracted folder in the format and edition
   accepted by your selected project.
4. **Select your files.** For an integrated port, use **Prepare in RE:COPILE**,
   then **Choose ISO** or **Choose folder**. For emulation, use **Add your own
   copy**. Other ports use their own documented setup or manual installation.
   Confirm your right to use the files; they may stay in their existing folder.
5. **Prepare the project.** When available, **Check files** verifies input and
   **Check and build** prepares the executable. These controls are specific to
   supported integrations. Other projects have their own procedures. Porting
   SDKs need configuration and development for each game.
6. **Check the result.** Follow Downloads and the preparation log. Check free
   space and project requirements if a stage fails. Downloading tools or passing
   an input checksum check does not confirm a complete build or working gameplay.
7. **Play.** Once ready, click **Play** in the game details. You can also use
   **Connect a finished game** or **Add a game or source** for an existing PC
   installation. Later launches reuse saved configuration; port updates may
   require preparation again. Saves and play history remain local.

## Xbox 360: your own disc and USB

On an Xbox 360, open the disc's game details, choose Install and select USB
storage. Existing HDD installations can be transferred through the console's
storage settings. Some games do not support installation. Preserve the USB's
files before any formatting. Copy the complete game package from Content to
your PC, retaining the main file and accompanying .data folder. Follow the
[Xenia project instructions](https://github.com/xenia-project/xenia/wiki/Quickstart#how-to-rip-games).

For suitable GOD packages, the external [GOD2ISO tool](https://github.com/raburton/god2iso)
can prepare an ISO. A project may instead accept an extracted folder. Choose
the result in RE:COPILE; the hub currently has no USB-to-ISO converter. A
converted image must still pass the port's own supported-input verification.
Use your own copy; downloading other people's game images is not recommended.

## PlayStation 2: your own DVD

Insert your own readable PS2 DVD into the PC's optical drive. In **How to play**,
enter the drive and output filename in the PS2 reader, confirm ownership and
start reading. The image and SHA-256 checksum are saved under
`recopileapps/discimages` in the current library. Follow progress in Downloads,
then select the ISO in the game's supported setup or emulator workflow.

This reader supports readable PS2 DVDs. Xbox 360 / PS3 discs and raw multitrack
CD images require their own procedures and hardware.

## Emulators and porting tools

For PS2 emulation, install and configure PCSX2 in **Emulators**, using your own
BIOS and the project's instructions. For Xbox 360, configure **Xenia program or
wrapper** in Settings. Linux requires a suitably configured wrapper. Add your
own game copy and disable **Recompilations only**. Compatibility varies by game.

**From disc to game** links to [ShiftGlue SDK](https://github.com/arcanite24/shiftglue-sdk),
[Xenia](https://github.com/xenia-project/xenia/wiki/Quickstart),
[PS2Recomp](https://github.com/ran-j/PS2Recomp),
[PCSX2](https://pcsx2.net/docs/category/setup/) and
[RPCS3](https://rpcs3.net/quickstart). SDKs are tools for developing ports;
selecting an arbitrary ISO does not produce a finished native game.

Xbox One catalog entries need an actual port or existing PC installation.
PSP and PS Vita support is deferred.

Collections list each series in release order, combining available port
projects with official PC editions. Use **Prepare game** to open a port's setup
and documentation, or **Connect a PC installation** for an existing local
executable or suitable startup script. Ready installations have **Play** in
the collection. Buying through a store link and connecting an installation
are separate steps.

The player card records hours and launch counts separately for each game and
profile after the launched program exits. The profile selected at launch owns
that session, even if you switch profiles while playing. Choose the game
program or a startup script that stays active for the session. In-game
achievement counts require a future adapter; launcher activity badges are
shown separately.

## Troubleshooting

Check your copy's edition and completeness, the project requirements and the
last failing stage's log. Include the port version, operating system and error
text in a report. Do not attach game images, BIOS files or game data.
