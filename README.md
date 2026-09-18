# GerbertoHTML — narzędzie do zarządzania montażem PCB

Aplikacja webowa (SPA) do zarządzania montażem płytek PCB (EMS/PCB assembly), z dwiema zakładkami:

- **Assembly** — lista komponentów z BOM sprzężona dwustronnie z wizualizacją płytki (zoom/pan), statusy dostawy i montażu.
- **Traceability** — numery sampli, wspólny stos przeróbek (rework) i notatki per sampel.

## Stack technologiczny i uzasadnienie wyboru

| Obszar | Wybór | Uzasadnienie |
| --- | --- | --- |
| Framework UI | **React 19 + TypeScript**, bundler **Vite** | szybki dev-loop (HMR), silne typowanie dla danych BOM/placement, standard w narzędziach inżynierskich |
| Stan aplikacji | **Zustand** (+ `persist` middleware, localStorage) | prosty, bez boilerplate'u Reduxa; `persist` daje "za darmo" zachowanie stanu BOM/statusów/reworków między sesjami — istotne przy pracy zmianowej na hali produkcyjnej |
| Renderowanie Gerber → SVG | **`@tracespace/core`** (część projektu [tracespace](https://github.com/tracespace/tracespace)) | jedyna dojrzała, czysto-JS biblioteka parsująca RS-274X (Gerber X2) i Excellon (wiertła) i renderująca realny obraz płytki (miedź, maska, opis, otwory) do SVG **bezpośrednio w przeglądarce**, bez backendu/serwera renderującego. Alternatywy (`pcb-stackup`, node-gerber) są starsze/mniej utrzymywane; pisanie własnego parsera RS-274X od zera byłoby nieuzasadnionym nakładem pracy |
| Canvas/wektory + interakcja | **Konva / react-konva** | wyrenderowane SVG płytki jest ładowane jako bitmapa tła (`Konva.Image`), a nad nim rysowane są w tym samym układzie współrzędnych (mm) interaktywne markery komponentów — okręgi, podświetlenia, etykiety. Konva daje wydajny hit-testing, natywne zoom/pan (transformacje `Stage`/`Group`) i płynne przerysowywanie przy zaznaczaniu, co przy podejściu "czyste SVG + React" byłoby wolniejsze przy większej liczbie elementów |
| Parsowanie BOM (CSV) | **PapaParse** | de facto standard do CSV w przeglądarce, dobra obsługa cudzysłowów/separatorów, wykrywanie nagłówków |
| Parsowanie BOM (XML) | **fast-xml-parser** | lekki, szybki parser XML→JS działający w przeglądarce; format BOM w XML nie jest ustandaryzowany między CAD-ami (Altium/KiCad/OrCAD eksportują różnie), więc parser BOM-a XML działa heurystycznie (patrz niżej) |
| Identyfikatory | **uuid** | stabilne id rekordów niezależne od kolejności w tablicy |

Cała aplikacja jest w 100% front-endowa (statyczny SPA) — nie wymaga backendu do renderowania Gerberów, co upraszcza wdrożenie (może być hostowana jako zwykłe pliki statyczne).

## Mapowanie komponentów BOM → wizualizacja PCB

Wymaganie: skojarzenie wierszy BOM z elementami na wizualizacji na podstawie oznaczeń (R1, C2, U3…).

1. **Dane pozycyjne (zalecane)** — jeśli dostępny jest plik **pick-and-place** (CSV z kolumnami typu `Designator, Mid X, Mid Y, Rotation, Layer`, eksportowany z KiCad/Altium/Eagle), aplikacja mapuje każdy `designator` na dokładną pozycję (x, y, rotacja, strona) na płytce. To jest ścieżka w pełni automatyczna.
2. **Brak danych pozycyjnych** — jeśli PnP nie jest dostępny (lub nie zawiera danego oznaczenia), komponent jest oznaczony na liście jako *"Brak pozycji"* z przyciskiem **„Ustaw na płytce”**: użytkownik klika przycisk, a następnie klika bezpośrednio na wizualizacji PCB, aby ręcznie przypisać współrzędne temu oznaczeniu. To częściowo-automatyczne/manualne rozwiązanie pozwala pracować nawet bez pliku PnP.
3. **Wiele oznaczeń w jednym wierszu BOM** — typowe eksporty BOM grupują identyczne części w jednym wierszu (`R1, R2, R5` jako jedna linia „rezystor 10k, 0402”). Parser BOM obsługuje to natywnie (dzieli pole „Designator/Reference” po przecinkach/spacjach), a kliknięcie takiego wiersza na liście podświetla **wszystkie** wystąpienia tych oznaczeń jednocześnie na wizualizacji.

Domyślnie każdy komponent, który ma przypisaną pozycję, ma wizualnie oznaczony **pin 1** (mały żółty znacznik przesunięty od środka komponentu zgodnie z jego rotacją) — zgodnie z wymaganiem.

## Struktura projektu

```
src/
  types.ts                     # wspólne typy domenowe (BomComponent, Placement, Sample, ReworkDef, ...)
  store/
    useAppStore.ts             # jedyne źródło prawdy (Zustand): BOM, placementy, statusy, rework, sample
  lib/
    gerber.ts                  # pipeline @tracespace/core: read → plot → renderLayers → renderBoard → SVG
    useSvgImage.ts             # hook ładujący string SVG jako HTMLImageElement (Blob URL) dla Konva
    bomParser.ts                # parser BOM: CSV (PapaParse) + XML (fast-xml-parser, heurystyczny)
    placementParser.ts         # parser pliku pick-and-place (CSV), konwersja jednostek mm/cale
  components/
    layout/
      Tabs.tsx                 # przełącznik zakładek Assembly / Traceability
    assembly/
      AssemblyTab.tsx          # layout: lista (lewo) + wizualizacja (prawo), przełącznik Top/Bottom
      FileUploadPanel.tsx      # wgrywanie plików Gerber / BOM / PnP
      ComponentList.tsx        # tabela komponentów: checkboxy Dostarczono/Zamontowano, wybór wiersza
      PcbViewer.tsx            # Konva Stage: zoom/pan, tło = render Gerber, markery komponentów + pin1
    traceability/
      TraceabilityTab.tsx      # layout: wspólna lista reworków (lewo) + siatka kart sampli (prawo)
      ReworkPool.tsx           # dodawanie/usuwanie pozycji na wspólnym stosie przeróbek
      SampleCard.tsx           # karta sampla: checkboxy względem wspólnej listy reworków + notatki
  App.tsx                       # kompozycja: nagłówek + zakładki
  index.css                     # motyw: biel / niebieski / granat / szarości
```

### Przepływ danych (Assembly)

```
Pliki Gerber ──▶ gerber.ts (@tracespace/core) ──▶ SVG + viewBox ──▶ store.gerber
Plik BOM (CSV/XML) ──▶ bomParser.ts ──▶ BomComponent[] ──▶ store.components
Plik PnP (CSV) ──▶ placementParser.ts ──▶ Placement[] (po designatorze) ──▶ store.placements
                                                                              │
ComponentList (klik na wiersz) ──▶ store.selectedComponentId ────────────────┤
                                                                              ▼
                                                            PcbViewer (Konva): dla KAŻDEGO
                                                     designatora zaznaczonego wiersza rysuje
                                                     podświetlenie na wspólnej płaszczyźnie mm
```

Kluczowe dla płynności: `PcbViewer` trzyma layer Gerbera i warstwę markerów w **tym samym układzie współrzędnych** (milimetry, oś Y odwrócona zgodnie z konwencją SVG używaną przez `@tracespace/core`), więc zaznaczenie w liście propaguje się do Canvasu przez zwykły re-render Reacta/Konva — bez dodatkowych przeliczeń czy opóźnień.

## Uruchomienie

```bash
npm install
npm run dev       # serwer deweloperski
npm run build     # build produkcyjny (tsc + vite build) do ./dist
```

## Znane ograniczenia / dalsze kroki

- Parser BOM XML jest heurystyczny (szuka węzłów z polem typu Designator/Reference) ze względu na brak jednego standardu formatu XML BOM między systemami CAD — dla większej niezawodności zalecany jest eksport BOM do CSV.
- Rozmiar/kształt markera komponentu jest uproszczony (stały promień + znacznik pin 1 wg rotacji) — biblioteka nie ma dostępu do rzeczywistej geometrii footprintu (do tego potrzebny byłby plik biblioteki komponentów/IPC, poza zakresem BOM+PnP).
- `@tracespace/core` jest w wersji `5.0.0-alpha`; pipeline jest opakowany w `try/catch` z czytelnymi komunikatami błędów, tak aby błąd renderowania Gerbera nie blokował reszty aplikacji (BOM, statusy, Traceability działają niezależnie).
