# GerbertoHTML — generator raportów Assembly / Traceability dla PCB

*[Deutsche Version dieser Anleitung](README.de.md)*

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

**Wersja językowa raportu:** w prawym górnym rogu wygenerowanego raportu jest przełącznik **PL / DE** —
zmienia język całego interfejsu (etykiety, przyciski, nagłówki tabel, komunikaty) bez ponownego
generowania pliku, więc jeden `report.html` można wysłać zarówno polsko-, jak i niemieckojęzycznemu
odbiorcy. Wybór zapamiętuje się w przeglądarce (niezależnie od `localStorage` konkretnego raportu).
Ostrzeżenia z parsowania plików wejściowych (widoczne w panelu "Dane wejściowe") oraz komunikaty
konsoli narzędzia pozostają po polsku niezależnie od tego przełącznika — dotyczą osoby uruchamiającej
narzędzie, nie odbiorcy raportu.

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
dowolnego katalogu. Ten krok instaluje dwie zależności (`gerbonara` do renderowania Gerberów,
`openpyxl` do odczytu BOM w formacie Excel) — nie trzeba niczego instalować osobno.

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

### Najwygodniej: auto-wykrywanie plików w katalogu projektu

Jeśli w katalogu projektu (eksport z Altium/KiCad) są pliki Gerber, jeden BOM i jeden (lub więcej —
np. osobno Top/Bottom) plik pick-and-place, wystarczy wskazać sam katalog — reszta wykrywa się
automatycznie po rozszerzeniu (Gerbery) i po zawartości nagłówków (BOM vs pick-and-place, patrz
niżej):

```bash
pcb-report sciezka/do/katalogu_projektu
```

(albo `pcb-report` bez argumentu, jeśli jesteś już w tym katalogu). Wynik trafia domyślnie do
`<katalog_projektu>/report.html`. To jest zalecany sposób użycia przy częstym, powtarzalnym
generowaniu raportów dla tego samego projektu — nie trzeba pamiętać ani wpisywać żadnych nazw plików.

Auto-wykrywanie można częściowo nadpisać — np. wskazać BOM jawnie, a Gerbery i PnP zostawić do
wykrycia:

```bash
pcb-report sciezka/do/projektu --bom moj_bom.xlsx
```

### Z jawnie podanymi plikami

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
| `KATALOG` (pozycyjny) | nie | Katalog projektu do przeszukania auto-wykrywaniem (domyślnie bieżący katalog). Ignorowany dla plików podanych jawnie poniżej. |
| `--gerber PLIK [PLIK ...]` | nie | Pliki Gerber/Excellon (RS-274X) — miedź, maska, opis, obrys, wiertła. Pominięcie = auto-wykrywanie w `KATALOG` po rozszerzeniu. |
| `--bom PLIK` | nie | Plik BOM w formacie `.csv`, `.xml` lub `.xlsx` (Excel). Pominięcie = auto-wykrywanie w `KATALOG`. |
| `--pnp PLIK [PLIK ...]` | nie | Plik(i) pick-and-place `.csv`/`.txt` — więcej niż jeden, gdy Top/Bottom są osobnymi plikami (typowe w Altium). Pominięcie = auto-wykrywanie w `KATALOG`. Bez żadnego pliku wszystkie komponenty trzeba ustawić ręcznie w raporcie. |
| `--unit {mm,inch}` | nie | Domyślne jednostki współrzędnych w pliku pick-and-place, używane tylko gdy nagłówek kolumny sam nie mówi jednostki (np. samo `X`/`Y` zamiast `Center-X(mm)`) — patrz niżej. |
| `-o, --output PLIK` | nie | Ścieżka wyjściowa (domyślnie `<KATALOG>/report.html`). |
| `--report-id ID` | nie | Wymuszony klucz `localStorage` (domyślnie wyliczany automatycznie z nazw plików Gerber + zestawu oznaczeń — pozwala to na ponowne wygenerowanie raportu dla tego samego projektu bez utraty zaznaczonych checkboxów). |
| `--all-layers` | nie | Zaznacz domyślnie wszystkie warstwy w panelu "Warstwy" raportu, zamiast tylko zwykle przydatnych (patrz sekcja "Format plików wejściowych"). Każdą warstwę można i tak dowolnie przełączyć bezpośrednio w raporcie. |
| `--non-interactive` | nie | Nie pytaj w terminalu o przeznaczenie nierozpoznanych plików (patrz "Jak działa auto-wykrywanie") — po prostu je pomiń, jak w wersjach bez tej funkcji. |

### Jak działa auto-wykrywanie (i jak rozróżnia BOM od pick-and-place)

Przeszukiwane jest **całe drzewo katalogów** pod wskazanym `KATALOG` (dowolna głębokość, dowolne
nazwy podfolderów) — folder "Project Outputs" z Altium typowo rozbija Gerber/NC Drill/BOM/
Pick-and-Place na osobne podfoldery, więc auto-wykrywanie nie ogranicza się do najwyższego poziomu.

Oba pliki (BOM i pick-and-place) bywają w tym samym formacie (`.csv`, a w Altium pick-and-place
często `.txt`) — sama nazwa rozszerzenia nic nie mówi o zawartości, więc auto-wykrywanie **otwiera i
sprawdza nagłówek kolumn** każdego kandydata, zamiast zgadywać po rozszerzeniu:

- Ma parę kolumn pozycji (`Mid X`/`Mid Y`, `Center-X`/`Center-Y`, `PosX`/`PosY`, ...) → **pick-and-place**.
- Ma kolumnę Designator/Reference, ale bez pary kolumn pozycji → **BOM**.
- Plik `.txt`, który w ogóle nie wygląda na tabelę z nagłówkiem, jest dodatkowo sprawdzany, czy da
  się go sparsować jako plik wiertła Excellon (Altium często eksportuje wiertła jako `.txt` — ta sama
  nazwa rozszerzenia co pick-and-place) — jeśli tak, trafia do listy plików Gerber, nie do BOM/PnP.
- Więcej niż jeden plik pasujący do BOM → traktowane jako **warianty montażu** (patrz niżej) zamiast
  błędu, o ile nazwy plików na to pozwalają; w przeciwnym razie trzeba wskazać właściwy przez `--bom`.
  Więcej niż jeden plik pick-and-place różniący się tylko stroną (Top/Bottom) jest **łączony**
  (typowy przypadek oddzielnych raportów Top/Bottom z Altium); różniący się czymś innym (np. też
  warianty) jest dopasowywany do wariantów BOM zamiast łączony w jedno.
- Jednostki (mm/mil/cal) w pick-and-place są odczytywane z samej nazwy kolumny, gdy ta ją zawiera
  (np. `Center-X(mil)`) — `--unit` jest używany tylko jako domyślna wartość dla kolumn bez podanej
  jednostki w nazwie (np. samo `X`).
- Plik, którego w ogóle nie da się rozpoznać jako BOM ani pick-and-place (np. jakiś raport
  statusu w formie tabeli) — jeśli narzędzie jest uruchomione w normalnym terminalu, **zapyta
  wprost**, czym ten plik jest (BOM / pick-and-place / pomiń), zamiast po cichu go ignorować.
  Wciśnięcie Enter pomija plik tak jak dotychczas. Żeby wyłączyć te pytania (np. przy uruchamianiu
  narzędzia automatycznie, bez człowieka przy klawiaturze), dodaj `--non-interactive` — wtedy
  nierozpoznane pliki są po prostu pomijane z ostrzeżeniem, tak jak działało to wcześniej.

## Format plików wejściowych

- **BOM (CSV lub Excel `.xlsx`)** — nagłówki (rozpoznawane bez rozróżniania wielkości liter):
  `Designator`/`Reference`/`RefDes`/`Ref Des` (oraz podobne warianty z kropkami/podkreślnikami),
  `Value`/`Comment` (Altium nazywa to pole "Comment"), `Footprint`/`Package`, `Description`,
  `Manufacturer`, `Qty`. Kolumna z numerem katalogowym producenta jest rozpoznawana szeroko —
  `MPN`, `MPN1`/`MPN2` (wiele zatwierdzonych producentów), `Part Number`, `Manufacturer Part Number`,
  `Mfr Part No.`, `P/N`, `Manufacturer P/N` itp. Dla `.xlsx` **przeszukiwane są wszystkie arkusze**
  (nie tylko ten, który był aktywny przy zapisie pliku) i pierwsze ~20 wierszy każdego z nich, aż
  znajdzie się wiersz z kolumną oznaczeń — typowe firmowe szablony BOM mają przed właściwą tabelą
  nagłówek/blok rewizji, więc to nie zawsze wiersz 1 arkusza 1. Jeśli w projekcie jest kilka plików
  wyglądających na BOM (np. `BOM.xlsx`, `BOM_Critical.xlsx`, `BOM_NotCritical.xlsx`), auto-wykrywanie
  zgłosi to jako niejednoznaczność i poprosi o wskazanie właściwego przez `--bom`. Pole z oznaczeniami
  może zawierać kilka wartości naraz, np. `"R1, R2, R5"` — typowe dla BOM-ów grupujących identyczne
  części w jednym wierszu. Kliknięcie takiego wiersza w raporcie podświetla **wszystkie** wymienione
  oznaczenia jednocześnie na wizualizacji płytki.
- **BOM (XML)** — parser jest heurystyczny: szuka węzłów zawierających pole typu Designator/Reference,
  ponieważ format XML BOM nie jest ustandaryzowany między systemami CAD. Dla większej niezawodności
  zalecany jest eksport do CSV.
- **Pick-and-place (CSV lub TXT)** — nagłówki: `Designator`/`Ref`, para kolumn pozycji w dowolnej z
  konwencji `Mid X`/`Mid Y`, `Center-X`/`Center-Y`, `PosX`/`PosY`, `Ref X`/`Ref Y` (opcjonalnie z
  jednostką w nazwie, np. `Center-X(mil)`), `Rotation`, `Layer`/`Side` (`Top`/`Bottom`). Standardowy
  eksport z KiCad/Altium/Eagle; delimiter (przecinek/tabulator/średnik) wykrywany automatycznie, a gdy
  żadnego nie ma — jak we własnym formacie KiCada (`Ref  Val  Package  PosX  PosY  Rot  Side`,
  kolumny wyrównane spacjami, bez separatora) albo w ASCII-owym raporcie Altium (`Free Format Pick
  and Place data`, też kolumny wyrównane spacjami, ale pola tekstowe typu Comment/Description są
  dodatkowo ujęte w cudzysłów, bo mogą same zawierać spacje i przecinki, np. `"TERM BLOCK HDR 2POS
  3.5MM"`) — kolumny są dzielone po dowolnym ciągu białych znaków **z poszanowaniem takich
  cudzysłowów** (spacja/przecinek wewnątrz `"..."` nie jest traktowana jako koniec kolumny). Altium
  często dodaje przed właściwym nagłówkiem linię tytułową/datę, a KiCad dodatkowo poprzedza sam
  nagłówek znakiem `#` (`# Ref  Val  ...`) — przeszukiwane jest pierwsze ~20 niepustych linii pliku
  (z tymczasowo zdjętym `#`) w poszukiwaniu tej z Designator+X+Y, więc żaden z tych formatów nie
  przeszkadza.
  Jeśli w pliku z delimiterem (np. przecinkiem) trafi się wiersz z komponentem, którego pole
  Comment/Value/Description samo zawiera ten znak bez ujęcia w cudzysłów (np. `GSM MODULE, 802.11
  b/g/n`), taki wiersz ma więcej pól niż nagłówek — kolumny X/Y "rozjeżdżają się" i bez obsługi tego
  przypadku trafiłyby do raportu jako bezsensowne wartości (fragmenty opisu zamiast liczb).
  Narzędzie wykrywa taką sytuację po samej liczbie pól i automatycznie sklaja z powrotem nadmiarowe
  fragmenty w kolumnę Comment/Value/Description, przywracając poprawne wyrównanie reszty kolumn dla
  tego wiersza — konsola wypisze ostrzeżenie z liczbą naprawionych wierszy, warto to jednak zweryfikować
  wzrokowo w raporcie. Naprawa działa tylko wtedy, gdy plik w ogóle ma taką kolumnę w nagłówku; w
  przeciwnym razie wiersz jest pomijany z ostrzeżeniem wskazującym na prawdopodobną przyczynę.
- **Gerber** — dowolny zestaw plików RS-274X (miedź, maska, opis, pasta, courtyard, obrys) i
  opcjonalnie Excellon (wiertła). Jeśli plik zawiera standardowy atrybut Gerber X2
  `%TF.FileFunction,...*%` (domyślne w nowszym eksporcie z Altium/KiCad), typ warstwy i strona są
  odczytywane właśnie z niego — nazwa pliku nie ma wtedy znaczenia. W przeciwnym razie (starszy,
  przed-X2 RS-274X, częsty w starszych eksportach z Altium) zgadywane są z nazwy pliku: rozpoznawane
  są konwencje KiCad (`*.gtl/.gbl/...` oraz `*-F.Cu.gbr/-B.Cu.gbr/...`, `*-In1.Cu.gbr/...` dla warstw
  wewnętrznych), Altium (`.G1`/`.G2`/... = wewnętrzne warstwy miedzi, `.GKO`/`.GML`/`GM1` = obrys,
  `GM13`/`GM14` = courtyard góra/dół, `GM15`/`GM16` = fabrykacja, pozostałe `.GM<numer>` = inna
  warstwa mechaniczna o nieznanym z nazwy przeznaczeniu) i typowe słowa kluczowe (`top`/`bottom`/
  `copper`/`mask`/`silk`/`paste`/`outline`/`edge`/`courtyard`/`inner`). Plik o nierozpoznanej w
  ogóle nazwie nadal zostanie wyrenderowany (w neutralnym kolorze, pokazany po obu stronach płytki)
  — patrz "Znane ograniczenia".
  Znaki opisu (silkscreen) z "dziurą" (np. `0`, `R`, `8`, `Q`) wyeksportowane jako wypełnione regiony
  wektorowe czcionki TrueType (typowe dla Altium/KiCad) są renderowane z prawdziwie wyciętym otworem
  (maska SVG odzwierciedlająca polaryzację "clear" z pliku Gerber), zamiast wyjść jako w pełni
  wypełniony kształt — to dotyczy tylko plików, które faktycznie używają takiej geometrii; pozostałe
  renderują się bez dodatkowego narzutu.

  **Domyślnie w widoku Assembly widoczne są: obrys, miedź zewnętrzna (góra/dół), silkscreen, pasta,
  courtyard i wiertła.** Miedź zewnętrzna jest celowo pokazywana — to na niej leżą pola lutownicze
  (pady) komponentów, czyli najbardziej czytelna wskazówka "gdzie fizycznie jest ten element"
  (potwierdzone porównaniem z ręcznym doborem warstw w przeglądarce Gerberów KiCada). Domyślnie
  ukryte są natomiast: **maska lutownicza** (tylko przebarwienie, nic nie wnosi), **wewnętrzne
  (zagrzebane) warstwy miedzi** (niewidoczne z zewnątrz, nieistotne przy montażu) oraz **inne,
  nierozpoznane warstwy mechaniczne Altium** (`.GM<numer>` poza obrysem/courtyardem) — w
  praktycznych projektach Altium bywa ich dziesiątki (wymiary, notatki fabrykacyjne, strefy
  wysokości...) i domyślnie tylko zaśmiecałyby widok.

  **To tylko domyślne ustawienie, nie twardy filtr** — klasyfikacja warstw to heurystyka (nazwa
  pliku albo atrybut X2), więc dla nietypowego projektu może się pomylić. W raporcie, w prawym
  górnym rogu widoku płytki, jest przycisk **„Warstwy”** otwierający panel z listą *każdego*
  wczytanego pliku Gerber osobno (nazwa, typ, strona) z checkboxem — można dowolnie włączyć lub
  wyłączyć każdą warstwę bez ponownego uruchamiania narzędzia, wybór zapisuje się tak samo jak
  reszta stanu (localStorage + eksport/import). Flaga `--all-layers` tylko zmienia, które warstwy
  są **domyślnie zaznaczone** przy pierwszym otwarciu raportu (wszystkie zamiast tylko powyższych)
  — nie jest już jedynym sposobem, by je zobaczyć.

## Mapowanie komponentów BOM → wizualizacja PCB

1. **Z danymi pick-and-place** — każdy `designator` z BOM jest automatycznie mapowany na pozycję
   (x, y, rotacja, strona) z pliku PnP.
2. **Bez danych pozycyjnych (lub brak konkretnego oznaczenia w PnP)** — w wygenerowanym raporcie
   oznaczenie jest podświetlone na pomarańczowo z podpisem *"Brak pozycji"* pod nim. Kliknij samo
   oznaczenie (nie tylko brakujące — **każde**, także już umiejscowione), a następnie kliknij na
   wizualizacji płytki, aby ręcznie przypisać/poprawić jego współrzędne. To działa w 100% w
   przeglądarce, po wygenerowaniu pliku — nie trzeba nic przeliczać ani ponownie uruchamiać narzędzia.
   Przydaje się to nie tylko przy brakujących pozycjach, ale też do poprawienia pojedynczego
   komponentu, którego pozycja z pliku pick-and-place okazała się błędna.
3. Domyślnie każdy umiejscowiony komponent ma widoczny znacznik **pinu 1** (żółta kropka przesunięta od
   środka zgodnie z rotacją komponentu).
4. Panel **"Dane wejściowe"** (lista plików Gerber i ostrzeżenia) jest domyślnie zwinięty — kliknij
   jego nagłówek, żeby go rozwinąć/schować, podobnie jak panel **"Warstwy"**.
5. Wizualizacja pokazuje **tylko komponenty z bieżącej strony** (Góra/Dół) — komponent umiejscowiony
   na dole nie jest w ogóle rysowany, gdy widok jest ustawiony na górę, i odwrotnie. Zaznaczenie
   komponentu (lub grupy) na liście po lewej podświetla na przyciskach **Góra/Dół** (pomarańczowa
   obwódka, niezależnie od tego, który jest aktualnie wybrany jako widok), po której stronie/stronach
   faktycznie się znajduje — grupa obejmująca komponenty z obu stron podświetli oba przyciski. Ustawianie
   pozycji ręcznie (patrz punkt 2. powyżej) przypisuje komponentowi tę stronę, na której akurat jest
   widok w momencie kliknięcia na płytce.
6. Znaczniki na wizualizacji są małe (mały kwadracik, a przy realnym dopasowaniu kształtu — sam
   obrys footprintu) zamiast dużych, wypełnionych kółek — przy gęściej upakowanej płytce duże kółka
   zasłaniałyby sąsiednie elementy i sam silkscreen. Zaznaczony komponent dostaje dodatkowo mały
   czerwony prostokąt wokół znacznika. Kliknięcie znacznika na wizualizacji zaznacza go też na liście
   po lewej i przewija listę tak, żeby ten wiersz był widoczny (przydatne przy długiej liście
   komponentów).

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

## Warianty montażu (Critical / NotCritical / ... )

Altium (i inne narzędzia) pozwalają zdefiniować **warianty projektu** — różne konfiguracje montażu
tej samej płytki (np. "Critical" = tylko kluczowe podzespoły na pierwszy montaż, "NotCritical" =
reszta, "Full"/domyślny = wszystko) — i eksportują osobny plik BOM (a często też osobny
pick-and-place) dla każdego wariantu. GerbertoHTML wykrywa to automatycznie:

- Jeśli auto-wykrywanie znajdzie **kilka plików wyglądających na BOM** tego samego projektu, zamiast
  błędu traktuje je jako warianty. Etykieta wariantu to część nazwy pliku, która różni je od siebie
  (np. `Board.xlsx` / `Board_Critical.xlsx` / `Board_NotCritical.xlsx` → warianty "Podstawowy" /
  "Critical" / "NotCritical").
- Analogicznie dla kilku plików pick-and-place, o ile nie wyglądają na zwykły podział Top/Bottom
  (wtedy nadal są łączone jak dotychczas) — każdy dopasowywany jest do wariantu BOM o tej samej lub
  podobnej nazwie. Gdy dopasowania po nazwie zabraknie dla dokładnie jednego wariantu BOM i dokładnie
  jednego pliku pick-and-place, są parowane jako ostatnia deska ratunku.
  Dla wariantów, których wciąż nie da się dopasować po nazwie (np. nazwy plików BOM i
  pick-and-place w ogóle się nie pokrywają), narzędzie sprawdza **rzeczywistą zawartość** — ile
  oznaczeń (designators) z danego wariantu BOM faktycznie występuje w każdym pozostałym pliku
  pick-and-place — i dopasowuje automatycznie, gdy jeden plik wyraźnie wygrywa tym pokryciem.
  Gdy to również jest niejednoznaczne (remis albo brak przewagi), a narzędzie jest uruchomione w
  normalnym terminalu, **zapyta wprost**, który plik pick-and-place pasuje do którego wariantu
  (z pokazanym % pokrycia oznaczeń dla każdego kandydata) — Enter pomija dopasowanie dla tego
  wariantu. Bez odpowiedzi (np. `--non-interactive` albo uruchomienie bez terminala) niesparowany
  wariant po prostu wymaga ręcznego ustawienia pozycji komponentów w raporcie (jak przy braku
  pick-and-place w ogóle).
- W konsoli pojawi się ostrzeżenie z listą wykrytych wariantów i wynikiem dopasowania
  pick-and-place — warto to sprawdzić, zwłaszcza gdy nazwy wariantów nie są oczywiste (np. osobny
  "Mechanical BOM" z akcesoriami mechanicznymi, a nie prawdziwy wariant montażu, też może zostać tu
  wymieniony, jeśli nazwa pliku na to wskazuje).

W wygenerowanym raporcie, jeśli wykryto więcej niż jeden wariant, w sidebarze Assembly pojawia się
lista rozwijana **„Wariant montażu”**. Przełączenie jej:

- Podmienia listę komponentów, sumy i panel braków na dane właściwe wybranemu wariantowi.
- Pokazuje na wizualizacji płytki tylko znaczniki komponentów należące do tego wariantu (reszta
  płytki — obrys, miedź, silkscreen — jest identyczna dla każdego wariantu, bo to wciąż ta sama
  fizyczna płytka).
- Śledzi Dostarczono/Zamontowano **osobno dla każdego wariantu** — zaznaczenie czegoś w wariancie
  "Critical" nie wpływa na postęp w "NotCritical". Ręcznie ustawione pozycje komponentów na płytce są
  natomiast wspólne dla wszystkich wariantów (to wciąż ten sam fizyczny punkt na płytce).
- Eksport/import stanu (patrz wyżej) przenosi postęp **wszystkich** wariantów naraz, więc
  przekazanie pliku stanu innej osobie nie gubi danych niezależnie od tego, który wariant akurat
  była otwarty.

Gdy wykryto tylko jeden BOM (typowy przypadek), lista wariantów jest ukryta i nic się nie zmienia w
dotychczasowym działaniu.

## Architektura i uzasadnienie wyboru narzędzi

| Element | Wybór | Uzasadnienie |
| --- | --- | --- |
| Interfejs / logika | **Python 3** — `csv`, `xml.etree.ElementTree`, `argparse`, `json` z biblioteki standardowej, plus dwie zależności pip (`gerbonara`, `openpyxl`) | minimalna liczba zależności; instalacja to jedno polecenie (`pip install -e .`), bez Node.js/npm |
| Renderowanie Gerber → SVG | [`gerbonara`](https://gitlab.com/gerbolyze/gerbonara) — czysto-pythonowy parser RS-274X/Excellon | parsowanie Gerberów (łuki, apertury, makra) od zera byłoby dużym, ryzykownym nakładem pracy. Pierwsza próba (`pcb-tools`) nie dała się zainstalować (niedziałające zależności natywne, cairocffi). `gerbonara` instaluje się czystym `pip` i renderuje geometrię **pojedynczego pliku** do SVG bez żadnych wymagań co do nazewnictwa czy kompletności zestawu — jego wysokopoziomowe API (`LayerStack`) wymaga pełnego, konwencjonalnie nazwanego zestawu plików fabrykacyjnych, więc `pcb_report/gerber.py` renderuje każdy plik osobno i **samodzielnie składa** je w jeden obraz (patrz niżej), zachowując tolerancję na dowolny, niepełny zestaw plików |
| Wyjście | **Jeden statyczny plik HTML** (CSS + JS + dane BOM/placement/SVG w jednym pliku, bez zewnętrznych zasobów) | można go otworzyć od razu w przeglądarce, wysłać, zarchiwizować — bez hostowania serwera |
| Interaktywność w przeglądarce | Czysty JavaScript (bez frameworków) operujący na natywnym `<svg>` | wizualizacja płytki i znaczniki komponentów są w tym samym układzie współrzędnych `viewBox` (mm) co dane pick-and-place, więc zoom/pan (transformacja CSS) i zaznaczanie (klasy CSS) nie wymagają dodatkowych przeliczeń ani bibliotek |
| Trwałość stanu | `localStorage` przeglądarki, klucz = ID raportu (hash nazw plików Gerber + zestawu oznaczeń) | pozwala zachować checkboxy/sample/przeróbki między otwarciami tego samego raportu, bez backendu i bazy danych |

### Jak działa kompozycja wielu plików Gerber w jeden obraz

`pcb_report/gerber.py` parsuje każdy plik osobno przez `gerbonara.rs274x.GerberFile`/
`gerbonara.excellon.ExcellonFile`, bierze jego geometrię (SVG) i ramkę graniczną (bounding box), po
czym:

1. Ustala typ warstwy (miedź/maska/opis/pasta/courtyard/obrys/wiertła) i stronę (góra/dół/obie).
   Jeśli plik zawiera standardowy atrybut Gerber X2 `%TF.FileFunction,...*%` (tak eksportują
   domyślnie Altium i KiCad), korzysta z niego — to niezawodny, niezależny od nazwy pliku sposób.
   W przeciwnym razie (starszy RS-274X bez atrybutów X2) zgaduje z nazwy pliku (prosta heurystyka,
   patrz `_classify_from_attrs`/`_classify_type`/`_classify_side` w kodzie).
2. Liczy wspólną ramkę graniczną (sumę) domyślnie widocznych plików (patrz "Format plików
   wejściowych") — to staje się `viewBox` całego SVG, żeby ukryte domyślnie warstwy (np. dziesiątki
   nieznanych mechanicznych plików o dużym rozmiarze) nie rozjeżdżały wyjściowego kadru.
3. Każdy plik trafia jako osobna, niezależnie przełączalna warstwa (`GerberLayer`) do panelu
   "Warstwy" w raporcie (patrz "Format plików wejściowych" wyżej), w kolejności rysowania miedź →
   maska → pasta → courtyard → opis → obrys → wiertła, każda w osobnym kolorze i przezroczystości.
5. Jeśli podano pick-and-place, próbuje dopasować każdemu oznaczeniu jego prawdziwy obrys z
   courtyard albo (gdy courtyard brak) z silkscreenu, zamiast rysować generyczny znacznik — patrz
   niżej "Dopasowywanie prawdziwych obrysów komponentów".

Dzięki temu narzędzie renderuje sensowny obraz płytki niezależnie od tego, czy dostaniesz 2 pliki czy
kompletny zestaw fabrykacyjny — kosztem nieco uproszczonego (nie w pełni fotorealistycznego)
wyglądu w porównaniu do dedykowanych narzędzi typu KiCad/gerbv.

### Dopasowywanie prawdziwych obrysów komponentów

Inspiracją była wtyczka [InteractiveHtmlBom](https://github.com/openscopeproject/InteractiveHtmlBom)
dla KiCada, która rysuje na wizualizacji prawdziwe kształty footprintów — z tą różnicą, że
GerbertoHTML nie ma dostępu do pliku płytki (`.kicad_pcb`/`PcbDoc`), tylko do samych Gerberów, więc
kształty trzeba odtworzyć z geometrii warstwy courtyard/silkscreen:

1. Dla każdej strony płytki bierze geometrię warstwy courtyard (preferowana — zwykle to prostokąt
   obrysu komponentu) albo, gdy jej brak, silkscreenu.
2. Grupuje sąsiadujące ze sobą prymitywy (linie/łuki/flashe) w klastry algorytmem Union-Find po
   nachodzeniu na siebie ramek granicznych (z niewielkim marginesem) — każdy klaster to kandydat na
   obrys jednego komponentu.
3. Dopasowuje klastry do oznaczeń z pick-and-place metodą najbliższego sąsiada (po współrzędnych
   środka), każdy klaster i każde oznaczenie może zostać dopasowane tylko raz, w promieniu
   ograniczonym przekątną klastra.
4. Oznaczenia, dla których nie znaleziono pasującego klastra (bo np. courtyard/silkscreen nie
   zawiera dla nich żadnej geometrii, albo geometria jest zbyt daleko/zbyt duża), dostają zwykły
   generyczny znacznik (kółko) — tak jak wcześniej.

To dopasowanie jest heurystyczne i "best effort" — dla typowych płytek z kompletnym courtyardem
działa dobrze, ale nie jest gwarantowane dla każdej płytki (gęsto upakowane komponenty, brak
courtyardu, niestandardowe warstwy fabrykacyjne). Liczbę dopasowanych komponentów narzędzie wypisuje
w konsoli po wygenerowaniu raportu.

## Struktura projektu

```
pcb_report/
  cli.py                 # argparse CLI: KATALOG --gerber --bom --pnp --unit -o
  discovery.py           # auto-wykrywanie Gerber/BOM/pick-and-place w katalogu projektu
  models.py              # dataclasses: BomComponent, Placement, ViewBox, GerberRenderResult
  bom.py                 # parser BOM: CSV/XLSX (stdlib csv + openpyxl) + XML (stdlib ElementTree)
  placement.py           # parser pick-and-place CSV/TXT, auto-wykrywanie delimitera i jednostek
  gerber.py              # gerbonara: parsowanie + kompozycja wielu plików Gerber -> jedno SVG
  report.py              # składa końcowy, samodzielny plik HTML (CSS + JS + dane w jednym pliku)
  assets/
    report.css            # motyw: biel / niebieski / granat / szarości
    report.js             # cała logika w przeglądarce: taby, zoom/pan, zaznaczanie, Traceability
examples/minimal/          # mały zestaw testowy + gotowe skrypty run_example.ps1 / .sh
```

## Znane ograniczenia

- Parser BOM XML jest heurystyczny — dla większej niezawodności zalecany jest eksport do CSV.
- Rozpoznawanie typu warstwy/strony Gerbera korzysta z atrybutu X2 `%TF.FileFunction,...*%`, gdy plik
  go zawiera (typowe dla eksportu z Altium/KiCad) — wtedy nazwa pliku nie ma znaczenia. Dla plików bez
  tego atrybutu (starszy RS-274X) klasyfikacja opiera się o nazwę pliku (prosta heurystyka) —
  nietypowe konwencje nazewnictwa mogą wtedy zostać źle zaklasyfikowane (plik nadal się wyrenderuje,
  tylko w neutralnym kolorze i po obu stronach płytki, ewentualnie nie zostanie odfiltrowany mimo że
  to miedź/maska; pojawi się o tym ostrzeżenie w raporcie).
- Kompozycja wielu warstw jest uproszczona (stałe kolory/przezroczystość per typ warstwy, bez
  właściwego maskowania miedzi przez maskę lutowniczą) — wystarczające do celów referencyjnych przy
  montażu, ale nie zastępuje dedykowanego przeglądarki Gerberów (np. gerbv, KiCad) do weryfikacji fab.
- Znacznik komponentu na wizualizacji pokazuje prawdziwy obrys z courtyard/silkscreen, gdy uda się go
  dopasować (patrz "Dopasowywanie prawdziwych obrysów komponentów" wyżej); w pozostałych przypadkach
  (brak geometrii, zbyt gęste upakowanie, brak pick-and-place) używany jest generyczny znacznik —
  stałe kółko + znacznik pinu 1 wg rotacji.
- `localStorage` jest przypisany do pochodzenia (origin) przeglądarki — w niektórych konfiguracjach
  otwieranie plików `file://` z restrykcyjnymi ustawieniami prywatności może ograniczać zapis stanu;
  w standardowej konfiguracji Chrome/Firefox/Edge działa to poprawnie (zweryfikowano).
