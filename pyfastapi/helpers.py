import logging
import re
from typing import Dict, List, Optional

from jhora import const


logger = logging.getLogger("uvicorn.error")

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
_RETRO_SYMBOL = const._retrogade_symbol  # '℞'


class ChartCleaner:
    @staticmethod
    def clean_text(text: str) -> str:
        return (
            re.sub(r"[^\x00-\x7F]+", "", text)
            .replace("\n", " ")
            .strip()
        )

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

    @staticmethod
    def format_response(raw_horoscope):
        placements = {}
        for raw_k, raw_v in raw_horoscope[0].items():
            k = ChartCleaner.clean_unicode(raw_k).replace(_RETRO_SYMBOL, "").strip()
            k, _ = ChartCleaner.split_name_symbol(k)
            placements[k.strip()] = ChartCleaner.clean_unicode(raw_v).replace(_RETRO_SYMBOL, "").strip()

        chart_entries = raw_horoscope[1]
        expected_chart_count = len(const.division_chart_factors)

        if len(chart_entries) == expected_chart_count:
            chart_labels = [f"D{factor}" for factor in const.division_chart_factors]
            formatted_charts = {
                name: ChartCleaner._clean_chart_houses(chart_entries[idx])
                for idx, name in enumerate(chart_labels)
            }
        else:
            formatted_charts = ChartCleaner._format_fallback_charts(
                placements=placements,
                chart_entries=chart_entries,
                expected_chart_count=expected_chart_count,
            )

        return {
            "placements": placements,
            "charts": formatted_charts,
            "house_indices": raw_horoscope[2],
        }

    @staticmethod
    def _clean_chart_planet(text: str) -> str:
        text = ChartCleaner.clean_unicode(text)
        text = text.replace(_RETRO_SYMBOL, "").strip()
        name, _ = ChartCleaner.split_name_symbol(text)
        if name and name[0] in _PLANET_SYMBOLS_SET:
            name = name[1:].strip()
        return name

    @staticmethod
    def _clean_chart_houses(chart_houses):
        return [
            [
                ChartCleaner._clean_chart_planet(p)
                for p in house.split("\n")
                if p.strip()
            ]
            for house in chart_houses
        ]

    @staticmethod
    def _derive_chart_labels_from_placements(placements: Dict[str, str]) -> List[str]:
        derived_labels = []
        seen_labels = set()

        for key in placements:
            if "-" not in key:
                continue
            prefix, suffix = key.split("-", 1)
            if suffix not in {"Ascendant", "Lagna"}:
                continue
            if prefix in seen_labels:
                continue
            seen_labels.add(prefix)
            derived_labels.append(prefix)

        return derived_labels

    @staticmethod
    def _extract_factor(label: str) -> Optional[int]:
        if label == "Raasi":
            return 1

        match = re.match(r"D(\d+)$", label)
        if not match:
            return None
        return int(match.group(1))

    @staticmethod
    def _format_fallback_charts(
        placements: Dict[str, str],
        chart_entries,
        expected_chart_count: int,
    ) -> List[Dict[str, object]]:
        derived_labels = ChartCleaner._derive_chart_labels_from_placements(placements)
        fallback_charts = []

        for idx, chart_houses in enumerate(chart_entries):
            label = (
                derived_labels[idx]
                if idx < len(derived_labels)
                else f"chart_{idx + 1}"
            )
            fallback_charts.append(
                {
                    "factor": ChartCleaner._extract_factor(label),
                    "label": label,
                    "houses": ChartCleaner._clean_chart_houses(chart_houses),
                }
            )

        logger.warning(
            "Chart label fallback applied: expected=%d actual=%d derived_labels=%d",
            expected_chart_count,
            len(chart_entries),
            len(derived_labels),
        )
        return fallback_charts
