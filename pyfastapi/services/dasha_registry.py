import importlib
from dataclasses import dataclass, field
from typing import Any, Callable, Dict


@dataclass(frozen=True)
class DashaSystemSpec:
    name: str
    module_path: str
    function_name: str
    input_kind: str  # "jd" | "dob_tob"
    lord_kind: str  # "planet" | "rasi"
    extra_kwargs: Dict[str, Any] = field(default_factory=dict)

    @property
    def function(self) -> Callable:
        module = importlib.import_module(self.module_path)
        return getattr(module, self.function_name)


DASHA_SYSTEMS: Dict[str, DashaSystemSpec] = {
    "ashtottari": DashaSystemSpec(
        name="ashtottari",
        module_path="jhora.horoscope.dhasa.graha.ashtottari",
        function_name="get_ashtottari_dhasa_bhukthi",
        input_kind="jd",
        lord_kind="planet",
    ),
    "yogini": DashaSystemSpec(
        name="yogini",
        module_path="jhora.horoscope.dhasa.graha.yogini",
        function_name="get_dhasa_bhukthi",
        input_kind="dob_tob",
        lord_kind="planet",
    ),
    "kalachakra": DashaSystemSpec(
        name="kalachakra",
        module_path="jhora.horoscope.dhasa.raasi.kalachakra",
        function_name="get_dhasa_bhukthi",
        input_kind="dob_tob",
        lord_kind="rasi",
    ),
    "chara": DashaSystemSpec(
        name="chara",
        module_path="jhora.horoscope.dhasa.raasi.chara",
        function_name="get_dhasa_antardhasa",
        input_kind="dob_tob",
        lord_kind="rasi",
    ),
}
