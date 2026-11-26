from typing import Dict, List

from jhora import const


NORTH_EN_PLANET_NAME_FIXES: Dict[str, str] = {"Raagu": "Rahu", "Kethu": "Ketu"}

NORTH_EN_NAKSHATRA_NAMES: List[str] = [
    "Ashvini", "Bharani", "Krittika", "Rohini", "Mrigashirsha",
    "Ardra", "Punarvasu", "Pushya", "Ashlesha", "Magha",
    "Purva Phalguni", "Uttara Phalguni", "Hasta", "Chitra", "Svati",
    "Vishakha", "Anuradha", "Jyeshtha", "Mula", "Purvashadha",
    "Uttarashadha", "Shravana", "Dhanishtha", "Shatabhisha",
    "Purva Bhadrapada", "Uttara Bhadrapada", "Revati", "Abhijit",
]

_PLANET_SYMBOLS_SET = set(const._planet_symbols)
_ZODIAC_SYMBOLS_SET = set(const._zodiac_symbols)
_VARIATION_SELECTORS = {0xFE0E, 0xFE0F}


class ChartCleaner:
    @staticmethod
    def clean_unicode(text: str) -> str:
        """Strip control characters and excess whitespace; preserve Unicode."""
        return text.replace("\n", " ").replace("\r", " ").strip()

    @staticmethod
    def split_name_symbol(text: str) -> tuple:
        """Split 'Sun☉' or 'सूर्य☉' into ('Sun', '☉').

        jhora lang files store names as '{name}{symbol}' where the symbol
        is a known planet symbol character appended at the end.
        """
        text = text.strip()
        if text and text[-1] in _PLANET_SYMBOLS_SET:
            return text[:-1].strip(), text[-1]
        return text, ""

    @staticmethod
    def strip_zodiac_prefix(text: str) -> str:
        """Strip leading zodiac symbol (and variation selectors) from '♈Aries' or '♑︎मकर'."""
        i = 0
        while i < len(text) and (
            text[i] in _ZODIAC_SYMBOLS_SET or ord(text[i]) in _VARIATION_SELECTORS
        ):
            i += 1
        return text[i:].strip()
