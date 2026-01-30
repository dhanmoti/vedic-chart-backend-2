import re

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

        # 2. Structure Divisional Charts (D1, D9, D10 as seen in wireframe)
        # Mapping based on common jhora output order
        chart_map = {0: "D1", 8: "D9", 9: "D10"} 
        formatted_charts = {}

        for idx, name in chart_map.items():
            if idx < len(raw_horoscope[1]):
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