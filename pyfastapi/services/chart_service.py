import re
from typing import Dict, List, Optional

from jhora import const, utils

from config import _SIGN_TO_INDEX
from helpers import ChartCleaner


def parse_karaka_from_placement(placement_value: str) -> Optional[str]:
    """Extract Jaimini Karaka from placement string e.g. '... (Maitra Karaka)'."""
    m = re.search(r"\(([^)]+Karaka)\)", placement_value)
    return m.group(1) if m else None


def parse_longitude_from_placement(
    placement_value: str,
    sign_to_index: Optional[Dict[str, int]] = None,
) -> Optional[float]:
    """Parse ecliptic longitude (degrees) from a zodiac placement string.

    Accepts an optional sign_to_index map to support non-English sign names.
    Longest sign names are matched first to avoid partial matches.
    """
    effective_map = {**_SIGN_TO_INDEX, **(sign_to_index or {})}
    sorted_signs = sorted(effective_map, key=len, reverse=True)
    sign_pat = "|".join(re.escape(s) for s in sorted_signs)
    match = re.search(
        rf"({sign_pat})\s+(\d{{1,2}})\D\s*(\d{{1,2}})(?:\D\s*(\d{{1,2}}))?",
        placement_value,
    )
    if not match:
        return None

    sign_name = match.group(1)
    sign_index = effective_map[sign_name]
    degrees = int(match.group(2))
    minutes = int(match.group(3))
    seconds = int(match.group(4) or 0)
    return sign_index * 30.0 + degrees + (minutes / 60.0) + (seconds / 3600.0)


def extract_longitude_map(placements: Dict[str, str]) -> Dict[str, float]:
    """Build a normalized longitude map from raw placement strings."""
    aliases = {
        "Raasi-Lagna": ["Raasi-Ascendant", "Raasi-Lagna"],
        "Raasi-Sun": ["Raasi-Sun"],
        "Raasi-Moon": ["Raasi-Moon"],
        "Raasi-Mars": ["Raasi-Mars"],
        "Raasi-Mercury": ["Raasi-Mercury"],
        "Raasi-Jupiter": ["Raasi-Jupiter"],
        "Raasi-Venus": ["Raasi-Venus"],
        "Raasi-Saturn": ["Raasi-Saturn"],
        "Raasi-Rahu": ["Raasi-Rahu", "Raasi-Raagu"],
        "Raasi-Ketu": ["Raasi-Ketu", "Raasi-Kethu"],
    }

    longitude_map: Dict[str, float] = {}
    for normalized_label, candidates in aliases.items():
        for candidate in candidates:
            placement_value = placements.get(candidate)
            if not placement_value:
                continue
            longitude = parse_longitude_from_placement(placement_value)
            if longitude is not None:
                longitude_map[normalized_label] = longitude
                break

    rahu_longitude = longitude_map.get("Raasi-Rahu")
    ketu_longitude = longitude_map.get("Raasi-Ketu")
    if rahu_longitude is not None and ketu_longitude is None:
        longitude_map["Raasi-Ketu"] = (rahu_longitude + 180.0) % 360.0
    elif ketu_longitude is not None and rahu_longitude is None:
        longitude_map["Raasi-Rahu"] = (ketu_longitude + 180.0) % 360.0

    return longitude_map


def traditional_parasara_hora_from_rasi_positions(
    rasi_positions: List[List[object]],
    planet_names: List[str],
) -> List[List[str]]:
    """Convert rasi positions to a D2 chart using Traditional Parasara mapping."""
    d2_houses = [[] for _ in range(12)]

    for planet, (sign_index, longitude_in_sign) in rasi_positions:
        hora_sign = 3  # Moon's Hora => Cancer
        half_index = int(longitude_in_sign // 15.0)
        if (sign_index in const.odd_signs and half_index == 0) or (
            sign_index in const.even_signs and half_index == 1
        ):
            hora_sign = 4  # Sun's Hora => Leo

        if planet == "L":
            planet_name = "Ascendant"
        else:
            idx = int(planet)
            planet_name = planet_names[idx] if idx < len(planet_names) else f"Planet{idx}"

        d2_houses[hora_sign].append(planet_name)

    return d2_houses
