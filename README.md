# EaaS-Archiv – Gruppe 2: Das Dämonenarchiv

Praxisprojekt *Exorcism as a Service* (Vernetzte Systeme, Bluetooth Low Energy).
Das Archiv ist ein **BLE-Peripheral + GATT-Server**. Der Exorzist (Gruppe 3) schreibt
eine Dämonenkennung in `QUERY` und liest die passende Austreibungsformel aus `RESULT`.

```
TOASTER / G1  <──>  EXORZIST / G3  <──>  ARCHIV / G2 (dieses Repo)
```

## Schnittstelle

| Eigenschaft | Wert |
|---|---|
| Gerätename | `EaaS-Archiv` |
| Service-UUID | **Platzhalter** – siehe [`archiv/config.py`](archiv/config.py) |
| `QUERY` | Write mit Response, Platzhalter-UUID |
| `RESULT` | Read, Platzhalter-UUID |

> ⚠️ Die verbindlichen UUIDs stehen im technischen Anhang (ab Folie 15) und müssen vor
> der Integration in `archiv/config.py` eingetragen werden.

### Nachrichtenformat

ASCII, höchstens 20 Byte, keine Leerzeichen/Zeilenumbrüche, Felder durch `:` getrennt,
Anfrage-IDs `01`–`99`. Die Anfrage-ID wird in jede Antwort übernommen.

| QUERY (geschrieben) | RESULT (gelesen) | Bedeutung |
|---|---|---|
| `01:D1` | `01:AQUA` | Toastifer |
| `01:D2` | `01:SAL` | Kruemeloth |
| `01:D3` | `01:LUX` | Belzebrot |
| `01:DX` | `01:UNKNOWN` | unbekannte Kennung |
| `01:`, `01:D 1`, > 20 Byte … | `01:UNKNOWN` | gültige ID, kaputte Nutzlast |
| `D1`, `00:D1`, `1:D1` … | *(leer)* | keine gültige Anfrage-ID erkennbar |
| *(noch keine Anfrage)* | *(leer)* | |

Kennungen werden exakt verglichen (`d1` ≠ `D1`).
Neue Dämonen (Erweiterung D4) werden in `DAEMONEN` in
[`archiv/protocol.py`](archiv/protocol.py) ergänzt – abgestimmt mit Gruppe 1.

## Starten

**Linux / macOS**

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m archiv.server
```

**Windows** (bless braucht hier Python 3.11, siehe unten)

```powershell
py install 3.11
py -V:3.11 -m venv .venv
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\python -m archiv.server
```

Liegt das Repo in OneDrive, die venv besser außerhalb anlegen (z. B. `C:\dev\venvs\eaas-archiv`),
damit OneDrive nicht tausende Dateien synchronisiert.

Die Konsole zeigt jede eingegangene Anfrage und die gelieferte Formel:

```
[10:42:01] QUERY  '01:D1'                  D1 = Toastifer -> Formel AQUA
[10:42:01]        RESULT = 01:AQUA
[10:42:01] READ   RESULT -> 01:AQUA
```

### Hinweis Windows

`bless` läuft unter Linux (BlueZ) und macOS direkt. Unter Windows funktioniert es derzeit
nur mit **Python 3.11**, `bless==0.2.6`, `bleak>=0.21,<0.22`, `bleak-winrt` und dem
Paket `pysetupdi`, das nur auf GitHub verfügbar ist (`gwangyi/pysetupdi`). Das alles
installiert `requirements.txt` automatisch (Git muss installiert sein). Neuere bless-Versionen
sind unter Windows wegen widersprüchlicher winrt-Abhängigkeiten nicht installierbar.

Außerdem zeigt Windows beim Advertising den Bluetooth-Namen des Rechners statt
`EaaS-Archiv`, also sollte der Exorzist nach der **Service-UUID** scannen.

## Tests

Die Fachlogik ist ohne Bluetooth testbar:

```bash
python -m unittest discover -s tests -t .
```
