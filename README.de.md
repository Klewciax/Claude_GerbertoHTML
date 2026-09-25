# GerbertoHTML — Generator für Assembly-/Traceability-Berichte für Leiterplatten

*[Polnische Originalanleitung](README.md)*

Ein Python-CLI-Tool: Du gibst **Gerber**-Dateien, eine **Stückliste (BOM)** (CSV/XML) und optional
**Pick-and-Place**-Daten (CSV) an, und erhältst als Ergebnis **eine einzige, eigenständige HTML-Datei**
mit zwei Reitern:

- **Assembly** — Bauteilliste aus der Stückliste, zweiseitig verknüpft mit der Platinenvisualisierung
  (Zoom/Verschieben), Checkboxen für Geliefert/Bestückt, manuelle Positionierung von Bauteilen ohne
  Pick-and-Place-Daten.
- **Traceability** — Musternummern, gemeinsamer Nacharbeits-Pool (Rework) mit Fotos an jeder
  Nacharbeit (als Nachweis/Anleitung ihrer Durchführung), Notizen pro Muster, gemeinsame Liste von
  Softwareversionen (mit klickbarem Download-Link) je Muster per Dropdown-Liste zugewiesen.

Die erzeugte Datei `report.html` lässt sich direkt im Browser öffnen (Doppelklick, ohne Server), per
E-Mail versenden, der Fertigungsdokumentation beilegen oder archivieren. Sie ist voll interaktiv —
Änderungen (Mengen, Muster, Nacharbeiten, manuelle Positionen) werden lokal im Browser gespeichert
(`localStorage`), sodass beim nächsten Öffnen derselben Datei der vorherige Stand erhalten bleibt.

**Zusammenarbeit mehrerer Personen am selben Bericht:** `localStorage` ist an einen bestimmten Browser
auf einem bestimmten Computer gebunden — er verschwindet beim Löschen der Browserdaten und ist auf
einem anderen Gerät nicht sichtbar. Zum Weitergeben des Status zwischen Personen/Computern dienen die
Schaltflächen **„Status exportieren“** / **„Status importieren“** im Kopfbereich des Berichts: der
Export lädt eine kleine `.json`-Datei mit allen Änderungen herunter, die auf beliebigem Weg weitergegeben
werden kann (SharePoint, Teams, Netzlaufwerk, E-Mail, USB-Stick) — das Tool schreibt keinen bestimmten
Kanal vor. Der Import warnt, wenn die Datei aus einem anderen Bericht stammt (andere Gerber-/BOM-Dateien)
oder älter ist als der bereits im Browser geöffnete Stand, damit nicht versehentlich neuere Arbeit mit
einer älteren Datei überschrieben wird.

Das Tool ist zu 100 % in Python geschrieben — **es benötigt kein Node.js** (eine frühere Version nutzte
Node.js zum Rendern der Gerber-Dateien; das wurde durch die reine Python-Bibliothek `gerbonara` ersetzt,
siehe Abschnitt „Architektur“ weiter unten).

**Anpassen der Oberfläche an den Bildschirm:** Die Schaltfläche ☀️/🌙 im Kopfbereich schaltet zwischen
**hellem und dunklem Design** für den ganzen Bericht um. Im Assembly-Tab lässt sich die Seitenleiste
(Eingabedaten + Bauteilliste) **an ihrer rechten Kante ziehen**, um sie breiter oder schmaler zu
machen, und in der Bauteiltabelle selbst lässt sich **jede Spalte an ihrer rechten Kante ziehen**, um
ihre Breite anzupassen (besonders nützlich auf einem kleineren Laptop-Bildschirm, wo die Standardmaße
Inhalte abschneiden können). Das Panel **„Fehlmengen (Lieferung / Bestückung)“** unten im selben Tab
funktioniert genauso: seine **obere Kante lässt sich ziehen**, um seine Höhe zu ändern, und der Pfeil
▾/▸ neben der Überschrift **klappt es auf die reine Kopfzeile zusammen** (nützlich, wenn die
Fehlmengenliste gerade im Weg ist, aber nicht gebraucht wird). Design, Seitenleistenbreite,
Spaltenbreiten sowie Höhe/Zustand des Fehlmengen-Panels sind Browsereinstellungen (wie die Sprache) —
sie gehören nicht zu den Berichtsdaten und werden daher nicht über Export/Import des Status
übertragen; jede Person passt sie unabhängig an ihren eigenen Bildschirm an.

**Sprachversion des Berichts:** Oben rechts im erzeugten Bericht befindet sich ein Umschalter
**PL / DE** — er ändert die Sprache der gesamten Oberfläche (Beschriftungen, Schaltflächen,
Tabellenüberschriften, Meldungen), ohne die Datei neu zu erzeugen. So kann dieselbe `report.html`
sowohl an polnisch- als auch an deutschsprachige Empfänger verschickt werden. Die Auswahl wird im
Browser gemerkt (unabhängig vom `localStorage` eines einzelnen Berichts). Warnungen aus dem Parsen der
Eingabedateien (sichtbar im Panel „Eingabedaten“ und in der Konsole beim Erzeugen des Berichts) sind
unabhängig von diesem Umschalter auf Englisch — **die Konsole/das Terminal des Tools (der gesamte beim
Ausführen von `python -m pcb_report` ausgegebene Text, einschließlich `--help`) ist bewusst auf
Englisch** (international), unabhängig von der im Bericht selbst gewählten Sprache, damit die Person,
die das Tool ausführt, kein Polnisch können muss.

## Installation (3 Schritte)

**1. Voraussetzungen:** [Python 3.9+](https://www.python.org/downloads/) (bei der Installation unter
Windows „Add python.exe to PATH“ aktivieren). Sonst nichts weiter — kein Node.js, keine separate
Datenbank.

**2. Code herunterladen:**

```bash
git clone https://github.com/Klewciax/Claude_GerbertoHTML.git
cd Claude_GerbertoHTML
```

(Ohne Git: Schaltfläche **Code → Download ZIP** auf der Repo-Seite bei GitHub, entpacken, in den
entpackten Ordner wechseln.)

**3. Installieren:**

```bash
python -m pip install -e .
```

(Auf manchen Systemen heißt der Befehl `python3` statt `python` — wenn `python -m pip ...` den Fehler
„Befehl nicht gefunden“ liefert, versuche `python3 -m pip install -e .`.)

Prüfen, ob es funktioniert hat:

```bash
pcb-report --help
```

Wenn eine Beschreibung der Argumente erscheint (`--gerber`, `--bom`, …) — fertig, `pcb-report`
funktioniert jetzt aus jedem beliebigen Verzeichnis. Dieser Schritt installiert zwei Abhängigkeiten
(`gerbonara` zum Rendern der Gerber-Dateien, `openpyxl` zum Lesen von Stücklisten im Excel-Format) —
es muss nichts separat installiert werden.

> **Unter Windows: `'pcb-report' is not recognized`?** Das ist das häufigste Problem nach der
> Installation — der Befehl wurde korrekt installiert, aber der Ordner mit den Python-Skripten befindet
> sich nicht im `PATH`, sodass das System ihn nicht findet (suche in der Ausgabe von Schritt 3 nach der
> Warnung *„...is installed in ...\Scripts which is not on PATH“*). Die einfachste, überall
> funktionierende Umgehung: verwende `python -m pcb_report` statt einfach `pcb-report`, ausgeführt
> **aus dem Hauptverzeichnis des Repositories** (dem mit `pyproject.toml`):
> ```powershell
> python -m pcb_report --gerber ... --bom bom.csv --pnp placement.csv -o report.html
> ```
> Funktioniert genauso wie `pcb-report`, nur muss man an das Verzeichnis denken. (Niemals mit `python`
> kombinieren — `python pcb-report ...` versucht, eine Datei namens `pcb-report` als Skript zu öffnen,
> die es im Repository nicht gibt, und schlägt immer fehl.)

## Schnellstart

### Zuerst am Beispiel ausprobieren (kein Tippen von Befehlen mit eigenen Pfaden nötig)

Das Repository enthält einen kleinen Testdatensatz unter `examples/minimal/` mit einem fertigen Skript:

- **Windows:** Rechtsklick auf `examples\minimal\run_example.ps1` → *Mit PowerShell ausführen*
  (oder im Terminal: `powershell -File examples\minimal\run_example.ps1`).
- **macOS / Linux:** `bash examples/minimal/run_example.sh`

Ergebnis: die Datei `examples/minimal/report.html`, bereit zum Öffnen im Browser. Wenn das funktioniert
hat, ist die Installation korrekt.

### Am bequemsten: automatische Erkennung der Dateien im Projektordner

Wenn im Projektordner (Export aus Altium/KiCad) Gerber-Dateien, eine Stückliste und eine (oder mehrere —
z. B. getrennt für Top/Bottom) Pick-and-Place-Datei liegen, genügt die Angabe des Ordners — der Rest
wird automatisch erkannt, anhand der Dateiendung (Gerber-Dateien) und anhand des Inhalts der Kopfzeilen
(Stückliste vs. Pick-and-Place, siehe unten):

```bash
pcb-report pfad/zum/projektordner
```

(oder `pcb-report` ohne Argument, wenn du dich bereits in diesem Ordner befindest). Das Ergebnis landet
standardmäßig unter `<projektordner>/report.html`. Das ist die empfohlene Vorgehensweise bei häufiger,
wiederholter Berichtserstellung für dasselbe Projekt — es müssen keine Dateinamen gemerkt oder
eingetippt werden.

Die automatische Erkennung lässt sich teilweise überschreiben — z. B. die Stückliste explizit angeben
und Gerber-Dateien sowie Pick-and-Place der Erkennung überlassen:

```bash
pcb-report pfad/zum/projekt --bom meine_bom.xlsx
```

### Mit explizit angegebenen Dateien

**macOS / Linux (bash/zsh):**

```bash
pcb-report \
  --gerber board-top-copper.gbr board-bottom-copper.gbr board-outline.gbr board-silkscreen.gbr \
  --bom bom.csv \
  --pnp placement.csv \
  -o report.html
```

**Windows (PowerShell)** — `\` am Zeilenende ist bash-Syntax und **funktioniert in PowerShell nicht**
(wird jedes Mal als eigener, fehlerhafter Befehl interpretiert); verwende eine einzige Zeile:

```powershell
pcb-report --gerber board-top-copper.gbr board-bottom-copper.gbr board-outline.gbr board-silkscreen.gbr --bom bom.csv --pnp placement.csv -o report.html
```

Anschließend `report.html` im Browser öffnen.

## CLI-Argumente

| Argument | Erforderlich | Beschreibung |
| --- | --- | --- |
| `VERZEICHNIS` (positional) | nein | Projektordner, der automatisch durchsucht wird (Standard: aktuelles Verzeichnis). Wird ignoriert, wenn Dateien unten explizit angegeben werden. |
| `--gerber DATEI [DATEI ...]` | nein | Gerber-/Excellon-Dateien (RS-274X) — Kupfer, Maske, Bestückungsdruck, Umriss, Bohrungen. Weglassen = automatische Erkennung im `VERZEICHNIS` anhand der Dateiendung. |
| `--bom DATEI` | nein | Stücklistendatei im Format `.csv`, `.xml` oder `.xlsx` (Excel). Weglassen = automatische Erkennung im `VERZEICHNIS`. |
| `--pnp DATEI [DATEI ...]` | nein | Pick-and-Place-Datei(en) `.csv`/`.txt` — mehr als eine, wenn Top/Bottom getrennte Dateien sind (typisch bei Altium). Weglassen = automatische Erkennung im `VERZEICHNIS`. Ohne jede Datei müssen alle Bauteile im Bericht manuell positioniert werden. |
| `--unit {mm,inch}` | nein | Standardeinheit der Koordinaten in der Pick-and-Place-Datei, nur verwendet, wenn der Spaltenname selbst keine Einheit angibt (z. B. nur `X`/`Y` statt `Center-X(mm)`) — siehe unten. |
| `-o, --output DATEI` | nein | Ausgabepfad (Standard: `<VERZEICHNIS>/report.html`). |
| `--report-id ID` | nein | Erzwungener `localStorage`-Schlüssel (Standard: automatisch berechnet aus den Gerber-Dateinamen + der Menge der Bezeichnungen — ermöglicht die erneute Erzeugung des Berichts für dasselbe Projekt, ohne bereits gesetzte Checkboxen zu verlieren). |
| `--all-layers` | nein | Standardmäßig alle Ebenen im Panel „Ebenen“ des Berichts aktivieren (auch Kupfer, Maske, innere Kupferlagen, sonstige mechanische), statt nur der für die Bestückung nötigen, und diese auch bei der automatischen Bestimmung des Anfangs-Zooms/Bildausschnitts der Platine berücksichtigen (siehe Abschnitt „Format der Eingabedateien“). Jede Ebene lässt sich trotzdem direkt im Bericht beliebig umschalten. |
| `--non-interactive` | nein | Im Terminal nicht nach dem Zweck nicht erkannter Dateien fragen (siehe „Wie die automatische Erkennung funktioniert“) — solche Dateien einfach überspringen, wie in Versionen ohne diese Funktion. |

### Wie die automatische Erkennung funktioniert (und wie sie Stückliste von Pick-and-Place unterscheidet)

Durchsucht wird der **gesamte Verzeichnisbaum** unter dem angegebenen `VERZEICHNIS` (beliebige Tiefe,
beliebige Unterordnernamen) — der Ordner „Project Outputs“ von Altium teilt Gerber-/NC-Drill-/BOM-/
Pick-and-Place-Dateien typischerweise in separate Unterordner auf, daher beschränkt sich die
automatische Erkennung nicht auf die oberste Ebene.

Beide Dateiarten (Stückliste und Pick-and-Place) kommen häufig im selben Format vor (`.csv`, bei Altium
Pick-and-Place oft `.txt`) — die Dateiendung allein sagt nichts über den Inhalt aus, daher **öffnet die
automatische Erkennung jeden Kandidaten und prüft die Kopfzeile** der Spalten, statt anhand der Endung
zu raten:

- Enthält ein Paar von Positionsspalten (`Mid X`/`Mid Y`, `Center-X`/`Center-Y`, `PosX`/`PosY`, …) →
  **Pick-and-Place**.
- Enthält eine Designator-/Reference-Spalte, aber kein Paar von Positionsspalten → **Stückliste**.
- Eine `.txt`-Datei, die überhaupt nicht wie eine Tabelle mit Kopfzeile aussieht, wird zusätzlich
  darauf geprüft, ob sie sich als Excellon-Bohrdatei parsen lässt (Altium exportiert Bohrungen oft als
  `.txt` — dieselbe Dateiendung wie Pick-and-Place) — falls ja, landet sie in der Liste der
  Gerber-Dateien, nicht bei BOM/PnP.
- Mehr als eine Datei, die zur Stückliste passt → wird als **Bestückungsvarianten** behandelt (siehe
  unten) statt als Fehler, sofern die Dateinamen dies zulassen; andernfalls muss die richtige über
  `--bom` angegeben werden. Mehrere Pick-and-Place-Dateien, die sich nur durch die Seite (Top/Bottom)
  unterscheiden, werden **zusammengeführt** (typischer Fall getrennter Top-/Bottom-Berichte bei
  Altium); unterscheiden sie sich anders (z. B. ebenfalls Varianten), werden sie den BOM-Varianten
  zugeordnet, statt zusammengeführt zu werden.
- Einheiten (mm/mil/Zoll) in Pick-and-Place-Dateien werden aus dem Spaltennamen selbst gelesen, wenn
  dieser sie enthält (z. B. `Center-X(mil)`) — `--unit` dient nur als Standardwert für Spalten ohne
  angegebene Einheit im Namen (z. B. nur `X`).
- Eine Datei, die sich überhaupt nicht als Stückliste oder Pick-and-Place erkennen lässt (z. B. ein
  Statusbericht in Tabellenform) — wenn das Tool in einem normalen Terminal läuft, **fragt es direkt
  nach**, was diese Datei ist (BOM / Pick-and-Place / überspringen), statt sie stillschweigend zu
  ignorieren. Enter-Taste überspringt die Datei wie bisher. Um diese Fragen zu deaktivieren (z. B. beim
  automatisierten Ausführen des Tools ohne Person am Terminal), `--non-interactive` hinzufügen — dann
  werden nicht erkannte Dateien einfach mit einer Warnung übersprungen, wie es zuvor funktionierte.

## Format der Eingabedateien

- **Stückliste (CSV oder Excel `.xlsx`)** — Kopfzeilen (Groß-/Kleinschreibung wird nicht
  unterschieden): `Designator`/`Reference`/`RefDes`/`Ref Des` (sowie ähnliche Varianten mit Punkten/
  Unterstrichen), `Value`/`Comment` (Altium nennt dieses Feld „Comment“), `Footprint`/`Package`,
  `Description`, `Manufacturer`, `Qty`. Die Spalte mit der Herstellerteilenummer wird breit erkannt —
  `MPN`, `MPN1`/`MPN2` (mehrere zugelassene Hersteller), `Part Number`, `Manufacturer Part Number`,
  `Mfr Part No.`, `P/N`, `Manufacturer P/N` usw. Bei `.xlsx` werden **alle Arbeitsblätter durchsucht**
  (nicht nur das beim Speichern aktive) sowie die ersten ~20 Zeilen jedes Blattes, bis eine Zeile mit
  einer Bezeichnungsspalte gefunden wird — typische firmeneigene BOM-Vorlagen haben vor der eigentlichen
  Tabelle einen Kopf-/Revisionsblock, sodass es nicht immer Zeile 1 von Blatt 1 ist. Gibt es im Projekt
  mehrere Dateien, die wie eine Stückliste aussehen (z. B. `BOM.xlsx`, `BOM_Critical.xlsx`,
  `BOM_NotCritical.xlsx`), meldet die automatische Erkennung dies als Mehrdeutigkeit und bittet um die
  Angabe der richtigen Datei über `--bom`. Das Feld mit den Bezeichnungen kann mehrere Werte auf einmal
  enthalten, z. B. `"R1, R2, R5"` — typisch für Stücklisten, die identische Bauteile in einer Zeile
  gruppieren. Ein Klick auf eine solche Zeile im Bericht hebt **alle** genannten Bezeichnungen
  gleichzeitig in der Platinenvisualisierung hervor.
- **Stückliste (XML)** — der Parser arbeitet heuristisch: Er sucht nach Knoten mit einem Feld vom Typ
  Designator/Reference, da das XML-BOM-Format zwischen CAD-Systemen nicht standardisiert ist. Für mehr
  Zuverlässigkeit wird ein Export nach CSV empfohlen.
- **Pick-and-Place (CSV oder TXT)** — Kopfzeilen: `Designator`/`Ref`, ein Paar Positionsspalten in einer
  der Konventionen `Mid X`/`Mid Y`, `Center-X`/`Center-Y`, `PosX`/`PosY`, `Ref X`/`Ref Y` (optional mit
  Einheit im Namen, z. B. `Center-X(mil)`), `Rotation`, `Layer`/`Side` (`Top`/`Bottom`). Standardexport
  aus KiCad/Altium/Eagle; das Trennzeichen (Komma/Tabulator/Semikolon) wird automatisch erkannt, und
  wenn keines vorhanden ist — wie im eigenen ASCII-Format von KiCad (`Ref  Val  Package  PosX  PosY
  Rot  Side`, Spalten durch Leerzeichen ausgerichtet, ohne Trennzeichen) oder im ASCII-Bericht von
  Altium (`Free Format Pick and Place data`, ebenfalls Spalten durch Leerzeichen ausgerichtet, aber
  Textfelder wie Comment/Description sind zusätzlich in Anführungszeichen gesetzt, da sie selbst
  Leerzeichen und Kommas enthalten können, z. B. `"TERM BLOCK HDR 2POS 3.5MM"`) — werden die Spalten
  anhand beliebiger Folgen von Leerraum getrennt, **unter Berücksichtigung solcher Anführungszeichen**
  (ein Leerzeichen/Komma innerhalb von `"..."` wird nicht als Spaltenende behandelt). Altium fügt vor
  der eigentlichen Kopfzeile oft eine Titel-/Datumszeile ein, und KiCad stellt der Kopfzeile zusätzlich
  ein `#` voran (`# Ref  Val  ...`) — die ersten ~20 nicht-leeren Zeilen der Datei werden durchsucht
  (mit vorübergehend entferntem `#`) auf der Suche nach der Zeile mit Designator+X+Y, sodass keines
  dieser Formate ein Problem darstellt.
  Enthält eine Datei mit Trennzeichen (z. B. Komma) eine Zeile mit einem Bauteil, dessen Feld
  Comment/Value/Description selbst dieses Zeichen ohne Anführungszeichen enthält (z. B. `GSM MODULE,
  802.11 b/g/n`), hat diese Zeile mehr Felder als die Kopfzeile — die Spalten X/Y „verrutschen“, und
  ohne Behandlung dieses Falls würden sinnlose Werte (Beschreibungsfragmente statt Zahlen) in den
  Bericht gelangen. Das Tool erkennt diese Situation allein an der Feldanzahl und fügt die
  überzähligen Fragmente automatisch wieder zur Spalte Comment/Value/Description zusammen, wodurch die
  restlichen Spalten dieser Zeile wieder korrekt ausgerichtet werden — die Konsole gibt eine Warnung
  mit der Anzahl der reparierten Zeilen aus, es lohnt sich aber, dies im Bericht optisch zu prüfen. Die
  Reparatur funktioniert nur, wenn die Datei überhaupt eine solche Spalte in der Kopfzeile hat;
  andernfalls wird die Zeile mit einer Warnung übersprungen, die auf die wahrscheinliche Ursache
  hinweist.
- **Gerber** — ein beliebiger Satz von RS-274X-Dateien (Kupfer, Maske, Bestückungsdruck, Lotpaste,
  Courtyard, Umriss) und optional Excellon (Bohrungen). Enthält eine Datei das Standard-Gerber-X2-
  Attribut `%TF.FileFunction,...*%` (Standard im neueren Export von Altium/KiCad), werden Ebenentyp
  und Seite direkt daraus gelesen — der Dateiname spielt dann keine Rolle. Andernfalls (älteres,
  Vor-X2-RS-274X, häufig bei älteren Altium-Exporten) wird aus dem Dateinamen geraten: erkannt werden
  die KiCad-Konventionen (`*.gtl/.gbl/…` sowie `*-F.Cu.gbr/-B.Cu.gbr/…`, `*-In1.Cu.gbr/…` für
  Innenlagen), Altium (`.G1`/`.G2`/… = Innenlagen-Kupfer, `.GKO`/`.GML`/`GM1` = Umriss, `GM13`/`GM14` =
  Courtyard oben/unten, `GM15`/`GM16` = Fertigung, übrige `.GM<Nummer>` = sonstige mechanische Ebene
  mit aus dem Namen nicht erkennbarem Zweck) sowie typische Schlüsselwörter (`top`/`bottom`/`copper`/
  `mask`/`silk`/`paste`/`outline`/`edge`/`courtyard`/`inner`). Eine Datei mit gar nicht erkennbarem
  Namen wird trotzdem gerendert (in neutraler Farbe, auf beiden Seiten der Platine angezeigt) — siehe
  „Bekannte Einschränkungen“.
  Silkscreen-Zeichen mit einem „Loch“ (z. B. `0`, `R`, `8`, `Q`), die als gefüllte Vektor-Umrissregionen
  einer TrueType-Schrift exportiert wurden (typisch bei Altium/KiCad), werden mit einem echt
  ausgeschnittenen Loch gerendert (SVG-Maske, die die „clear“-Polarität aus der Gerber-Datei
  widerspiegelt), statt als vollständig ausgefüllte Form zu erscheinen — dies betrifft nur Dateien, die
  tatsächlich solche Geometrie verwenden; die übrigen werden ohne zusätzlichen Mehraufwand gerendert.

  **Standardmäßig sichtbar sind nur die für die Bestückung nötigen Ebenen: Umriss, Silkscreen,
  Lotpaste, Courtyard und Bohrungen.** Kupfer (außen und innen), Lötstoppmaske sowie sonstige, nicht
  erkannte mechanische Ebenen von Altium (`.GM<Nummer>` außerhalb von Umriss/Courtyard) werden geladen
  und sind verfügbar, aber standardmäßig abgewählt — sie werden für die reine Bestückung nicht benötigt
  und würden die Ansicht nur zumüllen (Kupfer ist auf den ersten Blick oft dicht/unübersichtlich,
  mechanische Ebenen sind meist Fertigungsdokumentation, nicht die Platine selbst). Silkscreen und
  Courtyard haben zusätzlich **je eine eigene Farbe für oben und unten** (damit man sie auf einen Blick
  unterscheiden kann, da beide Seiten gemeinsam in der Liste erscheinen), die übrigen Typen haben eigene,
  feste Farben (siehe Legende im Panel „Ebenen“). Die reine Platinenansicht zeigt nur aktivierte Ebenen,
  die zur aktuell gewählten Seite (Oben/Unten) passen oder als für beide Seiten gemeinsam markiert sind.

  **Das ist nur eine Standardeinstellung, kein harter Filter** — die Klassifizierung der Ebenen beruht
  auf einer Heuristik (Dateiname oder X2-Attribut), kann sich also bei einem untypischen Projekt irren.
  Im Bericht, oben rechts in der Platinenansicht, gibt es die Schaltfläche **„Ebenen“**, die ein Panel
  mit der Liste *jeder* geladenen Gerber-Datei einzeln öffnet (Name, Typ, Seite, Farbe) mit Checkbox —
  jede Ebene lässt sich beliebig ein- oder ausschalten, ohne das Tool erneut auszuführen; die Auswahl
  wird wie der übrige Status gespeichert (localStorage + Export/Import).

  Das Flag `--all-layers` aktiviert sofort alle Ebenen (statt nur der für die Bestückung nötigen) und
  erweitert außerdem die Dateiauswahl für die automatische Bestimmung des Anfangs-Zooms/Bildausschnitts
  der Platine — nützlich, wenn Maske/innere Kupferlage/eine sonstige mechanische Ebene über den Umriss
  der Platine hinausragt und für den Bildausschnitt relevant ist.

## Zuordnung von Stücklisten-Bauteilen → PCB-Visualisierung

1. **Mit Pick-and-Place-Daten** — jeder `designator` aus der Stückliste wird automatisch auf eine
   Position (x, y, Rotation, Seite) aus der PnP-Datei abgebildet.
2. **Ohne Positionsdaten (oder ohne passende Bezeichnung in der PnP-Datei)** — im erzeugten Bericht ist
   die Bezeichnung orange hervorgehoben, mit der Unterschrift *„Keine Position“* darunter. Klicke auf
   die Bezeichnung selbst (nicht nur bei fehlenden — **bei jeder**, auch bereits platzierten), und dann
   auf die Platinenvisualisierung, um ihre Koordinaten manuell zuzuweisen/zu korrigieren. Das
   funktioniert zu 100 % im Browser, nach dem Erzeugen der Datei — nichts muss neu berechnet oder das
   Tool erneut ausgeführt werden. Das ist nicht nur bei fehlenden Positionen nützlich, sondern auch, um
   ein einzelnes Bauteil zu korrigieren, dessen Position aus der Pick-and-Place-Datei sich als falsch
   herausgestellt hat.
3. Standardmäßig hat jedes platzierte Bauteil eine sichtbare **Pin-1-Markierung** (gelber Punkt, vom
   Mittelpunkt aus entsprechend der Bauteilrotation versetzt).
4. Das Panel **„Eingabedaten“** (Liste der Gerber-Dateien und Warnungen) ist standardmäßig eingeklappt —
   auf die Überschrift klicken, um es auf-/zuzuklappen, genau wie das Panel **„Ebenen“**.
5. Die Visualisierung zeigt **nur Bauteile der aktuellen Seite** (Oben/Unten) — ein auf der Unterseite
   platziertes Bauteil wird gar nicht erst gezeichnet, wenn die Ansicht auf „Oben“ steht, und
   umgekehrt. Die Auswahl eines Bauteils (oder einer Gruppe) in der Liste links hebt an den
   Schaltflächen **Oben/Unten** (rote Umrandung, unabhängig davon, welche gerade als Ansicht gewählt
   ist) hervor, auf welcher Seite bzw. welchen Seiten es sich tatsächlich befindet — eine Gruppe mit
   Bauteilen auf beiden Seiten hebt beide Schaltflächen hervor. Das manuelle Setzen der Position (siehe
   Punkt 2 oben) weist dem Bauteil die Seite zu, auf die die Ansicht im Moment des Klicks auf die
   Platine gerade eingestellt ist.
6. Die Markierungen in der Visualisierung sind klein (ein kleines Quadrat, bei einer echten
   Formzuordnung der tatsächliche Footprint-Umriss) statt großer, gefüllter Kreise — bei einer dicht
   bestückten Platine würden große Kreise benachbarte Bauteile und den Silkscreen selbst verdecken. Ein
   ausgewähltes Bauteil erhält zusätzlich ein kleines rotes Rechteck um die Markierung. Ein Klick auf
   eine Markierung in der Visualisierung wählt sie auch in der Liste links aus und scrollt die Liste
   so, dass diese Zeile sichtbar wird (nützlich bei einer langen Bauteilliste).

## Gruppierung und Mengenverfolgung (Geliefert / Bestückt)

Die Bauteilliste ist immer natürlich nach Bezeichnung sortiert (R1, R2, R3, R10, C1… statt
alphabetisch R1, R10, R2). Die Checkbox **„Nach Bauteil gruppieren (MPN)“** in der Assembly-Seitenleiste
schaltet die Ansicht um:

- **Gruppiert (Standard)** — Zeilen werden nach MPN zusammengefasst (fehlt diese, nach Wert+Footprint),
  unabhängig davon, wie sie in der ursprünglichen Stücklistendatei gruppiert waren. Jede Zeile hat ein
  editierbares Feld **„Benötigt“** (Standard = Anzahl der Positionen/Bezeichnungen **mal Anzahl zu
  bestückender Platinen**, wenn diese gesetzt ist — siehe Abschnitt "Produktionsplanung" unten; ohne
  sie funktioniert es wie bisher, lässt sich aber immer manuell überschreiben, z. B. um einen Vorrat
  einzurechnen), das Feld **„Bestellt“** (wie viel tatsächlich beim Lieferanten bestellt wurde — für
  die gesamte Charge), das Feld **„Geliefert“** (für die gesamte Charge) sowie das Feld **„Bestückt“**
  (für die **aktuell ausgewählte Platine** — siehe unten) — Zahlen, die manuell eingegeben oder per
  Schaltfläche **„Alles“** gesetzt werden (setzt den Wert = Benötigt, bei Bestückt = Benötigt pro
  Platine). Die Fehlmenge wird automatisch berechnet und ist sowohl in der Zeile als auch im
  zusammenfassenden Panel **„Fehlmengen“** unten auf der Assembly-Seite sichtbar.
- **Flach (ohne Gruppierung)** — jede Bezeichnung als eigene Zeile, zum schnellen Auffinden einer
  einzelnen Position auf der Platine; zeigt den Mengenstatus der gesamten Gruppe, zu der sie gehört, an,
  erlaubt aber keine Bearbeitung der Zahlen (das Bearbeiten ist nur in der gruppierten Ansicht möglich).

Ein Klick auf eine Zeile (oder eine Markierung auf der Platine) in der **gruppierten** Ansicht hebt auf
der Platine **alle** Bezeichnungen des jeweiligen Bauteils gleichzeitig hervor. In der **flachen**
Ansicht wird nur die ausgewählte, einzelne Bezeichnung hervorgehoben.

Da der Status auf Bauteilebene berechnet wird (nicht auf Ebene einer einzelnen Bezeichnung — das Tool
weiß nicht, *welches konkrete* Exemplar geliefert/bestückt wurde), spiegelt die Farbe der Markierung auf
der Platine die Schwelle der gesamten Gruppe wider: grau = nichts, gelb = teilweise/vollständig
geliefert, grün = teilweise/vollständig bestückt (hellerer Farbton = teilweise, voll = vollständig;
Bestückung hat beim Einfärben Vorrang vor der Lieferung).

## Bestückungsvarianten (Critical / NotCritical / … )

Altium (und andere Tools) erlauben die Definition von **Projektvarianten** — unterschiedliche
Bestückungskonfigurationen derselben Platine (z. B. „Critical“ = nur kritische Bauteile für die erste
Bestückung, „NotCritical“ = der Rest, „Full“/Standard = alles) — und exportieren dafür eine eigene
Stücklistendatei (oft auch eine eigene Pick-and-Place-Datei) pro Variante. GerbertoHTML erkennt das
automatisch:

- Findet die automatische Erkennung **mehrere Dateien, die wie eine Stückliste aussehen**, für dasselbe
  Projekt, behandelt sie statt eines Fehlers als Varianten. Die Variantenbezeichnung ist der Teil des
  Dateinamens, der sie voneinander unterscheidet (z. B. `Board.xlsx` / `Board_Critical.xlsx` /
  `Board_NotCritical.xlsx` → Varianten „Podstawowy“ (Standard) / „Critical“ / „NotCritical“).
- Analog für mehrere Pick-and-Place-Dateien, sofern sie nicht wie eine gewöhnliche Top-/Bottom-Aufteilung
  aussehen (dann werden sie weiterhin wie bisher zusammengeführt) — jede wird der Stücklistenvariante
  mit demselben oder einem ähnlichen Namen zugeordnet. Fehlt die Namenszuordnung für genau eine
  Stücklistenvariante und genau eine Pick-and-Place-Datei, werden sie als letzte Möglichkeit gepaart.
  Für Varianten, die sich weiterhin nicht anhand des Namens zuordnen lassen (z. B. wenn sich die
  Dateinamen von Stückliste und Pick-and-Place überhaupt nicht ähneln), prüft das Tool den
  **tatsächlichen Inhalt** — wie viele Bezeichnungen (Designators) der jeweiligen Stücklistenvariante
  tatsächlich in jeder verbleibenden Pick-and-Place-Datei vorkommen — und ordnet automatisch zu, wenn
  eine Datei durch diese Übereinstimmung eindeutig gewinnt. Ist auch das mehrdeutig (Gleichstand oder
  kein klarer Vorsprung) und läuft das Tool in einem normalen Terminal, **fragt es direkt nach**,
  welche Pick-and-Place-Datei zu welcher Variante passt (mit dem angezeigten Prozentsatz der
  Bezeichnungs-Übereinstimmung für jeden Kandidaten) — die Eingabetaste überspringt die Zuordnung für
  diese Variante. Ohne Antwort (z. B. bei `--non-interactive` oder Ausführung ohne Terminal) erfordert
  eine nicht zugeordnete Variante einfach die manuelle Positionierung der Bauteile im Bericht (wie beim
  vollständigen Fehlen von Pick-and-Place-Daten).
- In der Konsole erscheint eine Warnung mit der Liste der erkannten Varianten und dem Ergebnis der
  Pick-and-Place-Zuordnung — es lohnt sich, dies zu prüfen, besonders wenn die Variantennamen nicht
  eindeutig sind (z. B. kann eine separate „Mechanical BOM“ mit mechanischem Zubehör, die keine echte
  Bestückungsvariante ist, hier ebenfalls aufgeführt werden, wenn der Dateiname darauf hindeutet).

Im erzeugten Bericht erscheint, wenn mehr als eine Variante erkannt wurde, in der Assembly-Seitenleiste
eine Auswahlliste **„Bestückungsvariante“**. Ihr Umschalten:

- Ersetzt die Bauteilliste, die Summen und das Fehlmengen-Panel durch die Daten der gewählten Variante.
- Zeigt in der Platinenvisualisierung nur die Markierungen der Bauteile, die zu dieser Variante gehören
  (der Rest der Platine — Umriss, Kupfer, Silkscreen — ist für jede Variante identisch, da es sich
  weiterhin um dieselbe physische Platine handelt).
- Verfolgt Geliefert/Bestückt **getrennt für jede Variante** — das Abhaken von etwas in der Variante
  „Critical“ wirkt sich nicht auf den Fortschritt in „NotCritical“ aus. Manuell auf der Platine
  gesetzte Bauteilpositionen sind dagegen für alle Varianten gemeinsam (es ist weiterhin derselbe
  physische Punkt auf der Platine).
- Export/Import des Status (siehe oben) überträgt den Fortschritt **aller** Varianten auf einmal, sodass
  die Weitergabe der Statusdatei an eine andere Person unabhängig davon, welche Variante gerade
  geöffnet war, keine Daten verliert.

Wurde nur eine Stückliste erkannt (der typische Fall), ist die Variantenliste ausgeblendet, und am
bisherigen Verhalten ändert sich nichts.

## Produktionsplanung (Projektnummer, Stückzahl, Bestückung pro Platine)

In der Assembly-Seitenleiste, unter der Variantenauswahl, gibt es ein Panel **„Projektnummer“** /
**„Anzahl zu bestückender Platinen“** — zwei einfache, immer verfügbare Felder. Werden beide
ausgefüllt, aktiviert das eine zusätzliche Verfolgung, unabhängig für jede Bestückungsvariante (gibt
es Varianten, hat jede ihre eigene Projektnummer und eigene Stückzahl, getrennt einstellbar):

- **Anzahl zu bestückender Platinen** multipliziert das Feld **„Benötigt“** jedes Bauteils mit dieser
  Zahl (z. B. ein Widerstand wird 2× pro Platine benötigt, bei 10 zu bauenden Stück → Benötigt = 20)
  — das ist die Menge für die **gesamte Produktionscharge**, zum Vergleich mit dem, was tatsächlich
  bestellt/geliefert wurde.
- Ist die Stückzahl größer als 1, erscheint unter diesen Feldern eine Auswahlliste **„Aktuell
  bestückte Platine“** (z. B. `P2024-118_001`, `P2024-118_002`, …). Das Feld **„Bestückt“** in der
  Bauteilliste bezieht sich immer auf **genau diese eine, ausgewählte Platine** — jede physische
  Platine hat ihre eigene, unabhängige Bestückungscheckliste (die Spaltenüberschrift zeigt, auf welche
  Platine sie sich bezieht). Die Zusammenfassung oben in der Seitenleiste und das Panel „Fehlmengen“
  zeigen die **Summe aller bestückten Teile über alle Platinen hinweg**, geben also einen Gesamtüberblick
  über den Fortschritt der ganzen Charge.
- **Bestellt** und **Geliefert** werden für die gesamte Charge auf einmal geführt (Bauteile werden
  typischerweise für alle Platinen zusammen bestellt/angenommen, nicht einzeln pro Platine). Sobald das
  Feld „Bestellt“ für ein Bauteil verwendet wird, zeigt das Panel „Fehlmengen“ zusätzlich **„aus
  Bestellung nicht angekommen: N“**, wenn die gelieferte Menge kleiner ist als die bestellte — genau
  das beantwortet die Frage "ist die bestellte Menge an Bauteilen tatsächlich angekommen".
- Sind beide Felder (Projektnummer und Stückzahl) ausgefüllt, erscheinen im Reiter **Traceability**
  automatisch Muster mit den Namen `PROJEKTNUMMER_001`, `PROJEKTNUMMER_002`, … bis zur eingestellten
  Stückzahl (Nummerierung mit führenden Nullen, Breite passend zur Stückzahl). Das funktioniert nur in
  eine Richtung — eine Verringerung der Stückzahl oder eine Änderung der Projektnummer **löscht oder
  benennt niemals** bereits vorhandene Muster um (damit nicht versehentlich jemandes Notizen/Nacharbeiten
  verloren gehen); es werden nur die fehlenden erzeugt.
- Ohne Ausfüllen dieser Felder funktioniert das Tool genau wie bisher (eine einzige, implizite
  „Platine“, Benötigt = Wert aus der Stückliste, keine Auswahlliste für Platinen) — diese Funktion ist
  vollständig optional.

## Fotos bei Nacharbeiten (Traceability)

Jeder Eintrag im **gemeinsamen Nacharbeits-Pool** (links im Traceability-Reiter, siehe Abschnitt
„Gruppierung...“ oben) hat einen Fotobereich: die Schaltfläche **„📷 Foto hinzufügen“** öffnet die
Dateiauswahl (mehrere Dateien auf einmal möglich), und hinzugefügte Fotos erscheinen als
Miniaturansichten nebeneinander. Ein Klick auf die Miniaturansicht öffnet das Foto in voller Größe
(Lightbox); eine kleine „✕“-Schaltfläche auf der Miniaturansicht entfernt das Foto. Da der
Nacharbeits-Pool für alle Muster gemeinsam ist, ist ein an eine Nacharbeit angehängtes Foto (z. B. ein
Bild, das zeigt, wie diese Reparatur aussieht) bei dieser Nacharbeit sichtbar, unabhängig davon, bei
wie vielen Mustern sie als durchgeführt markiert wird.

- Fotos werden **im Browser skaliert und komprimiert**, bevor sie gespeichert werden (max. 1280 px auf
  der längeren Seite, JPEG-Qualität ca. 72 %) — ein typisches Handyfoto (mehrere MB) landet als
  einige Dutzend bis einige Hundert KB im Status. Das geschieht lokal, ohne dass etwas nach außen
  gesendet wird.
- Fotos sind Teil des Nacharbeits-Status und unterliegen denselben Regeln wie der Rest: Sie werden im
  `localStorage` gespeichert und beim Export/Import der Statusdatei (siehe oben) zusammen mit den
  übrigen Daten übertragen. **Das bedeutet aber, dass die exportierte Statusdatei bei vielen Fotos
  nicht mehr „klein“ ist** — ein Dutzend Fotos auf mehreren Nacharbeiten kann bereits mehrere MB
  ergeben, was beim Versenden der Statusdatei per E-Mail zu beachten ist (SharePoint/Netzlaufwerk/USB-Stick
  kommen damit problemlos zurecht).
- Der `localStorage` des Browsers hat eine begrenzte Größe (typisch 5–10 MB pro Origin) — schlägt das
  Speichern fehl (z. B. zu viele Fotos), erscheint unten auf der Seite ein rotes Warnbanner, statt
  stillschweigend Daten zu verlieren; die Lösung ist, einige Fotos zu entfernen oder den Status in
  eine Datei zu exportieren, bevor der Browser geschlossen wird.

## Softwareversionen (Traceability)

Auf der linken Seite des Traceability-Tabs, unterhalb der gemeinsamen Nacharbeitsliste, gibt es ein
eigenes Panel **„Softwareversionen“**: ein Formular mit Name/Nummer der Version (z. B. „Firmware
v1.4.2“) und einem optionalen Download-Link, sowie eine Liste der bereits hinzugefügten Versionen.
Genau wie die Nacharbeitsliste ist diese Liste **für den ganzen Bericht gemeinsam** — sie wird einmal
angelegt und dann einzelnen Mustern zugeordnet.

- Jedes Muster hat jetzt ein Feld **„Software“** — eine Dropdown-Liste mit allen im gemeinsamen Panel
  hinzugefügten Versionen (plus die Option „— keine —“). Die Auswahl hält fest, welche Softwareversion
  auf diesem Muster aufgespielt/getestet wurde.
- Hat eine Version einen Link, ist dieser **klickbar** — sowohl bei ihrem Eintrag in der gemeinsamen
  Liste (der Versionsname selbst ist ein Link) als auch beim Muster, dem sie zugeordnet ist (Schaltfläche
  „Herunterladen“ neben der Dropdown-Liste) — er öffnet sich in einem neuen Tab, sodass das Herunterladen
  der aktuellen Firmware nicht erst woanders gesucht werden muss.
- Aus Sicherheitsgründen werden nur Adressen, die mit `http://` oder `https://` beginnen, als Link
  dargestellt — das betrifft insbesondere den Import einer Statusdatei von einer anderen Person (siehe
  Abschnitt „Export/Import des Status“ oben), bei der ein Link theoretisch präpariert sein könnte.
- Wird eine Version aus der gemeinsamen Liste entfernt, wird auch ihre Zuordnung bei allen Mustern
  gelöscht, die sie ausgewählt hatten (die Muster selbst samt Notizen/Nacharbeiten bleiben erhalten).
- Die Versionsliste wird genau wie der übrige Status gespeichert (`localStorage` + Export/Import der
  Statusdatei).

## Architektur und Begründung der Werkzeugwahl

| Element | Wahl | Begründung |
| --- | --- | --- |
| Oberfläche / Logik | **Python 3** — `csv`, `xml.etree.ElementTree`, `argparse`, `json` aus der Standardbibliothek, plus zwei Pip-Abhängigkeiten (`gerbonara`, `openpyxl`) | minimale Anzahl an Abhängigkeiten; die Installation ist ein einziger Befehl (`pip install -e .`), ohne Node.js/npm |
| Gerber-→-SVG-Rendering | [`gerbonara`](https://gitlab.com/gerbolyze/gerbonara) — ein reiner Python-Parser für RS-274X/Excellon | RS-274X-Dateien (Bögen, Aperturen, Makros) von Grund auf zu parsen wäre ein großer, riskanter Aufwand gewesen. Der erste Versuch (`pcb-tools`) ließ sich nicht installieren (defekte native Abhängigkeiten, cairocffi). `gerbonara` installiert sich mit reinem `pip` und rendert die Geometrie **einer einzelnen Datei** zu SVG ohne jede Anforderung an Benennung oder Vollständigkeit des Satzes — seine High-Level-API (`LayerStack`) benötigt einen vollständigen, konventionell benannten Satz von Fertigungsdateien, daher rendert `pcb_report/gerber.py` jede Datei einzeln und **setzt sie selbst** zu einem Bild zusammen (siehe unten), wodurch Toleranz gegenüber jedem beliebigen, unvollständigen Dateisatz erhalten bleibt |
| Ausgabe | **Eine einzige statische HTML-Datei** (CSS + JS + BOM-/Placement-/SVG-Daten in einer Datei, ohne externe Ressourcen) | lässt sich sofort im Browser öffnen, versenden, archivieren — ohne Server-Hosting |
| Interaktivität im Browser | Reines JavaScript (ohne Frameworks), das auf nativem `<svg>` arbeitet | die Platinenvisualisierung und die Bauteilmarkierungen liegen im selben `viewBox`-Koordinatensystem (mm) wie die Pick-and-Place-Daten, sodass Zoom/Verschieben (CSS-Transformation) und Auswahl (CSS-Klassen) keine zusätzlichen Umrechnungen oder Bibliotheken benötigen |
| Persistenz des Status | `localStorage` des Browsers, Schlüssel = Bericht-ID (Hash aus den Gerber-Dateinamen + der Menge der Bezeichnungen) | ermöglicht das Erhalten von Checkboxen/Mustern/Nacharbeiten zwischen Öffnungen desselben Berichts, ohne Backend und Datenbank |

### Wie die Zusammensetzung mehrerer Gerber-Dateien zu einem Bild funktioniert

`pcb_report/gerber.py` parst jede Datei einzeln über `gerbonara.rs274x.GerberFile`/
`gerbonara.excellon.ExcellonFile`, nimmt deren Geometrie (SVG) und Bounding Box und dann:

1. Bestimmt den Ebenentyp (Kupfer/Maske/Bestückungsdruck/Lotpaste/Courtyard/Umriss/Bohrungen) und die
   Seite (oben/unten/beide). Enthält die Datei das Standard-Gerber-X2-Attribut
   `%TF.FileFunction,...*%` (so exportieren Altium und KiCad standardmäßig), wird dieses genutzt — ein
   zuverlässiger, vom Dateinamen unabhängiger Weg. Andernfalls (älteres RS-274X ohne X2-Attribute) wird
   aus dem Dateinamen geraten (einfache Heuristik, siehe `_classify_from_attrs`/`_classify_type`/
   `_classify_side` im Code).
2. Berechnet die gemeinsame Bounding Box (Vereinigung) der standardmäßig sichtbaren Dateien (siehe
   „Format der Eingabedateien“) — das wird zur `viewBox` des gesamten SVG, damit standardmäßig
   ausgeblendete Ebenen (z. B. Dutzende unbekannter mechanischer Dateien mit großer Ausdehnung) den
   Ausgaberahmen nicht verzerren.
3. Jede Datei gelangt als separate, unabhängig umschaltbare Ebene (`GerberLayer`) in das Panel „Ebenen“
   im Bericht (siehe „Format der Eingabedateien“ oben), in der Zeichenreihenfolge Kupfer → Maske →
   Lotpaste → Courtyard → Bestückungsdruck → Umriss → Bohrungen, jede in eigener Farbe und
   Transparenz.
5. Wurden Pick-and-Place-Daten angegeben, wird versucht, jeder Bezeichnung ihren echten Umriss aus dem
   Courtyard oder (falls kein Courtyard vorhanden) dem Silkscreen zuzuordnen, statt eine generische
   Markierung zu zeichnen — siehe unten „Zuordnung echter Bauteilumrisse“.

Dadurch rendert das Tool ein sinnvolles Platinenbild unabhängig davon, ob nur 2 Dateien oder ein
vollständiger Fertigungssatz vorliegen — auf Kosten eines etwas vereinfachten (nicht vollständig
fotorealistischen) Aussehens im Vergleich zu dedizierten Tools wie KiCad/gerbv.

### Zuordnung echter Bauteilumrisse

Die Inspiration war das Plugin [InteractiveHtmlBom](https://github.com/openscopeproject/InteractiveHtmlBom)
für KiCad, das in der Visualisierung echte Footprint-Formen zeichnet — mit dem Unterschied, dass
GerbertoHTML keinen Zugriff auf die Platinendatei (`.kicad_pcb`/`PcbDoc`) hat, sondern nur auf die
Gerber-Dateien selbst, sodass die Formen aus der Geometrie der Courtyard-/Silkscreen-Ebene
rekonstruiert werden müssen:

1. Für jede Seite der Platine wird die Geometrie der Courtyard-Ebene genommen (bevorzugt — meist ein
   Rechteck des Bauteilumrisses) oder, falls diese fehlt, des Silkscreens.
2. Benachbarte Primitiven (Linien/Bögen/Flashes) werden mit dem Union-Find-Algorithmus anhand der
   Überlappung ihrer Bounding Boxes (mit kleinem Rand) zu Clustern gruppiert — jeder Cluster ist ein
   Kandidat für den Umriss eines Bauteils.
3. Die Cluster werden den Bezeichnungen aus den Pick-and-Place-Daten per Methode des nächsten Nachbarn
   zugeordnet (nach den Koordinaten des Mittelpunkts); jeder Cluster und jede Bezeichnung kann nur
   einmal zugeordnet werden, innerhalb eines durch die Diagonale des Clusters begrenzten Radius.
4. Bezeichnungen, für die kein passender Cluster gefunden wurde (weil z. B. Courtyard/Silkscreen keine
   Geometrie dafür enthält oder die Geometrie zu weit entfernt/zu groß ist), erhalten eine gewöhnliche
   generische Markierung (Kreis) — wie bisher.

Diese Zuordnung ist heuristisch und „best effort“ — bei typischen Platinen mit vollständigem Courtyard
funktioniert sie gut, ist aber nicht für jede Platine garantiert (dicht gepackte Bauteile, fehlender
Courtyard, nicht standardmäßige Fertigungsebenen). Die Anzahl der zugeordneten Bauteile gibt das Tool
nach der Erzeugung des Berichts in der Konsole aus.

## Projektstruktur

```
pcb_report/
  cli.py                 # argparse-CLI: VERZEICHNIS --gerber --bom --pnp --unit -o
  discovery.py           # automatische Erkennung von Gerber/BOM/Pick-and-Place im Projektordner
  models.py              # Dataclasses: BomComponent, Placement, ViewBox, GerberRenderResult
  bom.py                 # BOM-Parser: CSV/XLSX (stdlib csv + openpyxl) + XML (stdlib ElementTree)
  placement.py           # Pick-and-Place-Parser CSV/TXT, automatische Erkennung von Trennzeichen und Einheiten
  gerber.py              # gerbonara: Parsen + Zusammensetzen mehrerer Gerber-Dateien -> ein SVG
  report.py              # setzt die endgültige, eigenständige HTML-Datei zusammen (CSS + JS + Daten in einer Datei)
  assets/
    report.css            # Design: Weiß / Blau / Marineblau / Grautöne
    report.js             # gesamte Logik im Browser: Reiter, Zoom/Verschieben, Auswahl, Traceability
examples/minimal/          # kleiner Testdatensatz + fertige Skripte run_example.ps1 / .sh
```

## Bekannte Einschränkungen

- Der XML-BOM-Parser arbeitet heuristisch — für mehr Zuverlässigkeit wird ein Export nach CSV empfohlen.
- Die Erkennung von Ebenentyp/Seite bei Gerber-Dateien nutzt das X2-Attribut
  `%TF.FileFunction,...*%`, wenn die Datei es enthält (typisch beim Export aus Altium/KiCad) — dann
  spielt der Dateiname keine Rolle. Bei Dateien ohne dieses Attribut (älteres RS-274X) basiert die
  Klassifizierung auf dem Dateinamen (einfache Heuristik) — untypische Namenskonventionen können dann
  falsch klassifiziert werden (die Datei wird trotzdem gerendert, nur in neutraler Farbe und auf
  beiden Seiten der Platine, und wird eventuell nicht herausgefiltert, obwohl es sich um Kupfer/Maske
  handelt; eine entsprechende Warnung erscheint im Bericht).
- Die Zusammensetzung mehrerer Ebenen ist vereinfacht (feste Farben/Transparenz je Ebenentyp, ohne
  echte Maskierung des Kupfers durch die Lötstoppmaske) — ausreichend für Referenzzwecke bei der
  Bestückung, ersetzt aber nicht einen dedizierten Gerber-Betrachter (z. B. gerbv, KiCad) zur
  Fertigungsprüfung.
- Die Bauteilmarkierung in der Visualisierung zeigt den echten Umriss aus Courtyard/Silkscreen, wenn
  eine Zuordnung gelingt (siehe „Zuordnung echter Bauteilumrisse“ oben); in den übrigen Fällen (fehlende
  Geometrie, zu dichte Packung, fehlende Pick-and-Place-Daten) wird eine generische Markierung
  verwendet — ein festes Rechteck plus Pin-1-Markierung entsprechend der Rotation.
- `localStorage` ist an den Ursprung (Origin) des Browsers gebunden — in manchen Konfigurationen kann
  das Öffnen von `file://`-Dateien mit restriktiven Datenschutzeinstellungen das Speichern des Status
  einschränken; in der Standardkonfiguration von Chrome/Firefox/Edge funktioniert dies korrekt
  (verifiziert).
