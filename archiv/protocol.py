"""Fachlogik des Dämonenarchivs – unabhängig von Bluetooth und damit testbar.

Nachrichtenformat (gemeinsamer Vertrag):
  * ASCII, höchstens 20 Byte, ohne Leerzeichen oder Zeilenumbruch
  * Doppelpunkte trennen Felder
  * Anfrage-IDs 01 bis 99

QUERY  (Write):  "<ID>:<Kennung>"   z. B. "01:D1"
RESULT (Read):   "<ID>:<Formel>"    z. B. "01:AQUA"
                 "<ID>:UNKNOWN"     bei unbekannter Kennung oder kaputter Nutzlast
                 ""  (leer)         wenn keine gültige Anfrage-ID erkennbar ist
"""

from __future__ import annotations

from dataclasses import dataclass

MAX_LEN = 20
UNKNOWN = "UNKNOWN"

# Formeltabelle: Kennung -> (Dämon, Formel).
# Erweiterung D4: einfach hier eintragen (gemeinsam mit Gruppe 1 abstimmen).
DAEMONEN: dict[str, tuple[str, str]] = {
    "D1": ("Toastifer", "AQUA"),
    "D2": ("Kruemeloth", "SAL"),
    "D3": ("Belzebrot", "LUX"),
}


@dataclass(frozen=True)
class Antwort:
    request_id: str | None  # None, wenn keine gültige ID erkennbar war
    kennung: str | None
    formel: str | None      # None bei UNKNOWN / ohne ID
    result: bytes           # Wert, der in RESULT landet


def _parse_id(text: str) -> str | None:
    if len(text) == 2 and text.isdigit() and text != "00":
        return text
    return None


def verarbeite_query(raw: bytes) -> Antwort:
    """Verarbeitet einen QUERY-Schreibzugriff und liefert die RESULT-Antwort."""
    try:
        text = bytes(raw).decode("ascii")
    except UnicodeDecodeError:
        return Antwort(None, None, None, b"")

    # Formatverletzungen: zu lang oder Leerraum enthalten
    if len(raw) > MAX_LEN or any(c.isspace() for c in text):
        rid = _parse_id(text.split(":", 1)[0].strip())
        return _unknown(rid, None)

    teile = text.split(":")
    rid = _parse_id(teile[0])
    if rid is None:
        return Antwort(None, None, None, b"")

    if len(teile) != 2 or not teile[1]:
        return _unknown(rid, None)

    kennung = teile[1]
    eintrag = DAEMONEN.get(kennung)
    if eintrag is None:
        return _unknown(rid, kennung)

    formel = eintrag[1]
    return Antwort(rid, kennung, formel, f"{rid}:{formel}".encode("ascii"))


def _unknown(rid: str | None, kennung: str | None) -> Antwort:
    if rid is None:
        return Antwort(None, kennung, None, b"")
    return Antwort(rid, kennung, None, f"{rid}:{UNKNOWN}".encode("ascii"))
