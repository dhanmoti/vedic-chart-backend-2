# Vedic Chart Backend

## Licensing & Dependencies

This project uses the Swiss Ephemeris under the Swiss Ephemeris Free License and includes PyJHora for Vedic astrology calculations.

## API

### `POST /horoscope`

Generates horoscope placements/charts and includes ascendant lord, ascendant nakshatra, and nakshatra + pada + nakshatra lord for Lagna and all supported grahas (Sun, Moon, Mars, Mercury, Jupiter, Venus, Saturn, Rahu, Ketu).

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
    "ascendant_lord": "Saturn",
    "ascendant_nakshatra": { "name": "Shatabhisha", "pada": 1, "lord": "Rahu" },
    "nakshatras": {
      "Raasi-Lagna": { "name": "Shatabhisha", "pada": 1, "lord": "Rahu" },
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

If ascendant or planet nakshatra computation cannot be completed, those specific fields are returned as `null` and the request still succeeds.

## Cache backend rollout guidance

### Cloud Run deployment (Redis/Memorystore)

For Cloud Run revisions that autoscale above a single instance, deploy with Redis as the shared cache backend:

```bash
gcloud run services update vedic-chart-backend \
  --region=YOUR_REGION \
  --set-env-vars=CACHE_BACKEND=redis,REDIS_URL=redis://YOUR_MEMORSTORE_HOST:6379
```

Use the Memorystore private endpoint for `REDIS_URL`. The service validates Redis connectivity once during startup (`PING`) and fails fast if Redis is unreachable.

### Local/dev defaults

Keep local and developer environments on in-memory caching by default:

```bash
CACHE_BACKEND=memory
```

This remains the default when `CACHE_BACKEND` is unset.

### Metrics and rollout validation

Track `GET /metrics/cache` before and after rollout and compare:

- `hit_rate`
- `requests`
- `errors`
- `backend` / `requested_backend`

A sustained higher hit rate with Redis should correspond to lower horoscope recomputation CPU cost.

### Optional L1 + L2 approach

If Redis network latency becomes a bottleneck, add a short-TTL in-process L1 cache in front of Redis L2 so hot keys are served from memory while keeping cross-instance cache consistency in Redis.
