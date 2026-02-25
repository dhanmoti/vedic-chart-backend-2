import logging
import re
from typing import Dict, List, Optional

from jhora import const


logger = logging.getLogger("uvicorn.error")


class ChartCleaner:
    @staticmethod
    def clean_text(text: str) -> str:
        return (
            re.sub(r"[^\x00-\x7F]+", "", text)
            .replace("\n", " ")
            .strip()
        )

    @staticmethod
    def format_response(raw_horoscope):
        placements = {
            ChartCleaner.clean_text(k): ChartCleaner.clean_text(v)
            for k, v in raw_horoscope[0].items()
        }

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
    def _clean_chart_houses(chart_houses):
        return [
            [
                ChartCleaner.clean_text(p)
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
