"""Zustand des Archivs ohne Bluetooth-Abhängigkeit.

Der BLE-Server (server.py) und die Oberflächen (Konsole, ui.py) hängen sich als
Zuhörer an und bekommen jede Anfrage und jede Abholung als Ereignis gemeldet.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable, Literal

from .protocol import Antwort, verarbeite_query


@dataclass(frozen=True)
class Ereignis:
    art: Literal["query", "read"]
    roh: bytes                 # geschriebene QUERY bzw. gelesenes RESULT
    result: bytes              # RESULT-Wert nach dem Ereignis
    antwort: Antwort | None = None
    zeit: datetime = field(default_factory=datetime.now)


Zuhoerer = Callable[[Ereignis], None]


class Archiv:
    def __init__(self) -> None:
        self.result: bytes = b""
        self._zuhoerer: list[Zuhoerer] = []
        self._lock = threading.Lock()

    def abonnieren(self, fn: Zuhoerer) -> None:
        self._zuhoerer.append(fn)

    def anfrage(self, raw: bytes) -> Antwort:
        """QUERY wurde geschrieben: Antwort berechnen und in RESULT ablegen."""
        antwort = verarbeite_query(bytes(raw))
        with self._lock:
            self.result = antwort.result
        self._melde(Ereignis("query", bytes(raw), antwort.result, antwort))
        return antwort

    def abholen(self) -> bytes:
        """RESULT wird gelesen."""
        with self._lock:
            wert = self.result
        self._melde(Ereignis("read", wert, wert))
        return wert

    def _melde(self, ereignis: Ereignis) -> None:
        for fn in self._zuhoerer:
            try:
                fn(ereignis)
            except Exception:  # eine kaputte Anzeige darf das Archiv nicht stoppen
                pass
