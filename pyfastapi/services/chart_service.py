from typing import List

from jhora import const


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
