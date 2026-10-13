import unittest
from pathlib import Path


class TranslationFilesTest(unittest.TestCase):
    """Both the compiled translations and the module that loads them exist."""

    def test_compiled_translations_exist(self):
        i18n = Path(__file__).resolve().parent.parent / "i18n"
        for name in ("mintcam_en.qm", "mintcam_it.qm"):
            self.assertTrue((i18n / name).is_file(), f"{name} mancante")

    def test_source_translations_exist(self):
        i18n = Path(__file__).resolve().parent.parent / "i18n"
        self.assertTrue((i18n / "mintcam_en.ts").is_file())

    def test_languages_list(self):
        from app.i18n import LANGUAGES, available
        self.assertEqual(set(LANGUAGES), {"it", "en"})
        codes = [code for code, _ in available()]
        self.assertIn("it", codes)
        self.assertIn("en", codes)

    def test_english_translation_has_entries(self):
        import xml.etree.ElementTree as ET
        path = (Path(__file__).resolve().parent.parent / "i18n" / "mintcam_en.ts")
        root = ET.parse(path).getroot()
        translated = [m for m in root.iter("message")
                      if m.findtext("translation")]
        self.assertGreater(len(translated), 100)

    def test_install_returns_false_for_interface_language(self):
        from app.i18n import install
        # l'italiano è la lingua dell'interfaccia: nessun traduttore da caricare
        self.assertFalse(install(None, "it"))

    def test_install_returns_false_for_unknown_language(self):
        from app.i18n import install
        self.assertFalse(install(None, "de"))
