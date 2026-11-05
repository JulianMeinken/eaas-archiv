import unittest

from archiv.protocol import verarbeite_query


def r(q: bytes) -> bytes:
    return verarbeite_query(q).result


class ProtocolTest(unittest.TestCase):
    def test_bekannte_faelle(self):
        self.assertEqual(r(b"01:D1"), b"01:AQUA")
        self.assertEqual(r(b"02:D2"), b"02:SAL")
        self.assertEqual(r(b"99:D3"), b"99:LUX")

    def test_id_wird_uebernommen(self):
        self.assertEqual(r(b"42:D1"), b"42:AQUA")

    def test_unbekannte_kennung(self):
        self.assertEqual(r(b"01:DX"), b"01:UNKNOWN")
        self.assertEqual(r(b"07:d1"), b"07:UNKNOWN")

    def test_kaputte_nutzlast_mit_gueltiger_id(self):
        self.assertEqual(r(b"03:"), b"03:UNKNOWN")
        self.assertEqual(r(b"03"), b"03:UNKNOWN")
        self.assertEqual(r(b"03:D1:X"), b"03:UNKNOWN")
        self.assertEqual(r(b"03:D 1"), b"03:UNKNOWN")
        self.assertEqual(r(b"03:D1\n"), b"03:UNKNOWN")
        self.assertEqual(r(b"03:" + b"D" * 20), b"03:UNKNOWN")

    def test_ohne_gueltige_id_bleibt_leer(self):
        for q in [b"", b"D1", b"1:D1", b"00:D1", b"100:D1", b"AB:D1", b"\xff\xfe"]:
            with self.subTest(q=q):
                self.assertEqual(r(q), b"")

    def test_antworten_hoechstens_20_byte(self):
        for q in [b"01:D1", b"01:DX", b"99:" + b"X" * 30]:
            self.assertLessEqual(len(r(q)), 20)


if __name__ == "__main__":
    unittest.main()
