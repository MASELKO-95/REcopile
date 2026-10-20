# Project sources and catalog metadata

The public player application reads catalog metadata and installs reviewed
project releases. It has no owner publishing interface or publication service.
The separate private Publisher, its code and its state are not distributed.

Players can add a GitHub source or connect an existing local executable. Read
each project's actual README and license and supply your own supported game
data. Source URLs, package patterns, platform mappings and release tags are
documented in [catalog format](catalog-format.md).

Public metadata is stored in `data/registry.json`. Catalog updates do not replace
the player application. README, license, source attribution and funding links
remain attached to the actual upstream project, including when RE:COPILE hosts
a source-tools integration package. The Pinyon package records its pinned
upstream revision and every modified helper in `package.json`.

Compatibility reports remain local until a player explicitly exports or submits
them. Published compatibility data is reviewed. A working installer, title screen
or timed process does not establish gameplay.
