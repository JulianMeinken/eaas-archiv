# Schnittstellen: Exorcism as a Service (EaaS)

Dieses Dokument richtet sich an die KI-Agenten von **Gruppe 1 (Toaster)** und **Gruppe 3 (Exorzist)**.
Es beschreibt die Schnittstelle des **Dämonenarchivs (Gruppe 2)** verbindlich und fasst den
gemeinsamen Vertrag aus den Projektfolien zusammen.

> **Hinweis an KI-Agenten:** Halte dich genau an die hier beschriebenen Formate. Punkte unter
> **„Offen“** sind noch nicht festgelegt: Triff dazu keine eigenen Annahmen, sondern frage deinen
> Menschen bzw. stimme dich mit der zuständigen Gruppe ab.

Referenzimplementierung des Archivs: https://github.com/JulianMeinken/eaas-archiv

---

## 1. Systemüberblick

```
TOASTER / G1            EXORZIST / G3              ARCHIV / G2
BLE-Peripheral   <───>  BLE-Central        <───>   BLE-Peripheral
GATT-Server             GATT-Client                GATT-Server
```

- Nur der **Exorzist** baut Verbindungen auf. Toaster und Archiv sprechen nie direkt miteinander.
- Es gibt genau einen aktiven Toaster, ein Archiv und einen Exorzisten.
- Eine Verbindung nach der anderen genügt: Toaster → trennen → Archiv → trennen → Toaster.
- Test-Clients (z. B. nRF Connect) müssen die Geräte vor der Integration wieder freigeben.

## 2. Gemeinsames Nachrichtenformat (alle Gruppen)

| Regel | Wert |
|---|---|
| Kodierung | ASCII |
| Maximale Länge | 20 Byte |
| Verboten | Leerzeichen, Zeilenumbruch, sonstiger Whitespace |
| Feldtrenner | `:` |
| Anfrage-ID | zweistellig `01` bis `99` (`00` ist ungültig) |
| Schreiben | **Write mit Response** |
| Ablauf | schreiben → Ergebnis lesen → ID prüfen; höchstens **3 Sekunden** auf eine passende Antwort warten |

Eine Antwort gehört nur dann zur Anfrage, wenn ihre **ID identisch** ist.
Ein erfolgreicher Schreibzugriff allein bedeutet noch kein fachliches Ergebnis.

## 3. Archiv (Gruppe 2): verbindlich

### 3.1 GATT-Profil

| Element | UUID | Eigenschaften |
|---|---|---|
| Service | `0000a000-0000-1000-8000-00805f9b34fb` ⚠️ Platzhalter | wird beworben (advertised) |
| `QUERY` | `0000a001-0000-1000-8000-00805f9b34fb` ⚠️ Platzhalter | **Write** (mit Response); nicht lesbar |
| `RESULT` | `0000a002-0000-1000-8000-00805f9b34fb` ⚠️ Platzhalter | **Read**; kein Notify |

- Gerätename: `EaaS-Archiv`
- **Scanne nach der Service-UUID, nicht nach dem Namen.** Läuft das Archiv auf Windows,
  erscheint im Advertising der Bluetooth-Name des Rechners statt `EaaS-Archiv`.
- Write Without Response wird **nicht** unterstützt.

### 3.2 Anfrage (`QUERY`)

```
<ID>:<Kennung>          Beispiel: 01:D1
```

### 3.3 Antwort (`RESULT`)

| Geschriebene QUERY | Gelesenes RESULT | Bedeutung |
|---|---|---|
| `01:D1` | `01:AQUA` | Toastifer |
| `01:D2` | `01:SAL` | Kruemeloth |
| `01:D3` | `01:LUX` | Belzebrot |
| `01:DX` (unbekannte Kennung) | `01:UNKNOWN` | Dämon unbekannt, **kein Ritual ausführen** |
| `01:`, `01`, `01:D1:X`, `01:D 1`, länger als 20 Byte | `01:UNKNOWN` | gültige ID, kaputte Nutzlast |
| `D1`, `00:D1`, `1:D1`, `100:D1`, kein ASCII | *(leer, 0 Byte)* | keine gültige ID erkennbar |
| *(noch keine QUERY seit Start)* | *(leer, 0 Byte)* | |

- Die Anfrage-ID wird **unverändert** in die Antwort übernommen.
- Kennungen werden **exakt** verglichen (Groß-/Kleinschreibung zählt: `d1` ergibt `UNKNOWN`).
- `RESULT` enthält immer die Antwort auf die **zuletzt** geschriebene QUERY.
- Das Archiv beantwortet die Anfrage sofort beim Write; ein anschließendes Read liefert das Ergebnis.

### 3.4 Formeltabelle

| Kennung | Dämon | Formel |
|---|---|---|
| `D1` | Toastifer | `AQUA` |
| `D2` | Kruemeloth | `SAL` |
| `D3` | Belzebrot | `LUX` |

Die Tabelle liegt **nur** beim Archiv (und beim Toaster zum Prüfen).
**Der Exorzist darf keine eigene Formeltabelle enthalten**: Er muss die echte Antwort des Archivs verwenden.

## 4. Toaster (Gruppe 1): laut Folien

> Die verbindliche Spezifikation liefert Gruppe 1. Hier steht nur, was die Projektfolien vorgeben.

| Characteristic | Richtung | Inhalt laut Folien |
|---|---|---|
| `INFO` | Read | Dämonenkennung `D1`, `D2` oder `D3` |
| `STATE` | Read | aktueller Zustand bzw. Ergebnis, z. B. `01:OK:C` |
| `RITUAL` | Write (mit Response) | `<ID>:<Formel>`, z. B. `01:AQUA` |

- Gerätename: `EaaS-Toaster`
- Zustände: `P` = besessen (nach lokalem Reset), `C` = gereinigt (passende Formel), `V` = verärgert (falsche Formel)
- Falsche Formel: Der Toaster antwortet `WRONG`, Zustand `V`, keine Erfolgsmeldung.
- Nur eine passende `OK`-Antwort mit `C` und gleicher ID zählt als Erfolg.

## 5. Vollständiger Ablauf (Exorzist, Gruppe 3)

```
1. Scan nach Toaster-Service, verbinden, INFO lesen           -> D1
   STATE lesen, trennen
2. Scan nach Archiv-Service, verbinden
   QUERY schreiben                                            <- 01:D1
   RESULT lesen, ID prüfen                                    -> 01:AQUA
   trennen
3. Erneut mit dem Toaster verbinden
   RITUAL schreiben                                           <- 01:AQUA
   STATE lesen, ID prüfen                                     -> 01:OK:C
```

Abbruchregeln (laut Folien):

| Ereignis | Erwartetes Verhalten |
|---|---|
| Archiv liefert `UNKNOWN` | kein Ritual ausführen |
| Keine bzw. nicht passende Antwort innerhalb 3 s | Timeout sichtbar melden, **keinen Ersatzcode erfinden** |
| Falsche Formel | Toaster: `WRONG`, Zustand `V`; keine Erfolgsmeldung |
| Verbindungsabbruch nach dem Ritual | Ergebnis unklar → neu verbinden und `STATE` lesen |

## 6. Testfälle mit dem Archiv

| Test | QUERY | erwartetes RESULT |
|---|---|---|
| bekannter Dämon | `01:D1` | `01:AQUA` |
| unbekannter Dämon | `02:DX` | `02:UNKNOWN` |
| ID-Übernahme | `42:D3` | `42:LUX` |

## 7. Offen: noch abzustimmen

| Punkt | Zuständig |
|---|---|
| Endgültige Service- und Characteristic-UUIDs aller Geräte (technischer Anhang ab Folie 15) | alle Gruppen |
| Exaktes Format von `INFO` (nur `D1` oder mit ID?) | Gruppe 1 |
| Exaktes `STATE`-Format im Fehlerfall (z. B. ob `01:WRONG:V`) und vor dem ersten Ritual | Gruppe 1 |
| Optionale Erweiterung D4: neue Kennung und Formel | Gruppe 1 + 2 |
| Optional: Notify auf `STATE` | Gruppe 1 + 3 |
