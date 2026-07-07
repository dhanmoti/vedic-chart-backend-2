import importlib
from dataclasses import dataclass, field
from typing import Any, Callable, Dict

from jhora import const


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
    "lagna_kendradi_rasi": DashaSystemSpec(
        name="lagna_kendradi_rasi",
        module_path="jhora.horoscope.dhasa.raasi.lagna_kendraadhi",
        function_name="get_lagna_kendradhi_rasi_bhukthi",
        input_kind="dob_tob",
        lord_kind="rasi",
    ),
    "sudasa": DashaSystemSpec(
        name="sudasa",
        module_path="jhora.horoscope.dhasa.raasi.sudasa",
        function_name="get_dhasa_bhukthi",
        input_kind="dob_tob",
        lord_kind="rasi",
    ),
    "narayana": DashaSystemSpec(
        name="narayana",
        module_path="jhora.horoscope.dhasa.raasi.narayana",
        function_name="narayana_dhasa_for_rasi_chart",
        input_kind="dob_tob",
        lord_kind="rasi",
    ),
    "drig": DashaSystemSpec(
        name="drig",
        module_path="jhora.horoscope.dhasa.raasi.drig",
        function_name="get_dhasa_antardhasa",
        input_kind="jd",
        lord_kind="rasi",
        # Pin explicitly rather than relying on pyjhora's const.DRIG_TYPE_DEFAULT,
        # so a future pyjhora release can't silently change dasha output for this system.
        extra_kwargs={"dhasa_method": const.DRIG_TYPE.PVR_PAPER},
    ),
    "shoola": DashaSystemSpec(
        name="shoola",
        module_path="jhora.horoscope.dhasa.raasi.shoola",
        function_name="get_dhasa_bhukthi",
        input_kind="dob_tob",
        lord_kind="rasi",
    ),
    "niryaana_shoola": DashaSystemSpec(
        name="niryaana_shoola",
        module_path="jhora.horoscope.dhasa.raasi.niryaana",
        function_name="get_dhasa_bhukthi",
        input_kind="dob_tob",
        lord_kind="rasi",
    ),
}
