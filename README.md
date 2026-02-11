# Vedic Chart Backend

## Licensing & Dependencies

This project uses the Swiss Ephemeris under the Swiss Ephemeris Free License and includes PyJHora for Vedic astrology calculations.

## API

### `POST /horoscope`

Generates horoscope placements/charts and includes nakshatra + pada + nakshatra lord for all supported grahas (Sun, Moon, Mars, Mercury, Jupiter, Venus, Saturn, Rahu, Ketu).

#### Response shape (200)

```json
{
  "status": "success",
  "data": {
    "placements": {
      "Raasi-Lagna": "Aquarius",
      "Raasi-Sun": "Capricorn"
    },
    "charts": {
      "D1": [
        ["Lagna"],
        ["Sun"]
      ]
    },
    "house_indices": [10, 11, 12, 1, 2, 3, 4, 5, 6, 7, 8, 9],
    "nakshatras": {
      "Raasi-Sun": { "name": "Uttara Ashadha", "pada": 3, "lord": "Sun" },
      "Raasi-Moon": { "name": "Shravana", "pada": 2, "lord": "Moon" },
      "Raasi-Mars": { "name": "Chitra", "pada": 1, "lord": "Mars" },
      "Raasi-Mercury": { "name": "Dhanishta", "pada": 4, "lord": "Mars" },
      "Raasi-Jupiter": { "name": "Punarvasu", "pada": 2, "lord": "Jupiter" },
      "Raasi-Venus": { "name": "Purva Ashadha", "pada": 1, "lord": "Venus" },
      "Raasi-Saturn": { "name": "Shatabhisha", "pada": 2, "lord": "Rahu" },
      "Raasi-Rahu": { "name": "Ashwini", "pada": 4, "lord": "Ketu" },
      "Raasi-Ketu": { "name": "Swati", "pada": 2, "lord": "Rahu" }
    }
  }
}
```

If a planet's nakshatra computation cannot be completed, that specific `Raasi-*` field is returned as `null` and the request still succeeds.
