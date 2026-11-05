"""BLE-Peripheral / GATT-Server "EaaS-Archiv" (Gruppe 2).

Start:  python -m archiv.server
Beenden: Strg+C
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Any

from bless import (
    BlessGATTCharacteristic,
    BlessServer,
    GATTAttributePermissions,
    GATTCharacteristicProperties,
)

from . import config
from .protocol import DAEMONEN, verarbeite_query

log = logging.getLogger("archiv")


def _ts() -> str:
    return datetime.now().strftime("%H:%M:%S")


class Archiv:
    def __init__(self) -> None:
        self.result: bytes = b""
        self.server: BlessServer | None = None

    # --- GATT-Callbacks ---------------------------------------------------
    def on_read(self, characteristic: BlessGATTCharacteristic, **kwargs: Any) -> bytearray:
        uuid = str(characteristic.uuid).lower()
        if uuid == config.RESULT_UUID.lower():
            print(f"[{_ts()}] READ   RESULT -> {self.result.decode('ascii') or '(leer)'}")
            return bytearray(self.result)
        return bytearray(characteristic.value or b"")

    def on_write(self, characteristic: BlessGATTCharacteristic, value: Any, **kwargs: Any) -> None:
        uuid = str(characteristic.uuid).lower()
        if uuid != config.QUERY_UUID.lower():
            log.warning("Schreibzugriff auf unerwartete Characteristic %s ignoriert", uuid)
            return

        raw = bytes(value)
        characteristic.value = bytearray(raw)
        antwort = verarbeite_query(raw)
        self.result = antwort.result

        result_char = self.server.get_characteristic(config.RESULT_UUID) if self.server else None
        if result_char is not None:
            result_char.value = bytearray(self.result)

        anfrage = raw.decode("ascii", errors="replace")
        if antwort.formel:
            daemon = DAEMONEN[antwort.kennung][0]
            info = f"{antwort.kennung} = {daemon} -> Formel {antwort.formel}"
        elif antwort.request_id:
            info = "unbekannt -> UNKNOWN"
        else:
            info = "keine gültige Anfrage-ID -> RESULT leer"
        print(f"[{_ts()}] QUERY  {anfrage!r:24} {info}")
        print(f"[{_ts()}]        RESULT = {self.result.decode('ascii') or '(leer)'}")

    # --- Start ------------------------------------------------------------
    async def run(self) -> None:
        loop = asyncio.get_running_loop()
        self.server = BlessServer(name=config.DEVICE_NAME, loop=loop)
        self.server.read_request_func = self.on_read
        self.server.write_request_func = self.on_write

        await self.server.add_new_service(config.SERVICE_UUID)
        await self.server.add_new_characteristic(
            config.SERVICE_UUID,
            config.QUERY_UUID,
            GATTCharacteristicProperties.write,
            None,
            GATTAttributePermissions.writeable,
        )
        await self.server.add_new_characteristic(
            config.SERVICE_UUID,
            config.RESULT_UUID,
            GATTCharacteristicProperties.read,
            bytearray(b""),
            GATTAttributePermissions.readable,
        )

        await self.server.start()
        print(f"{config.DEVICE_NAME} läuft und wirbt mit Service {config.SERVICE_UUID}")
        print(f"  QUERY  {config.QUERY_UUID}  (Write mit Response)")
        print(f"  RESULT {config.RESULT_UUID}  (Read)")
        print("Bekannte Fälle: " + ", ".join(f"{k} = {d} / {f}" for k, (d, f) in DAEMONEN.items()))
        print("Warte auf Anfragen ... (Strg+C beendet)\n")
        try:
            await asyncio.Event().wait()
        finally:
            await self.server.stop()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    try:
        asyncio.run(Archiv().run())
    except KeyboardInterrupt:
        print("\nArchiv beendet.")


if __name__ == "__main__":
    main()
