# Komponenty i prawa autorów

GNU GPLv3 obejmuje własny kod i materiały RE:COPILE. Nie zmienia licencji ani praw poniższych
projektów, gier, znaków towarowych i danych.

- React: MIT, https://github.com/facebook/react/blob/main/LICENSE
- Phosphor Icons: MIT, https://github.com/phosphor-icons/react/blob/master/LICENSE
- Electron: MIT oraz licencje Chromium; pakiet Electron zawiera LICENSE,
  LICENSES.chromium.html i dokumenty swoich zależności.
- electron-builder / electron-updater: MIT,
  https://github.com/electron-userland/electron-builder/blob/master/LICENSE
- Python: PSF, https://docs.python.org/3/license.html
- Chaquopy: MIT, https://github.com/chaquo/chaquopy/blob/master/LICENSE
- Pillow: HPND, https://github.com/python-pillow/Pillow/blob/main/LICENSE
- py7zr: LGPL-2.1, https://github.com/miurahr/py7zr/blob/master/LICENSE
- Inter i Barlow Condensed: SIL Open Font License. Pełne teksty dołączone w
  `frontend/public/assets/fonts/*-LICENSE.txt` i w zbudowanym interfejsie.
- Google Mobile Ads / UMP: warunki Google, tylko wariant Android skonfigurowany
  do reklam; https://developers.google.com/admob/android/privacy.

Porty i emulatory są pobierane bezpośrednio z GitHub Releases ich autorów.
Launcher pobiera ich rzeczywiste README i LICENSE dla wybranego wydania,
pokazuje je przed pobraniem programu, zachowuje w `Recopile-project-info` i
przedstawia finansowanie zadeklarowane w FUNDING.yml. Nie przepakowujemy ISO,
BIOS-u ani oryginalnych zasobów gry.

Katalog metadanych powstał z publicznych baz Libretro/libretro-database:
https://github.com/libretro/libretro-database. Pochodzenie, wersje plików,
daty i sumy źródeł są zapisane w migawce `data/catalog.json.gz`, a w aplikacji
w informacji o katalogu. Metadane są oddzielone od praw do samych gier.

Wpisy Xbox One pochodzą z list „List of Xbox One games (A–L)” i „(M–Z)”
angielskiej Wikipedii. Autorzy: Wikipedia contributors, CC BY-SA 4.0.
Adresy stron i sumy pobranych źródeł zapisano w `data/catalog.json.gz`.
Opisy pobierane na żądanie z Wikipedii pozostają w oryginalnym języku angielskim;
aplikacja pokazuje link do artykułu, atrybucję autorów i oznaczenie CC BY-SA 4.0.
https://en.wikipedia.org/wiki/List_of_Xbox_One_games_(A%E2%80%93L)
https://en.wikipedia.org/wiki/List_of_Xbox_One_games_(M%E2%80%93Z)
https://creativecommons.org/licenses/by-sa/4.0/

Okładki w lokalnym podglądzie pochodzą z Wikipedii, Libretro thumbnails i
xlenore/ps2-covers. Własność ilustracji pozostaje u ich autorów/wydawców.
Domyślne narzędzia pakowania pomijają ten lokalny zbiór grafik, ponieważ samo
pobranie okładki nie daje zgody na jej dalszą dystrybucję. W wydaniu publicznym
użyj własnych okładek lub materiałów z odpowiednimi prawami. Interfejs ma
działający widok zastępczy, gdy okładka nie została dołączona.

Nowe grafiki z Wikipedia/Wikimedia są pobierane tylko dla widocznych wyników
wyszukiwania lub po jawnym żądaniu użytkownika. Pamięć `covers/` w lokalnych
danych aplikacji nie jest częścią wydania. Link do artykułu przy grafice pozwala
sprawdzić jej pochodzenie; licencja tekstu Wikipedii nie udziela automatycznie
praw do ilustracji należącej do wydawcy gry.

Budowanie samodzielnej aplikacji dołącza binarne zależności z ich oryginalnymi
licencjami. Dystrybutor powinien zachować te dokumenty oraz udostępnić źródła
komponentów, dla których wymaga tego ich licencja. Użycie nazwy Xbox,
PlayStation czy tytułu gry nie oznacza powiązania ani poparcia przez jej wydawcę.
