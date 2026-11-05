import io
import unittest

from archiv.core import Archiv

try:
    from rich.console import Console

    from archiv.ui import Behoerde
except ImportError:  # rich nicht installiert
    Behoerde = None


@unittest.skipIf(Behoerde is None, "rich ist nicht installiert")
class BehoerdeTest(unittest.TestCase):
    def setUp(self):
        self.archiv = Archiv()
        self.amt = Behoerde("DEMO")
        self.archiv.abonnieren(self.amt.melden)

    def render_text(self) -> str:
        c = Console(file=io.StringIO(), width=140, height=42, record=True)
        c.print(self.amt.render())
        return c.export_text()

    def test_stempel_und_zaehler(self):
        for q in [b"01:D1", b"02:DX", b"03:D 1", b"D1"]:
            self.archiv.anfrage(q)
        self.assertEqual(
            [a.status for a in self.amt.akten],
            ["GENEHMIGT", "UNBEKANNT", "FORMFEHLER", "UNZULÄSSIG"],
        )
        self.assertEqual(self.amt.zaehler["GENEHMIGT"], 1)

    def test_abholung_wird_vermerkt(self):
        self.archiv.anfrage(b"01:D1")
        self.archiv.abholen()
        self.assertIsNotNone(self.amt.akten[-1].abgeholt_um)
        self.assertEqual(self.amt.abgeholt, 1)

    def test_leere_abholung(self):
        self.archiv.abholen()
        self.assertEqual(self.amt.leer_abgeholt, 1)

    def test_render_zeigt_bescheid(self):
        self.assertIn("keine Anträge", self.render_text())
        self.archiv.anfrage(b"07:D3")
        text = self.render_text()
        self.assertIn("GENEHMIGT", text)
        self.assertIn("07:LUX", text)
        self.assertIn("Belzebrot", text)


class ArchivTest(unittest.TestCase):
    def test_result_folgt_letzter_anfrage(self):
        archiv = Archiv()
        self.assertEqual(archiv.abholen(), b"")
        archiv.anfrage(b"01:D2")
        self.assertEqual(archiv.abholen(), b"01:SAL")
        archiv.anfrage(b"02:DX")
        self.assertEqual(archiv.abholen(), b"02:UNKNOWN")


if __name__ == "__main__":
    unittest.main()
