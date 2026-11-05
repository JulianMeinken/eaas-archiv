"""BLE-Peripheral / GATT-Server "EaaS-Archiv" (Gruppe 2).

Start (Konsolenprotokoll):  python -m archiv.server
Start (Behörden-UI):        python -m archiv.ui
Beenden: Strg+C
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Callable

from . import config
from .core import Archiv, Ereignis
from .protocol import DAEMONEN

log = logging.getLogger("archiv")


async def betreibe_ble(archiv: Archiv, gestartet: Callable[[], None] | None = None) -> None:
    """Stellt das Archiv als GATT-Server bereit, bis die Task abgebrochen wird."""
    from bless import (  # erst hier importieren, damit der Demo-Modus ohne bless läuft
        BlessGATTCharacteristic,
        BlessServer,
        GATTAttributePermissions,
        GATTCharacteristicProperties,
    )

    loop = asyncio.get_running_loop()
    server = BlessServer(name=config.DEVICE_NAME, loop=loop)

    def on_read(characteristic: BlessGATTCharacteristic, **kwargs: Any) -> bytearray:
        if str(characteristic.uuid).lower() == config.RESULT_UUID.lower():
            return bytearray(archiv.abholen())
        return bytearray(characteristic.value or b"")

    def on_write(characteristic: BlessGATTCharacteristic, value: Any, **kwargs: Any) -> None:
        uuid = str(characteristic.uuid).lower()
        if uuid != config.QUERY_UUID.lower():
            log.warning("Schreibzugriff auf unerwartete Characteristic %s ignoriert", uuid)
            return
        characteristic.value = bytearray(value)
        archiv.anfrage(bytes(value))
        result_char = server.get_characteristic(config.RESULT_UUID)
        if result_char is not None:
            result_char.value = bytearray(archiv.result)

    server.read_request_func = on_read
    server.write_request_func = on_write

    await server.add_new_service(config.SERVICE_UUID)
    await server.add_new_characteristic(
        config.SERVICE_UUID,
        config.QUERY_UUID,
        GATTCharacteristicProperties.write,
        None,
        GATTAttributePermissions.writeable,
    )
    await server.add_new_characteristic(
        config.SERVICE_UUID,
        config.RESULT_UUID,
        GATTCharacteristicProperties.read,
        bytearray(b""),
        GATTAttributePermissions.readable,
    )

    await server.start()
    if gestartet:
        gestartet()
    try:
        await asyncio.Event().wait()
    finally:
        await server.stop()


# --- Konsolenprotokoll ------------------------------------------------------

def konsolen_protokoll(e: Ereignis) -> None:
    ts = e.zeit.strftime("%H:%M:%S")
    result = e.result.decode("ascii") or "(leer)"
    if e.art == "read":
        print(f"[{ts}] READ   RESULT -> {result}")
        return
    a = e.antwort
    anfrage = e.roh.decode("ascii", errors="replace")
    if a and a.formel:
        info = f"{a.kennung} = {DAEMONEN[a.kennung][0]} -> Formel {a.formel}"
    elif a and a.request_id:
        info = "unbekannt -> UNKNOWN"
    else:
        info = "keine gültige Anfrage-ID -> RESULT leer"
    print(f"[{ts}] QUERY  {anfrage!r:24} {info}")
    print(f"[{ts}]        RESULT = {result}")


def _startmeldung() -> None:
    print(f"{config.DEVICE_NAME} läuft und wirbt mit Service {config.SERVICE_UUID}")
    print(f"  QUERY  {config.QUERY_UUID}  (Write mit Response)")
    print(f"  RESULT {config.RESULT_UUID}  (Read)")
    print("Bekannte Fälle: " + ", ".join(f"{k} = {d} / {f}" for k, (d, f) in DAEMONEN.items()))
    print("Warte auf Anfragen ... (Strg+C beendet)\n")


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    archiv = Archiv()
    archiv.abonnieren(konsolen_protokoll)
    try:
        asyncio.run(betreibe_ble(archiv, _startmeldung))
    except KeyboardInterrupt:
        print("\nArchiv beendet.")


if __name__ == "__main__":
    main()
