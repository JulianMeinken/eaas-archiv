"""Terminal-UI des Archivs: das Bundesamt für Dämonenangelegenheiten.

Start mit Bluetooth:   python -m archiv.ui
Übungsbetrieb:         python -m archiv.ui --demo   (simuliert Anfragen, ohne BLE)
Beenden: Strg+C
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import random
import sys
import threading
import time
from collections import deque
from dataclasses import dataclass
from datetime import datetime

from rich import box
from rich.align import Align
from rich.console import Console, Group, RenderableType
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from . import config
from .core import Archiv, Ereignis
from .protocol import DAEMONEN

AMT = "BUNDESAMT FÜR DÄMONENANGELEGENHEITEN"
REFERAT = "Referat II/2 · Austreibungsformeln · Dienststelle EaaS-Archiv"

HINWEISE = [
    "Bitte halten Sie Ihre Dämonenkennung bereit.",
    "Austreibungen ohne gültigen Bescheid sind ordnungswidrig (§ 666 DämonG).",
    "Sprechzeiten: Mo–Fr 9–12 Uhr, Vollmondnächte nach Vereinbarung.",
    "Formblatt EX-7 bitte in dreifacher Ausfertigung einreichen. Blut ist nicht erforderlich.",
    "Die Bearbeitungsdauer beträgt höchstens 3 Sekunden. Gemäß gemeinsamem Vertrag.",
    "Bitte legen Sie keine Pentagramme in den Toaster.",
    "Anträge über 20 Byte werden aus Gründen der Papierersparnis abgelehnt.",
    "Diese Dienststelle ist nach ISO 9001:666 zertifiziert.",
    "Leerzeichen in Anträgen sind seit der Verwaltungsreform 1666 unzulässig.",
    "Ihr Anliegen ist uns wichtig. Bitte warten Sie. Ewig, falls nötig.",
    "Der Exorzist muss die Formel beim Amt erfragen. Eigene Tabellen sind Schwarzarbeit.",
]

# Status -> (Farbe, Stempeltext)
STEMPEL = {
    "GENEHMIGT": ("green", "✔  GENEHMIGT"),
    "UNBEKANNT": ("yellow", "?  UNBEKANNT"),
    "FORMFEHLER": ("red", "✘  FORMFEHLER"),
    "UNZULÄSSIG": ("magenta", "⊘  UNZULÄSSIG"),
}


@dataclass
class Akte:
    nr: int
    zeit: datetime
    anfrage: str
    request_id: str | None
    kennung: str | None
    formel: str | None
    result: str
    status: str
    abgeholt_um: datetime | None = None

    @property
    def zeichen(self) -> str:
        return f"DA-{self.zeit:%Y}/{self.nr:04d}"


def _status(e: Ereignis) -> str:
    a = e.antwort
    if a is None or a.request_id is None:
        return "UNZULÄSSIG"
    if a.formel:
        return "GENEHMIGT"
    if a.kennung:
        return "UNBEKANNT"
    return "FORMFEHLER"


class Behoerde:
    """Hört dem Archiv zu und rendert daraus die Amtsstube."""

    def __init__(self, modus: str) -> None:
        self.modus = modus
        self.betrieb = "Dienststelle öffnet ..."
        self.akten: deque[Akte] = deque(maxlen=500)
        self.lfd = 0
        self.abgeholt = 0
        self.leer_abgeholt = 0
        self.zaehler = {k: 0 for k in STEMPEL}
        self.start = datetime.now()
        self._lock = threading.Lock()

    # --- Zuhörer ----------------------------------------------------------
    def melden(self, e: Ereignis) -> None:
        with self._lock:
            if e.art == "query":
                self.lfd += 1
                a = e.antwort
                status = _status(e)
                self.zaehler[status] += 1
                self.akten.append(
                    Akte(
                        nr=self.lfd,
                        zeit=e.zeit,
                        anfrage=e.roh.decode("ascii", errors="replace"),
                        request_id=a.request_id if a else None,
                        kennung=a.kennung if a else None,
                        formel=a.formel if a else None,
                        result=e.result.decode("ascii"),
                        status=status,
                    )
                )
            elif not e.result:
                self.leer_abgeholt += 1
            else:
                letzte = self.akten[-1] if self.akten else None
                if letzte and letzte.abgeholt_um is None and letzte.result == e.result.decode("ascii"):
                    letzte.abgeholt_um = e.zeit
                    self.abgeholt += 1

    # --- Darstellung --------------------------------------------------------
    def render(self, breite: int = 140, hoehe: int = 42) -> RenderableType:
        with self._lock:
            akten = list(self.akten)
            zaehler = dict(self.zaehler)
            abgeholt, leer = self.abgeholt, self.leer_abgeholt

        kompakt = hoehe < 40   # kleines Fenster: Dienststelle ausblenden, Bescheid kürzen
        schmal = breite < 135

        layout = Layout()
        layout.split_column(
            Layout(self._kopf(len(akten)), name="kopf", size=4),
            Layout(name="mitte"),
            Layout(self._fuss(), name="fuss", size=3),
        )
        layout["mitte"].split_row(
            Layout(name="links", size=40 if schmal else 48),
            Layout(name="rechts"),
        )
        links = [
            Layout(self._verzeichnis(), size=len(DAEMONEN) + 6),
            Layout(self._statistik(len(akten), zaehler, abgeholt, leer), size=12),
        ]
        if not kompakt:
            links.append(Layout(self._dienststelle(kurz=schmal)))
        else:
            links.append(Layout(" "))
        layout["links"].split_column(*links)
        layout["rechts"].split_column(
            Layout(self._bescheid(akten[-1] if akten else None, kompakt), size=14 if kompakt else 17),
            Layout(self._register(akten)),
        )
        return layout

    def _kopf(self, anzahl: int) -> RenderableType:
        jetzt = datetime.now()
        grid = Table.grid(expand=True)
        grid.add_column(justify="left", ratio=1)
        grid.add_column(justify="center", ratio=3)
        grid.add_column(justify="right", ratio=1)
        if self.betrieb.startswith("Dienstbetrieb"):
            offen, farbe = "GEÖFFNET", "bold green"
        elif self.betrieb.startswith("STÖRUNG"):
            offen, farbe = "STÖRUNG", "bold red blink"
        else:
            offen, farbe = "BITTE WARTEN", "bold yellow"
        modus = "ÜBUNG" if self.modus == "DEMO" else "BLE"
        grid.add_row(
            Text.assemble(("Wartenummer\n", "dim"), (f"{anzahl + 1:04d}", "bold cyan")),
            Text.assemble((f"⚜  {AMT}  ⚜\n", "bold white"), (REFERAT, "italic grey70")),
            Text.assemble((f"{jetzt:%d.%m.%Y %H:%M:%S}\n", "white"),
                          (offen, farbe),
                          (f" · {modus}", "magenta" if self.modus == "DEMO" else "green")),
        )
        return Panel(grid, box=box.DOUBLE, border_style="bright_blue")

    def _verzeichnis(self) -> RenderableType:
        t = Table(box=box.SIMPLE_HEAD, expand=True, header_style="bold")
        t.add_column("Kennung")
        t.add_column("Dämon")
        t.add_column("Formel", style="bold")
        for k, (d, f) in DAEMONEN.items():
            t.add_row(k, d, f)
        return Panel(t, title="Amtliches Formelverzeichnis", subtitle="Anlage 1 zu § 3 DämonG",
                     border_style="grey50")

    def _statistik(self, n: int, z: dict[str, int], abgeholt: int, leer: int) -> RenderableType:
        dauer = datetime.now() - self.start
        h, rest = divmod(int(dauer.total_seconds()), 3600)
        m, s = divmod(rest, 60)
        t = Table.grid(expand=True, padding=(0, 1))
        t.add_column()
        t.add_column(justify="right")
        t.add_row("Anträge eingegangen", Text(str(n), style="bold"))
        for status, (farbe, _) in STEMPEL.items():
            t.add_row(Text(f"  davon {status.lower()}", style=farbe), str(z[status]))
        t.add_row("Bescheide abgeholt", str(abgeholt))
        t.add_row(Text("Abholversuche ohne Bescheid", style="dim"), str(leer))
        t.add_row(Text("Dienstzeit", style="dim"), f"{h:02d}:{m:02d}:{s:02d}")
        quote = (z["GENEHMIGT"] / n * 100) if n else 0
        t.add_row(Text("Genehmigungsquote", style="dim"), f"{quote:.0f} %")
        return Panel(t, title="Geschäftsstatistik", border_style="grey50")

    def _dienststelle(self, kurz: bool = False) -> RenderableType:
        def uuid(u: str) -> str:
            return f"{u[:8]}…{u[-4:]}" if kurz else u

        t = Table.grid(padding=(0, 1))
        t.add_column(style="dim")
        t.add_column()
        farbe = "magenta" if self.modus == "DEMO" else "green"
        t.add_row("Modus", Text("ÜBUNGSBETRIEB (Demo)" if self.modus == "DEMO" else "Bluetooth LE",
                                style=f"bold {farbe}"))
        t.add_row("Status", self.betrieb)
        t.add_row("Gerät", config.DEVICE_NAME)
        t.add_row("Service", uuid(config.SERVICE_UUID))
        t.add_row("QUERY", uuid(config.QUERY_UUID))
        t.add_row("RESULT", uuid(config.RESULT_UUID))
        return Panel(t, title="Dienststelle", border_style="grey50")

    def _bescheid(self, akte: Akte | None, kompakt: bool = False) -> RenderableType:
        if akte is None and self.betrieb.startswith("STÖRUNG"):
            stoerung = Text.assemble(
                ("BETRIEBSSTÖRUNG\n\n", "bold red"),
                (self.betrieb.removeprefix("STÖRUNG: ") + "\n\n", "bold"),
                ("Die Dienststelle konnte sich nicht per Bluetooth anmelden. Bitte prüfen Sie, ob "
                 "bereits ein anderes Archiv läuft und ob Bluetooth eingeschaltet ist.", "italic"),
                justify="center",
            )
            return Panel(Align.center(stoerung, vertical="middle"), title="Aktueller Bescheid",
                         border_style="red")
        if akte is None:
            leer = Text.assemble(
                ("Derzeit liegen keine Anträge vor.\n\n", "bold"),
                ("Die Sachbearbeitung trinkt Kaffee und sortiert Pentagramme.\n", "italic"),
                ("Anträge bitte per Write mit Response an QUERY einreichen.", "dim"),
                justify="center",
            )
            return Panel(Align.center(leer, vertical="middle"), title="Aktueller Bescheid",
                         border_style="grey50")

        farbe, stempeltext = STEMPEL[akte.status]
        brief = Text()
        brief.append(f"Az. {akte.zeichen}", style="bold")
        brief.append(f" · Zeichen {akte.request_id or '—'} · {akte.zeit:%H:%M:%S}\n", style="dim")
        brief.append(f"Betreff: Antrag „{akte.anfrage}“\n\n")
        if not kompakt:
            brief.append("Sehr geehrte Antragstellende,\n\n")

        if akte.status == "GENEHMIGT":
            daemon = DAEMONEN[akte.kennung][0]
            brief.append("Ihrem Antrag wird stattgegeben. Der Dämon ")
            brief.append(daemon, style="bold")
            brief.append(f" ({akte.kennung}) ist hier aktenkundig.\nDie amtliche Austreibungsformel lautet:\n\n")
            brief.append(f"   {'  '.join(akte.formel)}   ", style="bold black on yellow")
            brief.append("\n" if kompakt else "\n\n")
            brief.append("Gebühr: 0,00 € (Erstaustreibung gebührenfrei).", style="dim" if kompakt else "")
        elif akte.status == "UNBEKANNT":
            brief.append("zu der Kennung ")
            brief.append(akte.kennung or "", style="bold")
            brief.append(" liegt hier keine Akte vor. Zuständig ist vermutlich eine andere Unterwelt.\n")
            brief.append("Ein Ritual ist NICHT zu vollziehen.", style="bold")
        elif akte.status == "FORMFEHLER":
            brief.append("Ihr Antrag entspricht nicht den Formvorschriften ")
            brief.append("(ASCII, max. 20 Byte, ID:Kennung, keine Leerzeichen).\n", style="dim")
            brief.append("Er wird als UNKNOWN beschieden. Bitte formgerecht neu einreichen.")
        else:
            brief.append("Ihr Antrag trägt kein gültiges Zeichen (01–99) und wird ungelesen abgeheftet.\n")
            brief.append("Es ergeht kein Bescheid.", style="bold")

        brief.append("\n" if kompakt else "\n\n")
        brief.append("RESULT: ", style="dim")
        brief.append(akte.result or "(leer)", style="bold")
        if akte.abgeholt_um:
            brief.append(f"   ·   Zugestellt um {akte.abgeholt_um:%H:%M:%S}", style="green")
        elif akte.result:
            brief.append("   ·   Liegt zur Abholung bereit", style="yellow")

        stempel = Panel(Text(stempeltext, style=f"bold {farbe}", justify="center"),
                        box=box.DOUBLE, border_style=farbe, width=20)
        grid = Table.grid(expand=True, padding=(0, 2))
        grid.add_column(ratio=1)
        grid.add_column(width=22, vertical="middle")
        grid.add_row(brief, Group(Text(""), stempel, Text("i. A. Sachbearbeitung\n     Referat II/2",
                                                          style="italic dim")))
        return Panel(grid, title="Aktueller Bescheid", border_style=farbe)

    def _register(self, akten: list[Akte]) -> RenderableType:
        t = Table(box=box.SIMPLE_HEAD, expand=True, header_style="bold", pad_edge=False)
        t.add_column("Aktenzeichen", no_wrap=True, min_width=12)
        t.add_column("Eingang", no_wrap=True, min_width=8)
        t.add_column("Antrag", no_wrap=True, min_width=8, overflow="ellipsis")
        t.add_column("Bescheid", no_wrap=True, min_width=10)
        t.add_column("Stempel", no_wrap=True, min_width=12)
        t.add_column("Zustellung", no_wrap=True, min_width=12)
        for a in reversed(akten[-30:]):
            farbe, stempeltext = STEMPEL[a.status]
            t.add_row(
                a.zeichen,
                f"{a.zeit:%H:%M:%S}",
                a.anfrage,
                a.result or Text("(leer)", style="dim"),
                Text(stempeltext.replace("  ", " "), style=farbe),
                Text("zugestellt", style="green") if a.abgeholt_um
                else Text("—", style="dim") if not a.result else Text("wartet", style="yellow"),
            )
        if not akten:
            t.add_row("—", "", Text("keine Vorgänge", style="dim"), "", "", "")
        return Panel(t, title="Posteingang / Aktenregister", border_style="grey50")

    def _fuss(self) -> RenderableType:
        hinweis = HINWEISE[int(time.monotonic() / 7) % len(HINWEISE)]
        return Panel(Text.assemble(("Amtlicher Hinweis: ", "bold"), (hinweis, "italic"), no_wrap=True,
                                   overflow="ellipsis"),
                     subtitle="Strg+C schließt die Dienststelle", subtitle_align="right",
                     border_style="bright_blue")


# --- Betrieb ------------------------------------------------------------------

async def uebungsbetrieb(archiv: Archiv) -> None:
    """Simuliert einen Exorzisten, der Anträge stellt und Bescheide abholt."""
    kennungen = ["D1", "D2", "D3", "DX", "D4", "d1", "D 1", "D1:X"]
    gewichte = [5, 4, 4, 2, 1, 1, 1, 1]
    rid = 0
    while True:
        await asyncio.sleep(random.uniform(2.5, 4.5))
        rid = rid % 99 + 1
        if random.random() < 0.07:
            raw = b"D1"  # vergessenes Zeichen
        else:
            raw = f"{rid:02d}:{random.choices(kennungen, gewichte)[0]}".encode("ascii")
        archiv.anfrage(raw)
        await asyncio.sleep(random.uniform(0.4, 1.2))
        archiv.abholen()


async def _betrieb(archiv: Archiv, behoerde: Behoerde, demo: bool) -> None:
    if demo:
        behoerde.betrieb = "Dienstbetrieb (Übungsakten)"
        await uebungsbetrieb(archiv)
    else:
        from .server import betreibe_ble

        def gestartet() -> None:
            behoerde.betrieb = "Dienstbetrieb · wirbt per BLE"

        await betreibe_ble(archiv, gestartet)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Bundesamt für Dämonenangelegenheiten (EaaS-Archiv)")
    parser.add_argument("--demo", action="store_true", help="Übungsbetrieb ohne Bluetooth")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.WARNING)
    for stream in (sys.stdout, sys.stderr):  # Sonderzeichen auch in alten Konsolen/Pipes
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    archiv = Archiv()
    behoerde = Behoerde("DEMO" if args.demo else "BLE")
    archiv.abonnieren(behoerde.melden)

    # Der Betrieb (BLE oder Übung) läuft in einem eigenen Thread mit eigener Event-Loop.
    # So bleibt die Oberfläche bedienbar und Strg+C wirkt auch dann, wenn der
    # Bluetooth-Stack beim Start hängt (z. B. weil schon ein Archiv läuft).
    loop = asyncio.new_event_loop()
    fehler: BaseException | None = None

    def betrieb_thread() -> None:
        nonlocal fehler
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(_betrieb(archiv, behoerde, args.demo))
        except asyncio.CancelledError:
            pass
        except Exception as ex:  # z. B. kein Bluetooth-Adapter
            fehler = ex

    thread = threading.Thread(target=betrieb_thread, name="betrieb", daemon=True)
    console = Console()
    with Live(get_renderable=lambda: behoerde.render(*console.size), console=console,
              screen=True, refresh_per_second=4):
        thread.start()
        start = time.monotonic()
        try:
            while thread.is_alive():
                thread.join(0.25)
                if (not behoerde.betrieb.startswith(("Dienstbetrieb", "STÖRUNG"))
                        and time.monotonic() - start > 15):
                    behoerde.betrieb = "STÖRUNG: BLE-Start hängt. Läuft schon ein Archiv?"
        except KeyboardInterrupt:
            for task in asyncio.all_tasks(loop):
                loop.call_soon_threadsafe(task.cancel)
            thread.join(5)  # Server sauber stoppen, aber nicht ewig warten

    if fehler:
        console.print(f"[bold red]Die Dienststelle konnte nicht öffnen:[/] {fehler!r}")
        return 1
    console.print(f"[bold]Dienststelle geschlossen.[/] {behoerde.lfd} Anträge bearbeitet. "
                  "Wir danken für Ihre Geduld.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
