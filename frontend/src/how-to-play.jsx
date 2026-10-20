import React from 'react';
import {Books, Disc} from '@phosphor-icons/react';
import {External} from './ui.jsx';

export function HowToPlay({go, onAdd}) {
  return <section className="panel how-to-play" aria-labelledby="play-guide-title">
    <div className="panel-title"><Books size={25}/><div><h2 id="play-guide-title">Jak grać w RE:COPILE</h2><p>Wybierz grę → przygotuj własną kopię → skonfiguruj → graj.</p></div></div>
    <p className="guide-intro">Wspólna instrukcja obsługi programu dla Xbox 360 i PlayStation 2. Obsługiwane wydanie gry, wymagania i szczegóły przygotowania znajdziesz zawsze w dokumentacji wybranego projektu przy grze.</p>
    <ol className="play-steps">
      <li><strong>Znajdź grę i wybierz sposób uruchamiania</strong><p>Otwórz Bibliotekę, wybierz konsolę i wyszukaj tytuł. Sprawdź źródła portu, paczki Linux / Windows i status zgodności. Aby zobaczyć gry uruchamiane przez emulator, wyłącz filtr „Tylko rekompilacje”.</p></li>
      <li><strong>Przejrzyj dokumentację i pobierz port</strong><p>W szczegółach wybierz źródło i otwórz „README, licencja i wsparcie autorów”. Sprawdź wymagania, region i wersję gry, a następnie użyj dostępnej opcji instalacji. Zgodę na automatyczne aktualizacje wybierasz osobno. Wpis katalogowy i sam kod źródłowy nie są gotową grą.</p></li>
      <li><strong>Przygotuj własne pliki gry</strong><p>Dla PS2 możesz odczytać własne DVD poniżej. Dla Xbox 360 przygotuj kopię przez konsolę i USB według osobnej instrukcji. Zachowaj kompletny obraz lub folder w formacie wymaganym przez port albo emulator.</p></li>
      <li><strong>Wskaż kopię w panelu gry</strong><p>Jeśli port oferuje „Przygotuj w RE:COPILE”, wybierz własne ISO lub folder i potwierdź prawo do korzystania z plików. Przy emulacji użyj „Dodaj własną kopię”. Inne porty przygotuj według ich README, używając dostępnej konfiguracji lub instalacji ręcznej. Pliki mogą pozostać w swoim folderze.</p></li>
      <li><strong>Wykonaj przygotowanie wybranego projektu</strong><p>W zintegrowanym panelu „Sprawdź pliki” tylko weryfikuje dane, a „Sprawdź i zbuduj” przygotowuje program. Te przyciski są dostępne dla obsługiwanych integracji. Pozostałe projekty mają własną procedurę. ShiftGlue SDK i PS2Recomp służą do tworzenia portów; potrzebują konfiguracji i pracy nad konkretną grą.</p></li>
      <li><strong>Sprawdź wynik w Pobranych i w logu</strong><p>Poczekaj na zakończenie instalacji lub budowania. Jeśli etap się zatrzyma, sprawdź log, wolne miejsce i wymagania projektu. Pobranie narzędzi i poprawna suma obrazu nie potwierdzają gotowej kompilacji ani działającej rozgrywki.</p></li>
      <li><strong>Uruchom przygotowaną grę</strong><p>Gdy instalacja jest gotowa, otwórz szczegóły i kliknij „Graj”. Gotowy program PC możesz dodać przez „Podłącz gotową grę” albo „Dodaj grę lub źródło”. Kolejne uruchomienia korzystają z zapisanej konfiguracji; aktualizacja portu może wymagać ponownego przygotowania. Zapisy pozostają lokalne.</p></li>
    </ol>
    <div className="engine-actions"><button type="button" className="primary" onClick={()=>go('catalog')}>Otwórz bibliotekę</button><button type="button" className="outline" onClick={onAdd}>Dodaj gotową grę PC</button></div>
    <details className="play-troubleshooting"><summary>Uruchamianie przez emulator</summary><p>PS2: w zakładce Emulatory zainstaluj i skonfiguruj PCSX2 według jego instrukcji, z własnym BIOS-em. Xbox 360: w Ustawieniach wskaż „Program lub wrapper Xenia”; na Linuxie potrzebny jest odpowiednio skonfigurowany wrapper. Dodaj własną kopię przy grze i wyłącz „Tylko rekompilacje”. Zgodność zależy od tytułu i systemu.</p><div className="engine-actions"><button type="button" className="outline" onClick={()=>go('engines')}>Otwórz emulatory</button><button type="button" className="outline" onClick={()=>go('settings')}>Ustawienia Xenia</button></div></details>
    <details className="play-troubleshooting"><summary>Co zrobić, gdy przygotowanie nie działa?</summary><p>Sprawdź wydanie własnej kopii, kompletność plików, wymagania projektu i log ostatniego etapu. Przy zgłoszeniu błędu podaj wersję portu, system i treść błędu. Nie dołączaj ISO, BIOS-u ani danych gry.</p></details>
    <p className="form-help">Xbox One ma osobny katalog i wymaga przypisanego portu lub własnej instalacji PC. PSP i PS Vita są planowane na później.</p>
  </section>;
}

export function XboxCopyGuide() {
  return <section className="panel xbox-copy-guide" aria-labelledby="xbox-copy-title">
    <div className="panel-title"><Disc size={25}/><div><h2 id="xbox-copy-title">Xbox 360 · własna płyta i USB</h2><p>Przygotuj kopię na konsoli, a następnie przenieś ją na PC.</p></div></div>
    <ol className="play-steps">
      <li><strong>Zainstaluj z własnej płyty</strong><p>Na Xbox 360 wybierz szczegóły gry → Zainstaluj i jako miejsce docelowe wybierz USB. Jeśli gra jest już na dysku konsoli, przenieś ją przez Ustawienia → System → Pamięć. Nie każdy tytuł obsługuje instalację.</p></li>
      <li><strong>Podłącz USB do komputera</strong><p>Skopiuj cały pakiet gry z folderu Content, zachowując plik główny i towarzyszący folder .data. To pakiet konsoli, który trzeba przygotować w formacie akceptowanym przez wybrany projekt.</p></li>
      <li><strong>Przygotuj obsługiwany format</strong><p>Odpowiedni pakiet GOD można przekonwertować zewnętrznym narzędziem GOD2ISO. Jeśli projekt przyjmuje wypakowane pliki, przygotuj folder według jego dokumentacji. Gotowe ISO lub folder wskaż w RE:COPILE. Hub nie ma obecnie konwertera USB → ISO; utworzony obraz musi przejść weryfikację portu.</p></li>
    </ol>
    <p className="form-help">Korzystaj z własnej kopii. Pobierania cudzych obrazów z internetu nie zalecamy. Przed formatowaniem USB zachowaj jego pliki. Zwykły czytnik DVD PS2 poniżej nie odczytuje płyt Xbox 360.</p>
    <div className="engine-actions"><External className="outline" href="https://github.com/xenia-project/xenia/wiki/Quickstart#how-to-rip-games">Instrukcja kopiowania Xbox 360</External><External className="outline" href="https://github.com/raburton/god2iso">GOD2ISO · instrukcja i źródła</External></div>
  </section>;
}
