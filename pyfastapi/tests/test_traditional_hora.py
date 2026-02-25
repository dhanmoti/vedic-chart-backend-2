from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from main import _traditional_parasara_hora_from_rasi_positions


def test_traditional_parasara_hora_maps_only_to_cancer_and_leo():
    # [planet_id, (rasi_sign, longitude_within_sign)]
    rasi_positions = [
        ["L", (0, 10.0)],   # odd sign, first half => Leo
        [0, (0, 20.0)],      # odd sign, second half => Cancer
        [1, (1, 10.0)],      # even sign, first half => Cancer
        [2, (1, 20.0)],      # even sign, second half => Leo
    ]

    d2_chart = _traditional_parasara_hora_from_rasi_positions(rasi_positions)

    non_empty_houses = {idx for idx, house in enumerate(d2_chart) if house}
    assert non_empty_houses == {3, 4}
    assert d2_chart[4] == ["Ascendant", "Mars"]
    assert d2_chart[3] == ["Sun", "Moon"]
