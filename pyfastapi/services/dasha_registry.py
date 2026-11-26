import importlib
from dataclasses import dataclass, field
from types import ModuleType
from typing import Any, Callable, Dict

from jhora import const


@dataclass(frozen=True)
class DashaSystemSpec:
    name: str
    module_path: str
    function_name: str
    lord_kind: str  # "planet" | "rasi"
    extra_kwargs: Dict[str, Any] = field(default_factory=dict)
    # Append a Narayana-style second cycle (12 years minus each first-cycle period).
    # PyJHora 5 returns only one cycle for some rasi dasas.
    second_cycle: bool = False

    @property
    def module(self) -> ModuleType:
        return importlib.import_module(self.module_path)

    @property
    def function(self) -> Callable:
        return getattr(self.module, self.function_name)


DASHA_SYSTEMS: Dict[str, DashaSystemSpec] = {
    "ashtottari": DashaSystemSpec(
        name="ashtottari",
        module_path="jhora.horoscope.dhasa.graha.ashtottari",
        function_name="get_dhasa_antardhasa",
        lord_kind="planet",
    ),
    "yogini": DashaSystemSpec(
        name="yogini",
        module_path="jhora.horoscope.dhasa.graha.yogini",
        function_name="get_dhasa_antardhasa",
        lord_kind="planet",
    ),
    "kalachakra": DashaSystemSpec(
        name="kalachakra",
        module_path="jhora.horoscope.dhasa.raasi.kalachakra",
        function_name="get_dhasa_antardhasa",
        lord_kind="rasi",
        # pyjhora 5 changed the default method; this keeps the one used before.
        extra_kwargs={"dhasa_method": const.KALACHAKRA_TYPE.PVR_SANJAY_RATH},
    ),
    "chara": DashaSystemSpec(
        name="chara",
        module_path="jhora.horoscope.dhasa.raasi.chara",
        function_name="get_dhasa_antardhasa",
        lord_kind="rasi",
    ),
    "lagna_kendradi_rasi": DashaSystemSpec(
        name="lagna_kendradi_rasi",
        module_path="jhora.horoscope.dhasa.raasi.lagna_kendraadhi",
        function_name="get_dhasa_antardhasa",
        lord_kind="rasi",
        # Ref: PVR, Vedic Astrology: An Integrated Approach §19.2(6): periods "are found just
        # like in Narayana dasa", which has a second cycle (§18.2, special note 2).
        second_cycle=True,
    ),
    "sudasa": DashaSystemSpec(
        name="sudasa",
        module_path="jhora.horoscope.dhasa.raasi.sudasa",
        function_name="get_dhasa_antardhasa",
        lord_kind="rasi",
        # Ref: PVR §20.2 (the book's method) and §20.3 ("Capricorn dasa in the second cycle").
        extra_kwargs={"dhasa_method": const.SUDASA_METHOD.PVR_BOOK},
        second_cycle=True,
    ),
    "narayana": DashaSystemSpec(
        name="narayana",
        module_path="jhora.horoscope.dhasa.raasi.narayana",
        function_name="narayana_dhasa_for_rasi_chart",
        lord_kind="rasi",
        # Ref: PVR ch. 18. Pinned so a library default change cannot move results.
        extra_kwargs={"dhasa_method": const.NARAYANA_OPTION.PVR_BOOK},
    ),
    "drig": DashaSystemSpec(
        name="drig",
        module_path="jhora.horoscope.dhasa.raasi.drig",
        function_name="get_dhasa_antardhasa",
        lord_kind="rasi",
        # Ref: PVR ch. 21. The project follows PVR's book (decision 2026-11-26), so this is
        # pinned to PVR_BOOK rather than PyJHora's default PVR_PAPER.
        extra_kwargs={"dhasa_method": const.DRIG_TYPE.PVR_BOOK},
    ),
    "shoola": DashaSystemSpec(
        name="shoola",
        module_path="jhora.horoscope.dhasa.raasi.shoola",
        function_name="get_dhasa_antardhasa",
        lord_kind="rasi",
    ),
    "niryaana_shoola": DashaSystemSpec(
        name="niryaana_shoola",
        module_path="jhora.horoscope.dhasa.raasi.niryaana",
        function_name="get_dhasa_antardhasa",
        lord_kind="rasi",
    ),
}
