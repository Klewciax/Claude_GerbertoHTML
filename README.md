# GerbertoHTML — generator raportów Assembly / Traceability dla PCB

Narzędzie CLI w Pythonie: wskazujesz pliki **Gerber**, **BOM** (CSV/XML) i opcjonalnie **pick-and-place**
(CSV), a na wyjściu dostajesz **jeden samodzielny plik HTML** z dwiema zakładkami:

- **Assembly** — lista komponentów z BOM sprzężona dwustronnie z wizualizacją płytki (zoom/pan),
  checkboxy Dostarczono/Zamontowano, ręczne pozycjonowanie komponentów bez danych z pick-and-place.
- **Traceability** — numery sampli, wspólny stos przeróbek (rework), notatki per sampel.

Wygenerowany plik `report.html` można otworzyć bezpośrednio w przeglądarce (dwuklik, bez serwera),
wysłać mailem, dołączyć do dokumentacji partii produkcyjnej albo zarchiwizować. Jest w pełni
interaktywny — zmiany (ilości, sample, przeróbki, ręczne pozycje) zapisują się lokalnie w
przeglądarce (`localStorage`), więc kolejne otwarcie tego samego pliku pamięta poprzedni stan.

**Praca wielu osób nad tym samym raportem:** `localStorage` jest przypisany do jednej przeglądarki na
jednym komputerze — zniknie po wyczyszczeniu danych przeglądarki i nie jest widoczny na innym
urządzeniu. Do przekazywania stanu między osobami/komputerami służą przyciski **„Eksportuj stan”** /
**„Importuj stan”** w nagłówku raportu: eksport pobiera mały plik `.json` ze wszystkimi zmianami,
który można umieścić gdziekolwiek wygodnie danej osobie (SharePoint, Teams, dysk sieciowy, mail,
USB) — narzędzie nie narzuca konkretnego kanału. Import ostrzega, jeśli plik pochodzi z innego
raportu (inne pliki Gerber/BOM) albo jest starszy niż stan już otwarty w przeglądarce, żeby nie
nadpisać przypadkiem nowszej pracy starszym plikiem.

Narzędzie jest w 100% Pythonem — **nie wymaga Node.js** (wcześniejsza wersja korzystała z Node.js do
renderowania Gerberów; zostało to zastąpione czysto-pythonową biblioteką `gerbonara`, patrz sekcja
architektura niżej).

## Instalacja (3 kroki)

**1. Wymagania:** [Python 3.9+](https://www.python.org/downloads/) (przy instalacji na Windows
zaznacz "Add python.exe to PATH"). Nic więcej — żadnego Node.js, żadnych osobnych baz danych.

**2. Pobierz kod:**

```bash
git clone https://github.com/Klewciax/Claude_GerbertoHTML.git
cd Claude_GerbertoHTML
```

(Bez gita: przycisk **Code → Download ZIP** na stronie repo na GitHubie, rozpakuj, wejdź do
rozpakowanego folderu.)

**3. Zainstaluj:**

```bash
python -m pip install -e .
```

(Na niektórych systemach polecenie to `python3` zamiast `python` — jeśli `python -m pip ...` da
błąd "nie znaleziono polecenia", spróbuj `python3 -m pip install -e .`.)

Sprawdź, czy zadziałało:

```bash
pcb-report --help
```

Jeśli zobaczysz opis argumentów (`--gerber`, `--bom`, ...) — gotowe, `pcb-report` działa już z
dowolnego katalogu. Ten krok instaluje jedyną zależność (`gerbonara`, do renderowania Gerberów) —
nie trzeba niczego instalować osobno.

> **Na Windows: `'pcb-report' is not recognized`?** To najczęstszy problem po instalacji — polecenie
> zainstalowało się poprawnie, ale folder ze skryptami Pythona nie jest w `PATH`, więc system go nie
> widzi (poszukaj w outpucie kroku 3 ostrzeżenia *"...is installed in ...\Scripts which is not on
> PATH"`). Najprostsze obejście, działa zawsze i wszędzie — używaj `python -m pcb_report` zamiast
> samego `pcb-report`, uruchamiane **z głównego katalogu repozytorium** (tego z `pyproject.toml`):
> ```powershell
> python -m pcb_report --gerber ... --bom bom.csv --pnp placement.csv -o report.html
> ```
> Działa identycznie jak `pcb-report`, tylko trzeba pamiętać o katalogu. (Nigdy nie łącz tego z
> `python` — `python pcb-report ...` próbuje otworzyć plik o nazwie `pcb-report` jako skrypt, czego
> nie ma w repozytorium, i zawsze się wywali.)

## Szybki start

### Najpierw wypróbuj na przykładzie (zero pisania poleceń z własnymi ścieżkami)

Repozytorium zawiera mały zestaw testowy w `examples/minimal/` z gotowym skryptem:

- **Windows:** kliknij prawym przyciskiem na `examples\minimal\run_example.ps1` → *Uruchom za pomocą
  programu PowerShell* (albo z terminala: `powershell -File examples\minimal\run_example.ps1`).
- **macOS / Linux:** `bash examples/minimal/run_example.sh`

Efekt: plik `examples/minimal/report.html`, gotowy do otwarcia w przeglądarce. Jeśli to zadziałało —
instalacja jest poprawna.

### Z własnymi plikami

**macOS / Linux (bash/zsh):**

```bash
pcb-report \
  --gerber board-top-copper.gbr board-bottom-copper.gbr board-outline.gbr board-silkscreen.gbr \
  --bom bom.csv \
  --pnp placement.csv \
  -o report.html
```

**Windows (PowerShell)** — `\` na końcu linii to składnia bash i **nie zadziała** w PowerShellu
(zostanie każdorazowo zinterpretowany jako osobna, błędna komenda); użyj jednej linii:

```powershell
pcb-report --gerber board-top-copper.gbr board-bottom-copper.gbr board-outline.gbr board-silkscreen.gbr --bom bom.csv --pnp placement.csv -o report.html
```

Następnie otwórz `report.html` w przeglądarce.

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
  (wiertła); typ warstwy (miedź/maska/opis/obrys/wiertła) i strona (góra/dół) są zgadywane po nazwie
  pliku — rozpoznawane są konwencje KiCad (`*.gtl/.gbl/...` oraz `*-F.Cu.gbr/-B.Cu.gbr/...`) i typowe
  słowa kluczowe (`top`/`bottom`/`copper`/`mask`/`silk`/`paste`/`outline`/`edge`). Plik o nierozpoznanej
  nazwie nadal zostanie wyrenderowany (w neutralnym kolorze, pokazany po obu stronach płytki) — patrz
  "Znane ograniczenia".

## Mapowanie komponentów BOM → wizualizacja PCB

1. **Z danymi pick-and-place** — każdy `designator` z BOM jest automatycznie mapowany na pozycję
   (x, y, rotacja, strona) z pliku PnP.
2. **Bez danych pozycyjnych (lub brak konkretnego oznaczenia w PnP)** — w wygenerowanym raporcie
   komponent jest oznaczony jako *"Brak pozycji"* z przyciskiem **„Ustaw na płytce”**: klikasz przycisk,
   a następnie klikasz na wizualizacji, aby ręcznie przypisać współrzędne. To działa w 100% w
   przeglądarce, po wygenerowaniu pliku — nie trzeba nic przeliczać ani ponownie uruchamiać narzędzia.
3. Domyślnie każdy umiejscowiony komponent ma widoczny znacznik **pinu 1** (żółta kropka przesunięta od
   środka zgodnie z rotacją komponentu).

## Grupowanie i śledzenie ilości (Dostarczono / Zamontowano)

Lista komponentów jest zawsze posortowana naturalnie po oznaczeniu (R1, R2, R3, R10, C1… zamiast
alfabetycznie R1, R10, R2). Checkbox **„Grupuj wg części (MPN)”** w sidebarze Assembly przełącza
widok:

- **Zgrupowany (domyślny)** — wiersze łączone po MPN (a gdy go brak — po Wartości+Footprincie),
  niezależnie od tego, jak były pogrupowane w oryginalnym pliku BOM. Każdy wiersz ma edytowalne pole
  **„Potrzeba”** (domyślnie = liczba pozycji/refdesów, można nadpisać np. żeby doliczyć zapas),
  oraz pola **„Dostarczono”** i **„Zamontowano”** — liczby wpisywane ręcznie lub przyciskiem
  **„Wszystko”** (ustawia wartość = potrzeba). Brakująca ilość liczy się automatycznie i jest
  widoczna zarówno przy wierszu, jak i w zbiorczym panelu **„Braki”** na dole strony Assembly.
- **Płaski (bez grupowania)** — każdy refdes jako osobny wiersz, do szybkiego zlokalizowania
  pojedynczej pozycji na płytce; pokazuje status ilościowy całej grupy, do której należy, ale nie
  pozwala edytować liczb (edycja jest tylko w widoku zgrupowanym).

Kliknięcie wiersza (lub znacznika na płytce) w widoku **zgrupowanym** podświetla na płytce
**wszystkie** refdesy danej części naraz. W widoku **płaskim** podświetla się tylko wybrany,
pojedynczy refdes.

Ponieważ status jest liczony na poziomie części (a nie pojedynczego refdesu — narzędzie nie wie,
*który konkretnie* egzemplarz został dostarczony/zamontowany), kolor znacznika na płytce odzwierciedla
próg dla całej grupy: szary = nic, żółty = częściowo/w całości dostarczone, zielony = częściowo/w
całości zamontowane (jaśniejszy odcień = częściowo, pełny = w całości; zamontowanie ma pierwszeństwo
przed dostawą w kolorowaniu).

## Architektura i uzasadnienie wyboru narzędzi

| Element | Wybór | Uzasadnienie |
| --- | --- | --- |
| Interfejs / logika | **Python 3** — `csv`, `xml.etree.ElementTree`, `argparse`, `json` z biblioteki standardowej, plus jedna zależność pip (`gerbonara`) | minimalna liczba zależności; instalacja to jedno polecenie (`pip install -e .`), bez Node.js/npm |
| Renderowanie Gerber → SVG | [`gerbonara`](https://gitlab.com/gerbolyze/gerbonara) — czysto-pythonowy parser RS-274X/Excellon | parsowanie Gerberów (łuki, apertury, makra) od zera byłoby dużym, ryzykownym nakładem pracy. Pierwsza próba (`pcb-tools`) nie dała się zainstalować (niedziałające zależności natywne, cairocffi). `gerbonara` instaluje się czystym `pip` i renderuje geometrię **pojedynczego pliku** do SVG bez żadnych wymagań co do nazewnictwa czy kompletności zestawu — jego wysokopoziomowe API (`LayerStack`) wymaga pełnego, konwencjonalnie nazwanego zestawu plików fabrykacyjnych, więc `pcb_report/gerber.py` renderuje każdy plik osobno i **samodzielnie składa** je w jeden obraz (patrz niżej), zachowując tolerancję na dowolny, niepełny zestaw plików |
| Wyjście | **Jeden statyczny plik HTML** (CSS + JS + dane BOM/placement/SVG w jednym pliku, bez zewnętrznych zasobów) | można go otworzyć od razu w przeglądarce, wysłać, zarchiwizować — bez hostowania serwera |
| Interaktywność w przeglądarce | Czysty JavaScript (bez frameworków) operujący na natywnym `<svg>` | wizualizacja płytki i znaczniki komponentów są w tym samym układzie współrzędnych `viewBox` (mm) co dane pick-and-place, więc zoom/pan (transformacja CSS) i zaznaczanie (klasy CSS) nie wymagają dodatkowych przeliczeń ani bibliotek |
| Trwałość stanu | `localStorage` przeglądarki, klucz = ID raportu (hash nazw plików Gerber + zestawu oznaczeń) | pozwala zachować checkboxy/sample/przeróbki między otwarciami tego samego raportu, bez backendu i bazy danych |

### Jak działa kompozycja wielu plików Gerber w jeden obraz

`pcb_report/gerber.py` parsuje każdy plik osobno przez `gerbonara.rs274x.GerberFile`/
`gerbonara.excellon.ExcellonFile`, bierze jego geometrię (SVG) i ramkę graniczną (bounding box), po
czym:

1. Zgaduje typ warstwy (miedź/maska/opis/pasta/obrys/wiertła) i stronę (góra/dół/obie) z nazwy pliku
   (prosta heurystyka, patrz `_classify_type`/`_classify_side` w kodzie).
2. Liczy wspólną ramkę graniczną (sumę) wszystkich plików — to staje się `viewBox` całego SVG.
3. Nakłada wszystkie warstwy dla danej strony na jeden `<g>`, w kolejności miedź → maska → pasta →
   opis → obrys → wiertła, każdą w osobnym kolorze i przezroczystości.

Dzięki temu narzędzie renderuje sensowny obraz płytki niezależnie od tego, czy dostaniesz 2 pliki czy
kompletny zestaw fabrykacyjny — kosztem nieco uproszczonego (nie w pełni fotorealistycznego)
wyglądu w porównaniu do dedykowanych narzędzi typu KiCad/gerbv.

## Struktura projektu

```
pcb_report/
  cli.py                 # argparse CLI: --gerber --bom --pnp --unit -o
  models.py              # dataclasses: BomComponent, Placement, ViewBox, GerberRenderResult
  bom.py                 # parser BOM: CSV (stdlib csv) + XML (stdlib ElementTree, heurystyczny)
  placement.py           # parser pick-and-place CSV, konwersja jednostek mm/cale
  gerber.py              # gerbonara: parsowanie + kompozycja wielu plików Gerber -> jedno SVG
  report.py              # składa końcowy, samodzielny plik HTML (CSS + JS + dane w jednym pliku)
  assets/
    report.css            # motyw: biel / niebieski / granat / szarości
    report.js             # cała logika w przeglądarce: taby, zoom/pan, zaznaczanie, Traceability
examples/minimal/          # mały zestaw testowy + gotowe skrypty run_example.ps1 / .sh
```

## Znane ograniczenia

- Parser BOM XML jest heurystyczny — dla większej niezawodności zalecany jest eksport do CSV.
- Rozpoznawanie typu warstwy/strony Gerbera opiera się o nazwę pliku (prosta heurystyka), nie o
  zawartość/nagłówki pliku — nietypowe konwencje nazewnictwa mogą zostać źle zaklasyfikowane
  (plik nadal się wyrenderuje, tylko w neutralnym kolorze i po obu stronach płytki; pojawi się o tym
  ostrzeżenie w raporcie).
- Kompozycja wielu warstw jest uproszczona (stałe kolory/przezroczystość per typ warstwy, bez
  właściwego maskowania miedzi przez maskę lutowniczą) — wystarczające do celów referencyjnych przy
  montażu, ale nie zastępuje dedykowanego przeglądarki Gerberów (np. gerbv, KiCad) do weryfikacji fab.
- Rozmiar znacznika komponentu na wizualizacji jest uproszczony (stały promień + znacznik pinu 1 wg
  rotacji) — narzędzie nie ma dostępu do rzeczywistej geometrii footprintu.
- `localStorage` jest przypisany do pochodzenia (origin) przeglądarki — w niektórych konfiguracjach
  otwieranie plików `file://` z restrykcyjnymi ustawieniami prywatności może ograniczać zapis stanu;
  w standardowej konfiguracji Chrome/Firefox/Edge działa to poprawnie (zweryfikowano).
