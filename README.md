# GerbertoHTML — generator raportów Assembly / Traceability dla PCB

Narzędzie CLI w Pythonie: wskazujesz pliki **Gerber**, **BOM** (CSV/XML) i opcjonalnie **pick-and-place**
(CSV), a na wyjściu dostajesz **jeden samodzielny plik HTML** z dwiema zakładkami:

- **Assembly** — lista komponentów z BOM sprzężona dwustronnie z wizualizacją płytki (zoom/pan),
  checkboxy Dostarczono/Zamontowano, ręczne pozycjonowanie komponentów bez danych z pick-and-place.
- **Traceability** — numery sampli, wspólny stos przeróbek (rework), notatki per sampel.

Wygenerowany plik `report.html` można otworzyć bezpośrednio w przeglądarce (dwuklik, bez serwera),
wysłać mailem, dołączyć do dokumentacji partii produkcyjnej albo zarchiwizować. Jest w pełni
interaktywny — zmiany (checkboxy, sample, przeróbki, ręczne pozycje) zapisują się lokalnie w
przeglądarce (`localStorage`), więc kolejne otwarcie tego samego pliku pamięta poprzedni stan.

## Szybki start

> **Ważne:** polecenie `python -m pcb_report ...` trzeba uruchamiać **z głównego katalogu tego
> repozytorium** (tego, w którym leży folder `pcb_report/`) — Python szuka modułu w bieżącym
> katalogu roboczym. Jeśli chcesz wołać narzędzie z dowolnego miejsca (np. z katalogu z plikami
> projektu PCB), zainstaluj je raz jako pakiet:
>
> ```bash
> cd /ścieżka/do/repo   # katalog z pyproject.toml
> pip install -e .
> ```
>
> Od tego momentu w dowolnym katalogu działa krótsza komenda `pcb-report` (bez `python -m`,
> bez konieczności bycia w katalogu repo) — użyta w przykładach niżej zamiennie z `python -m pcb_report`.

**macOS / Linux (bash/zsh):**

```bash
python3 -m pcb_report \
  --gerber board-top-copper.gbr board-bottom-copper.gbr board-outline.gbr board-silkscreen.gbr \
  --bom bom.csv \
  --pnp placement.csv \
  -o report.html
```

**Windows (PowerShell)** — `\` na końcu linii to składnia bash i **nie zadziała** w PowerShellu
(zostanie każdorazowo zinterpretowany jako osobna, błędna komenda); użyj jednej linii albo
backticka `` ` ``:

```powershell
python -m pcb_report --gerber board-top-copper.gbr board-bottom-copper.gbr board-outline.gbr board-silkscreen.gbr --bom bom.csv --pnp placement.csv -o report.html
```

albo:

```powershell
python -m pcb_report `
  --gerber board-top-copper.gbr board-bottom-copper.gbr board-outline.gbr board-silkscreen.gbr `
  --bom bom.csv `
  --pnp placement.csv `
  -o report.html
```

Następnie otwórz `report.html` w przeglądarce.

**Wymagania:**
- Python 3.9+. Sam kod narzędzia nie ma żadnych zależności z PyPI (używa wyłącznie biblioteki
  standardowej) — `pip install -e .` powyżej instaluje jedynie polecenie `pcb-report` jako skrót,
  nie pobiera żadnych pakietów.
- **Node.js ≥ 18** dostępny w `PATH` — wymagany tylko do renderowania plików Gerber (patrz niżej,
  sekcja "Dlaczego Node.js"). Reszta narzędzia (parsowanie BOM/pick-and-place, budowa HTML) jest
  czystym Pythonem. Jeśli zobaczysz ostrzeżenie *"Nie znaleziono polecenia 'node' w PATH"*: pobierz
  instalator LTS z [nodejs.org](https://nodejs.org/), zainstaluj z domyślnymi opcjami, **zamknij i
  otwórz terminal na nowo** (żeby PATH się odświeżył), i sprawdź `node --version`.

Repozytorium zawiera minimalny zestaw testowy w `examples/minimal/` — najprościej uruchomić gotowy
skrypt (nie wymaga wklejania wieloliniowych poleceń, sam ustawia wszystkie ścieżki):

- **Windows:** kliknij prawym przyciskiem na `examples\minimal\run_example.ps1` → *Uruchom za pomocą
  programu PowerShell* (albo z terminala: `powershell -File examples\minimal\run_example.ps1`).
- **macOS / Linux:** `bash examples/minimal/run_example.sh`

Efekt: plik `examples/minimal/report.html`, gotowy do otwarcia w przeglądarce.

Jeśli wolisz wywołać CLI ręcznie zamiast skryptu — patrz sekcje "macOS / Linux" i "Windows
(PowerShell)" powyżej, podstawiając ścieżki z `examples/minimal/`.

## Argumenty CLI

| Argument | Wymagany | Opis |
| --- | --- | --- |
| `--gerber PLIK [PLIK ...]` | tak | Pliki Gerber/Excellon (RS-274X) — miedź, maska, opis, obrys, wiertła. |
| `--bom PLIK` | tak | Plik BOM w formacie `.csv` lub `.xml`. |
| `--pnp PLIK` | nie | Plik pick-and-place `.csv` (pozycje X/Y/rotacja/strona). Bez niego wszystkie komponenty trzeba ustawić ręcznie w raporcie. |
| `--unit {mm,inch}` | nie | Jednostki współrzędnych w pliku pick-and-place (domyślnie `mm`). |
| `-o, --output PLIK` | nie | Ścieżka wyjściowa (domyślnie `report.html`). |
| `--report-id ID` | nie | Wymuszony klucz `localStorage` (domyślnie wyliczany automatycznie z nazw plików Gerber + zestawu oznaczeń — pozwala to na ponowne wygenerowanie raportu dla tego samego projektu bez utraty zaznaczonych checkboxów). |

## Format plików wejściowych

- **BOM (CSV)** — nagłówki (rozpoznawane bez rozróżniania wielkości liter): `Designator`/`Reference`/`RefDes`,
  `Value`, `Footprint`/`Package`, `Description`, `Manufacturer`, `MPN`, `Qty`. Pole z oznaczeniami może
  zawierać kilka wartości naraz, np. `"R1, R2, R5"` — typowe dla BOM-ów grupujących identyczne części
  w jednym wierszu. Kliknięcie takiego wiersza w raporcie podświetla **wszystkie** wymienione oznaczenia
  jednocześnie na wizualizacji płytki.
- **BOM (XML)** — parser jest heurystyczny: szuka węzłów zawierających pole typu Designator/Reference,
  ponieważ format XML BOM nie jest ustandaryzowany między systemami CAD. Dla większej niezawodności
  zalecany jest eksport do CSV.
- **Pick-and-place (CSV)** — nagłówki: `Designator`, `Mid X`/`X`, `Mid Y`/`Y`, `Rotation`, `Layer`/`Side`
  (`Top`/`Bottom`). Standardowy eksport z KiCad/Altium/Eagle.
- **Gerber** — dowolny zestaw plików RS-274X (miedź, maska, opis, obrys) i opcjonalnie Excellon
  (wiertła); typ warstwy jest rozpoznawany automatycznie po zawartości/nazwie pliku.

## Mapowanie komponentów BOM → wizualizacja PCB

1. **Z danymi pick-and-place** — każdy `designator` z BOM jest automatycznie mapowany na pozycję
   (x, y, rotacja, strona) z pliku PnP.
2. **Bez danych pozycyjnych (lub brak konkretnego oznaczenia w PnP)** — w wygenerowanym raporcie
   komponent jest oznaczony jako *"Brak pozycji"* z przyciskiem **„Ustaw na płytce”**: klikasz przycisk,
   a następnie klikasz na wizualizacji, aby ręcznie przypisać współrzędne. To działa w 100% w
   przeglądarce, po wygenerowaniu pliku — nie trzeba nic przeliczać ani ponownie uruchamiać narzędzia.
3. Domyślnie każdy umiejscowiony komponent ma widoczny znacznik **pinu 1** (żółta kropka przesunięta od
   środka zgodnie z rotacją komponentu).

## Architektura i uzasadnienie wyboru narzędzi

| Element | Wybór | Uzasadnienie |
| --- | --- | --- |
| Interfejs / logika | **Python 3, tylko biblioteka standardowa** (`csv`, `xml.etree.ElementTree`, `argparse`, `json`, `subprocess`) | zero zależności do zainstalowania przez `pip` — narzędzie działa "z pudełka" wszędzie, gdzie jest Python |
| Renderowanie Gerber → SVG | Zvendorowany, samodzielny bundle Node.js (`pcb_report/assets/tracespace-bundle.mjs`), zbudowany z [`@tracespace/core`](https://github.com/tracespace/tracespace) | parsowanie RS-274X (łuki, apertury, makra) od zera byłoby dużym, ryzykownym nakładem pracy; próba użycia czysto-pythonowej biblioteki (`pcb-tools`) napotkała na niedziałające, nieaktualizowane zależności natywne (cairocffi) przy instalacji — `@tracespace/core` jest jedyną sprawdzoną, aktywnie rozwijaną biblioteką do tego zadania. Zamiast wymagać `npm install` przy każdym uruchomieniu, bundle jest budowany raz (`build_tools/`, przez `esbuild`) do jednego pliku `.mjs` bez zależności — Python woła go przez `subprocess`, przekazując tylko listę ścieżek do plików Gerber i odczytując JSON (SVG + `viewBox` + ostrzeżenia) ze stdout |
| Wyjście | **Jeden statyczny plik HTML** (CSS + JS + dane BOM/placement/SVG w jednym pliku, bez zewnętrznych zasobów) | można go otworzyć od razu w przeglądarce, wysłać, zarchiwizować — bez hostowania serwera |
| Interaktywność w przeglądarce | Czysty JavaScript (bez frameworków) operujący na natywnym `<svg>` | wizualizacja płytki i znaczniki komponentów są w tym samym układzie współrzędnych `viewBox` (mm) co dane pick-and-place, więc zoom/pan (transformacja CSS) i zaznaczanie (klasy CSS) nie wymagają dodatkowych przeliczeń ani bibliotek |
| Trwałość stanu | `localStorage` przeglądarki, klucz = ID raportu (hash nazw plików Gerber + zestawu oznaczeń) | pozwala zachować checkboxy/sample/przeróbki między otwarciami tego samego raportu, bez backendu i bazy danych |

### Dlaczego Node.js jest wymagany tylko w jednym miejscu

Jedyny krok, który nie jest czystym Pythonem, to renderowanie Gerber → SVG (`pcb_report/gerber.py`
woła `node pcb_report/assets/tracespace-bundle.mjs <pliki...>`). Ten plik `.mjs` jest w pełni
samodzielny (wszystkie pakiety `@tracespace/*` są w niego wbudowane przez `esbuild`) — nie trzeba
robić `npm install`, wystarczy sam interpreter `node` w `PATH`. Jeśli Node.js nie jest dostępny,
narzędzie kończy się czytelnym komunikatem błędu, a reszta funkcjonalności (parsowanie BOM,
pick-and-place) pozostaje niezależna od tego kroku.

## Struktura projektu

```
pcb_report/
  cli.py                 # argparse CLI: --gerber --bom --pnp --unit -o
  models.py              # dataclasses: BomComponent, Placement, ViewBox, GerberRenderResult
  bom.py                 # parser BOM: CSV (stdlib csv) + XML (stdlib ElementTree, heurystyczny)
  placement.py           # parser pick-and-place CSV, konwersja jednostek mm/cale
  gerber.py              # subprocess -> assets/tracespace-bundle.mjs -> JSON (SVG + viewBox)
  report.py              # składa końcowy, samodzielny plik HTML (CSS + JS + dane w jednym pliku)
  assets/
    tracespace-bundle.mjs  # zvendorowany, samodzielny render Gerber->SVG (Node, brak npm install)
    report.css            # motyw: biel / niebieski / granat / szarości
    report.js             # cała logika w przeglądarce: taby, zoom/pan, zaznaczanie, Traceability
build_tools/              # narzędzie deweloperskie do przebudowania tracespace-bundle.mjs (nie jest
                           # potrzebne do uruchomienia pcb_report — patrz build_tools/README.md)
```

## Przebudowa silnika renderowania Gerber (tylko dla deweloperów)

`pcb_report/assets/tracespace-bundle.mjs` jest generowany raz i wpisany do repozytorium. Aby
zaktualizować go po zmianie wersji `@tracespace/core`:

```bash
cd build_tools
npm install
npm run build
```

## Znane ograniczenia

- Parser BOM XML jest heurystyczny — dla większej niezawodności zalecany jest eksport do CSV.
- Rozmiar znacznika komponentu na wizualizacji jest uproszczony (stały promień + znacznik pinu 1 wg
  rotacji) — narzędzie nie ma dostępu do rzeczywistej geometrii footprintu.
- `@tracespace/core` jest w wersji `5.0.0-alpha`; błędy renderowania konkretnych plików Gerber są
  przechwytywane i pokazywane jako ostrzeżenia w raporcie, bez przerywania działania całego narzędzia.
- `localStorage` jest przypisany do pochodzenia (origin) przeglądarki — w niektórych konfiguracjach
  otwieranie plików `file://` z restrykcyjnymi ustawieniami prywatności może ograniczać zapis stanu;
  w standardowej konfiguracji Chrome/Firefox/Edge działa to poprawnie (zweryfikowano).
