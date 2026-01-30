import re

from jhora import const

class ChartCleaner:
    @staticmethod
    def clean_text(text):
        # Removes symbols like ☉, ☾, ℞ and extra newlines
        return re.sub(r'[^\x00-\x7F]+', '', text).replace('\n', ' ').strip()

    @staticmethod
    def format_response(raw_horoscope):
        """
        raw_horoscope[0]: Dict of placements
        raw_horoscope[1]: List of planet positions for D-charts
        raw_horoscope[2]: House indices
        """
        # 1. Standardize Placements
        placements = {
            ChartCleaner.clean_text(k): ChartCleaner.clean_text(v) 
            for k, v in raw_horoscope[0].items()
        }

        # 2. Structure Divisional Charts in the order used by Horoscope.get_horoscope_information().
        chart_labels = [f"D{factor}" for factor in const.division_chart_factors]
        formatted_charts = {}

        for idx, name in enumerate(chart_labels):
            if idx >= len(raw_horoscope[1]):
                break
            # Convert the list of strings into clean lists for each of the 12 houses
            formatted_charts[name] = [
                [ChartCleaner.clean_text(p) for p in house.split('\n') if p.strip()]
                for house in raw_horoscope[1][idx]
            ]

        return {
            "placements": placements,
            "charts": formatted_charts,
            "house_indices": raw_horoscope[2] # Needed for North Indian rotations
        }
