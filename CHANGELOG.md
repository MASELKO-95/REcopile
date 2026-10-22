# Historia zmian

## 0.2.2-beta.4 — 2026-10-22

- Add a separate FH2 Xbox One entry with the official Azimuth download page.
  Download and extract the wrapper at the author's site, then connect its EXE.
  Windows and Linux through Proton retain unverified local gameplay status.
- External downloads preserve the author's distribution and terms and remain
  outside automatic GitHub installation and update jobs. No game data is included.
- Update FH2 Xbox 360 research status: manual driving and festival arrival
  observed on Linux; graphics artifacts, low FPS and stutters remain open.

## 0.2.2-beta.3 — 2026-10-21

- On Linux, Play for prepared Pinyon Shift 0.6 installations offers direct play
  or the original upstream desktop launcher, with an optional remembered choice.
  Launch options can change or forget the preference later.
- Game settings for this integration opens the original Avalonia launcher with
  the same prepared build, game files and state. Opening the launcher does not
  count as game time; sessions started inside it are not separately timed.
- The Pinyon tools component `pinyon-v0.6.0-recopile.2` includes that launcher,
  its sources, a source-location adapter and dependency notices. It contains
  no game data or compiled guest game. Other integrations keep their settings.
- Keep the original launcher's own update check disabled during managed handoff
  so reviewed tools updates remain under RE:COPILE's installation workflow.

## 0.2.2-beta.2 — 2026-10-20

- Opcjonalne Ustawienia gry: wspólny panel dla integracji, argumenty uruchamiania i wybór zgodności Windows na Linuxie. Graj nadal uruchamia grę bez dodatkowego ekranu.
- Pełne opcje konfiguracji udostępniane przez CLI Pinyon Shift 0.6, w tym FSR 2/3, DLSS, presety, limity FPS, efekty, zalecenia sprzętowe oraz kopie ustawień. Starsze instalacje mogą korzystać z istniejącej łatki Linux 0.4.
- Osobny zestaw dostępnych opcji lokalnego FH2, bez deklarowania FSR lub potwierdzonej rozgrywki.
- Aktualizator wybiera wydania aplikacji ze wspólnego repozytorium i pomija paczki portów.
- Poprawne porównywanie wersji beta i stabilnych, osobne metadane kanału beta.

## 0.2.2-beta.1 — 2026-10-20

- Pierwsza publiczna beta Linux: AppImage, DEB, pacman oraz zgodne źródła GPLv3.
- Pobieralny pakiet źródeł i narzędzi Pinyon Shift 0.6.0 w Releases RE:COPILE, z oryginalną licencją BSD i bez plików gry.
- Osobne tagi wydań komponentów zapobiegają pomyleniu portu z aktualizacją huba.
- Bez prywatnego Publishera, danych kont, bibliotek gier i zapisów.
- FH2 pozostaje eksperymentalny; jazda niepotwierdzona.

## 0.2.1 — 2026-10-19

- Usunięto funkcje publikacji katalogu z aplikacji i paczek dla graczy.
- Czytnik katalogu obsługuje własne nazwy tagów i technologii oraz uwagi z testów.

## 0.2.0 — 2026-10-19

- Licencja launchera automatycznie przy pierwszym starcie i aktualizacji wersji;
  zapamiętana zgoda przy zwykłych restartach. Licencje projektów pozostają osobne.
- Powiadomienia o aktualizacjach gier; przy niezmienionej licencji i wcześniejszej
  zgodzie instalacja po następnym starcie bez ponownego okna akceptacji.
- Technologie zadeklarowane w katalogu widoczne przy wynikach i szczegółach.
- Lokalne pomiary: sprzęt CPU/GPU/RAM, MangoHud / konsolowy PresentMon, czas
  testu i rozgrzewka, import CSV, prawdziwe FPS / frametime, opis ustawień,
  eksport i wybór wyników do publikacji. Windows wymaga testu na tym systemie.
- Pakowanie Linux DEB / AppImage; zachowany NSIS dla buildu na Windowsie.

## Zmiany lokalne — 2026-10-15

- GNU GPLv3 zastępuje wcześniejszy projekt licencji własnego kodu. Zachowane
  autorstwo i informacje o zmianach; użycie komercyjne jest dozwolone.
- Forza Horizon 2 (Xbox 360): oryginalne źródło, fork społeczności i fork
  MASELKO-95; brak gotowej paczki i brak potwierdzonej rozgrywki.
- RE:COPILE Edition: wspólny panel importu / weryfikacji / kompilacji Pinyon
  Shift oraz lokalne uruchamianie eksperymentu Ratchet 3.
- Szczegółowy poradnik tekstowy How to play dla portów Xbox 360.
- Katalog Xbox One: 3033 wpisy z przypisanym pochodzeniem; osobny filtr i stan
  „Brak integracji”, bez sugerowania nieprzypisanego emulatora lub portu.
- Okładki pobierane wyłącznie dla widocznych wyników wyszukiwania lub na żądanie
  (bieżąca strona / wybrana gra). Lokalny cache i osobne pobieranie opisów.
- Widok „Na tym PC”: paczki i programy właściwego systemu; na Linuxie także
  wyraźnie oznaczone opcje Windows przez Proton / Wine, wymagające ręcznej instalacji.
- Nowe elementy dostępne po polsku, angielsku i węgiersku.

## 0.1.0 — wersja developerska, 2026-10-13

Autor: MASELKO-95. Oryginalne repozytorium zostanie wskazane w
data/distribution.json przed publikacją. Kontakt: https://github.com/MASELKO-95.

- Biblioteka konsol, wyszukiwanie i własne źródła GitHub.
- Oryginalny launcher Pinyon Shift jako domyślny kanał Final; fork Linux
  jako niewspierany, archiwalny Pre-release.
- Biblioteki podobne do Steama, osobne wersje i powrót do poprzedniego programu.
- README, licencja i finansowanie autorów przed pobraniem; zgody na aktualizacje.
- Profile lokalne, statystyki uruchomień, odznaki launchera i eksport PNG.
- Oznaczenia urządzenia i szkice raportów zgodności do GitHub Issues.
- Interfejs oraz natywne okno Electron dla desktopu.
- Projekt licencji zmieniony z MIT na Recopile Community License 1.0.
- Android, PS4 i Xbox One odłożone do kolejnych etapów.
