# Vedic Chart Backend

## Licensing & Dependencies

This project uses the Swiss Ephemeris under the Swiss Ephemeris Free License and includes PyJHora for Vedic astrology calculations.

---

## API

### `POST /horoscope`

Generates a full Vedic horoscope: per-planet data (sign, house, longitude, dignity, retrograde, nakshatra, symbol, color), ascendant details, D1–D60 divisional charts, and a house-to-sign mapping for rendering.

#### Request body

```json
{
  "dob":         "YYYY-MM-DD",
  "time":        "HH:MM",
  "lat":         13.08,
  "lng":         80.27,
  "tz":          5.5,
  "language":    "en",
  "chart_style": "south"
}
```

| Field | Type | Required | Default | Notes |
|---|---|---|---|---|
| `dob` | string | yes | — | `YYYY-MM-DD`; cannot be a future date |
| `time` | string | yes | — | 24-hour `HH:MM`, 00:00–23:59 |
| `lat` | float | yes | — | −90 to 90 |
| `lng` | float | yes | — | −180 to 180 |
| `tz` | float | yes | — | UTC offset, −14 to 14 |
| `language` | string | no | `"en"` | `en`, `hi`, `ta`, `te`, `ka`, `ml` |
| `chart_style` | string | no | `"south"` | `"south"` or `"north"` |

##### `chart_style` and naming

| `chart_style` | `language` | Planet names | Sign names | Nakshatra names |
|---|---|---|---|---|
| `south` | `en` | Tamil-English ("Raagu", "Kethu") | Western English | Tamil-style ("Aswini", "Karthigai") |
| `north` | `en` | Western English + fixed ("Rahu", "Ketu") | Western English | Sanskrit ("Ashvini", "Krittika") |
| any | `hi` | Hindi Devanagari | Hindi Devanagari | Hindi Devanagari |
| any | `ta` | Tamil script | Tamil script | Tamil script |

`chart_style` is echoed in `data.meta` so the client knows which rendering convention to apply. `house_signs` enables both north (house-fixed diamond) and south (sign-fixed grid) layouts from the same data.

---

#### Response shape (200)

```json
{
  "status": "success",
  "data": {
    "meta": {
      "chart_style": "south",
      "language":    "en"
    },
    "ascendant": {
      "sign":              "Aquarius",
      "sign_index":        10,
      "sign_symbol":       "♒",
      "longitude":         315.24,
      "longitude_in_sign": 15.24,
      "lord":              "Saturn",
      "lord_symbol":       "♄",
      "nakshatra": {
        "name":        "Sadhayam",
        "index":       24,
        "pada":        1,
        "lord":        "Raagu",
        "lord_symbol": "☊"
      }
    },
    "planets": [
      {
        "id":                0,
        "name":              "Sun",
        "symbol":            "☉",
        "color":             "sun_fiery_orange",
        "sign":              "Capricorn",
        "sign_index":        9,
        "sign_symbol":       "♑︎",
        "house":             12,
        "longitude":         280.5,
        "longitude_in_sign": 10.5,
        "is_retrograde":     false,
        "daily_motion":      0.986,
        "dignity": {
          "status": "debilitated",
          "score":  0,
          "label":  "Neecham/Defibilated"
        },
        "nakshatra": {
          "name":        "Uthiraadam",
          "index":       21,
          "pada":        3,
          "lord":        "Sun",
          "lord_symbol": "☉"
        }
      }
    ],
    "charts": {
      "D1":  [["Lagna", "Sun"], [], [], ["Moon"], [], [], [], [], [], [], [], []],
      "D2":  [[], [], [], [], [], [], [], [], [], [], [], []],
      "D9":  [[], [], [], [], [], [], [], [], [], [], [], []],
      "D60": [[], [], [], [], [], [], [], [], [], [], [], []]
    },
    "house_signs": [10, 11, 0, 1, 2, 3, 4, 5, 6, 7, 8, 9]
  }
}
```

##### `planets` — field reference

| Field | Type | Description |
|---|---|---|
| `id` | int | Planet index: 0=Sun, 1=Moon, 2=Mars, 3=Mercury, 4=Jupiter, 5=Venus, 6=Saturn, 7=Rahu, 8=Ketu |
| `name` | string | Planet name in the requested language/style |
| `symbol` | string | Unicode astrological symbol (☉ ☾ ♂ ☿ ♃ ♀ ♄ ☊ ☋) |
| `color` | string | Color code key for frontend theming — see table below |
| `sign` | string | Zodiac sign name |
| `sign_index` | int | Sign index 0 (Aries) – 11 (Pisces) |
| `sign_symbol` | string | Unicode zodiac symbol |
| `house` | int | House number 1–12 counted from ascendant |
| `longitude` | float | Absolute sidereal longitude 0–360° |
| `longitude_in_sign` | float | Degrees within the sign 0–30° |
| `is_retrograde` | bool | `true` if retrograde; always `true` for Rahu and Ketu |
| `daily_motion` | float | Absolute daily motion in degrees |
| `dignity.status` | string | `exalted`, `own_sign`, `moolatrikona`, `friend`, `neutral`, `enemy`, or `debilitated` |
| `dignity.score` | int | Strength score 0 (debilitated) – 5 (own sign) |
| `dignity.label` | string | Human-readable dignity label |
| `nakshatra.name` | string | Nakshatra name |
| `nakshatra.index` | int | Nakshatra index 1–28 |
| `nakshatra.pada` | int | Quarter 1–4 |
| `nakshatra.lord` | string | Nakshatra ruling planet name |
| `nakshatra.lord_symbol` | string | Ruling planet Unicode symbol |

##### Planet color codes

| `color` code | Planet | Tone |
|---|---|---|
| `sun_fiery_orange` | Sun | Bright fiery orangish-red / golden copper |
| `moon_pearl_white` | Moon | Milky white / translucent silver |
| `mars_blood_red` | Mars | Deep maroon / blood-red |
| `mercury_emerald_green` | Mercury | Vibrant grass green / deep emerald |
| `jupiter_honey_gold` | Jupiter | Bright yellow / mustard / rich honey gold |
| `venus_pastel_pink` | Venus | Shining white / soft pink / pastels |
| `saturn_dark_indigo` | Saturn | Jet black / charcoal grey / deep navy blue |
| `rahu_smoke_grey` | Rahu | Smoke grey / metallic blue / dark blackish-brown |
| `ketu_ash_grey` | Ketu | Ash grey / checkered / mottled |

##### `charts`

Dictionary keyed `D1`–`D60` (23 divisional charts). Each value is a 12-element array (one per house) where each element is a list of planet name strings in that house. D2 (Hora) uses the Traditional Parasara method.

Supported divisional chart factors: `1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 16, 20, 24, 27, 30, 40, 45, 60, 81, 108, 144`.

##### `house_signs`

12-element array. `house_signs[i]` is the sign index (0=Aries … 11=Pisces) of house `i+1`.

- **South Indian** (sign-fixed grid): each sign has a fixed cell; `house_signs` tells you which house belongs to which cell.
- **North Indian** (house-fixed diamond): use the chart house arrays directly; `house_signs` provides the sign label for each cell.

---

### `POST /dasha`

Generates the Vimshottari dasha timeline: three levels (mahadasha → antardasha → pratyantardasha) with start dates. Uses the same request body as `/horoscope`.

#### Response shape (200)

```json
{
  "status": "success",
  "data": {
    "balance": { "years": 3, "months": 7, "days": 12 },
    "dashas": [
      {
        "lord": "Moon",
        "start_date": "1990-01-01",
        "antardashas": [
          {
            "lord": "Moon",
            "start_date": "1990-01-01",
            "pratyantardashas": [
              { "lord": "Moon", "start_date": "1990-01-01" }
            ]
          }
        ]
      }
    ]
  }
}
```

---

### `GET /`

Health check. Returns `{"status": "online"}`. No authentication required.

### `GET /metrics/cache`

Returns cache statistics for horoscope and dasha caches. No authentication required.

```json
{
  "horoscope_cache": {
    "hits": 120, "misses": 30, "writes": 30,
    "errors": 0, "requests": 150, "hit_rate": 0.8,
    "config": {
      "ttl_seconds": 900, "max_entries": 1024,
      "lat_lng_precision": 2, "tz_precision": 2,
      "key_prefix": "horoscope:v1"
    }
  },
  "dasha_cache": { "...": "..." }
}
```

---

## Authentication

All computation endpoints (`/horoscope`, `/dasha`) require a Firebase App Check token:

```
X-Firebase-AppCheck: <token>
```

Missing or invalid token → `401 Unauthorized`.

---

## Cache

In-process TTL-based in-memory cache per endpoint. Cache keys include `dob`, `time`, `lat`/`lng` (rounded), `tz`, `language`, and `chart_style`.

```bash
CACHE_TTL_SECONDS=900
CACHE_MAX_ENTRIES=1024
CACHE_LAT_LNG_PRECISION=2
CACHE_TZ_PRECISION=2
CACHE_KEY_PREFIX=horoscope:v1
DASHA_CACHE_KEY_PREFIX=dasha:v1
```
