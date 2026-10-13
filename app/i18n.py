"""Language selection for MintCam.

The user interface is written in Italian and translated through the Qt
translation system: the source strings are wrapped in self.tr(), the
translations live in .ts files and are compiled to .qm, which is what the
application loads at run time. Nothing else is needed at run time, so the
package only has to ship the compiled files.

Adding a language later means adding a .ts file with the translated strings and
listing it in LANGUAGES: no change to the application code.
"""

import logging
from pathlib import Path

from PyQt6.QtCore import QLocale, QTranslator

logger = logging.getLogger("mintcam.i18n")

# Language code -> name shown in the selector. The first entry is the language
# the interface is written in, so it needs no translation file.
LANGUAGES: dict[str, str] = {
    "it": "Italiano",
    "en": "English",
}

TRANSLATIONS_DIR = Path(__file__).resolve().parent.parent / "i18n"


def system_language() -> str:
    """Best match between the system locale and the supported languages."""
    locale = QLocale.system()
    for name in (locale.name(), locale.name().split("_")[0]):
        if name in LANGUAGES:
            return name
    return "it"


def install(app, language: str) -> bool:
    """Load the translation for `language` and install it on the application.

    Returns True when a translator was installed, False when the language is
    the interface language (nothing to translate) or the file is missing.
    """
    if language not in LANGUAGES or language == "it":
        return False
    path = TRANSLATIONS_DIR / f"mintcam_{language}.qm"
    if not path.is_file():
        logger.warning("Traduzione mancante: %s", path)
        return False
    translator = QTranslator(app)
    if not translator.load(str(path)):
        logger.warning("Traduzione non caricabile: %s", path)
        return False
    app.installTranslator(translator)
    # kept alive: a translator without a reference is garbage collected and the
    # translation silently stops working
    app._mintcam_translator = translator
    logger.info("Lingua attiva: %s", language)
    return True


def available() -> list[tuple[str, str]]:
    """Supported languages as (code, name), for the selector."""
    return sorted(LANGUAGES.items(), key=lambda item: item[1])
