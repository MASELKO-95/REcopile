# How to play Xbox 360 ports in RE:COPILE

**Download the port → choose your own ISO → prepare the game → play.**

These steps describe **Forza Horizon / Pinyon Shift** on
Linux and Windows. Each other port has its own supported game versions,
requirements and preparation procedure. The in-app **How to play** page is
available in English, Polish and Hungarian.

1. **Find the right game.** Choose Xbox 360 in the library, find Forza Horizon
   and open its details. Check the package for your operating system and the
   compatibility information. A metadata entry or source repository alone
   does not provide a playable port.
2. **Download the port tools.** Select **Pinyon Shift**,
   the default **Final** channel, then **Download port tools**. Review that
   release's actual README, license, authors and requirements before approving
   the download. Automatic updates have a separate optional consent. The
   download supplies software; you supply the game data.
3. **Have your own supported copy ready.** Pinyon Shift identifies the Xbox 360
   USA retail disc, **MS-2505**. Its file verification confirms the exact
   supported dump. Choose a readable ISO, or an extracted game folder accepted
   by the port. An Xbox One image, another region or an incomplete dump does
   not substitute for the supported copy. This guide starts with an existing
   image; the PS2 DVD reader in RE:COPILE does not create Xbox disc images.
4. **Choose your files.** After downloading, click **Prepare in RE:COPILE**,
   then **Choose ISO** or **Choose folder**, and confirm your right to use the
   copy. The ISO may stay in its existing location. Setup uses Pinyon Shift's
   tools inside RE:COPILE, without its separate graphical launcher.
5. **Verify and build.** **Check files** performs verification only.
   **Check and build** also prepares the local executable. The initial setup
   can download a compiler and dependencies and take considerable time.
   Pinyon Shift's Linux documentation requests about **45 GB** free. Check
   current CPU, Vulkan, Python/Git and Windows tool requirements in the
   installed release's README. Internet access is needed for missing tools.
6. **Wait for preparation to finish.** Follow progress in the game panel or
   Downloads. If it stops, expand **Preparation log** and check the last stage.
   Downloaded tools and a verified ISO do not enable Play: a complete build
   must be confirmed. Cancelling leaves local files and saves in place.
7. **Play.** Once the build is confirmed, click **Play** in the game details.
   RE:COPILE launches the port directly. Later launches reuse the prepared
   files; an update may require preparation again. Existing saves stay local.
   A successful build is separate from a gameplay compatibility report.

## If preparation fails

For verification errors, check the supported edition and the completeness of
your copy. For a build error, check free space, connectivity, system requirements
and the preparation log. Do not mark downloaded tools as a finished game.
Include the port version, operating system and relevant error text in a bug
report; do not attach ISO images or game data.

## Forza Horizon 2

The catalog links the [original FH2 project](https://github.com/fabioap-cpu/Forza-Horizon-2-Recomp),
the [community fork](https://github.com/ShreyashDesai/Forza-Horizon-2-Recomp) and
[MASELKO-95's development fork](https://github.com/MASELKO-95/Forza-Horizon-2-Recomp).
They target **Xbox 360**, not the Xbox One edition. The upstream status reports
Windows startup to a loading screen followed by a semaphore stall; full gameplay
is unverified. There is no downloadable game package configured in RE:COPILE.
The Forza Horizon setup instructions above are not a claim that FH2 is playable.

Xbox One entries have their own metadata catalog. Choosing an Xbox One ISO
alone does not launch a game on PC; an actual port or appropriate prepared
local installation is required.

Upstream instructions: [Pinyon Shift: How to play](https://github.com/arcanite24/pinyon-shift#how-to-play)
and [Linux / Steam Deck requirements](https://github.com/arcanite24/pinyon-shift/blob/main/docs/LINUX.md).
The actual README and license for the selected release remain authoritative.
