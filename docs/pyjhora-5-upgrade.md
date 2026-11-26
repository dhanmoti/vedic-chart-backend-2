# PyJHora 4.8.7 → 5.0.6: impact and migration

For backend and front-end developers, and for whoever signs off astrological results.

## Summary

- The JSON structure of every endpoint is unchanged. `/horoscope` gains a `D150` key in `charts` and `divisions`.
- Many display strings change. Match on `id`, `index` and `sign_index`, not on names.
- **Dasha results change.** Vimshottari and Ashtottari keep their sequence, with dates within one day. The other nine systems differ materially and **need astrological sign-off before release**.
- **All calculations now really use Lahiri.** Swiss Ephemeris keeps the ayanamsa per thread, and requests run in worker threads, so before this change they used Fagan-Bradley (about 0.88° off) on Linux. This also affected 4.8.7 in production. Every longitude, varga and dasha date served before this release may differ.
- `jaimini_karaka` now uses the rasi-chart karakas in every division (PVR §7.3.6, §8.2), and two English labels change (see below).

## How this was measured

Outputs of 4.8.7 and 5.0.6 were compared across 702 service results: 20 birth records, all 11 dasha
systems, the six languages (four of the records), both chart styles, and a two-year panchanga sweep.
The comparison covers those inputs only, and it shows what changed, not which version is astrologically correct.

## Calculation changes

| Area | Change |
|---|---|
| Planet longitudes, signs, houses, chart occupancy, ashtakavarga, the seven yogas | No change observed |
| `divisions.*.planets[].longitude_in_sign` | Differs by up to 0.0002° (now rounded from the exact value, previously cut to whole arc-seconds) |
| `divisions.*.planets[].jaimini_karaka` | Every division, D2 included, now repeats the D1 karakas (PVR §7.3.6: the Karakamsa is the navamsa sign of the rasi-chart atma karaka). D1 is unchanged |
| Dignity | Jupiter in Virgo is now `enemy` (score 1), previously `friend` (score 3) |
| Arudha | Differs for 2 of 20 births (one graha arudha, one bhava arudha). PyJHora now counts Rahu/Ketu longitude backwards when comparing co-lords |
| Panchanga `lunar_month` | `Month0` is fixed (now `Phalguna`). PyJHora rewrote the calculation, so some dates near a month boundary also move (seen: Ashadha → Jyeshtha, Chaitra → Phalguna) |
| Vimshottari `balance` | May differ by one day |

### Dasha systems

Pinned settings follow PVR Narasimha Rao's *Vedic Astrology: An Integrated Approach* (project decision, 2026-11-26): Lahiri ayanamsa, solar (mean sidereal) year of 365.256364 days (PVR ch. 16), Kalachakra "PVR / Sanjay Rath", Drig "PVR book", Narayana "PVR book", Sudasa "PVR book".

Sudasa and Lagna Kendradi rasi dasa get a second cycle that PyJHora 5 dropped: each rasi's second-cycle period is 12 years minus its first-cycle period (PVR §18.2 note 2, §19.2(6), §20.2(6)). The table below was measured before these three changes; the rows for `drig`, `lagna_kendradi_rasi` and `sudasa` need re-measuring.
"Within 1 day" is the share of old pratyantardasha rows whose lord sequence still exists with a start date within one day.

| System | Sequence | Within 1 day | Largest shift |
|---|---|---|---|
| `vimshottari` | Same | 100% | 1 day |
| `ashtottari` | Same | 100% | 1 day |
| `shoola` | Same lords | 94% | about 4.9 years |
| `drig` | PVR book method; re-measure | – | – |
| `narayana` | Same lords | 26% | about 12 years |
| `niryaana_shoola` | Same lords, fewer periods (24 → 17 mahadashas in a sampled chart) | 14% | about 189 years |
| `yogini` | Same lords | 4% | about 15 months |
| `lagna_kendradi_rasi` | 24 periods again (two cycles); re-measure | – | – |
| `chara` | 99% of sequences present; some charts have fewer periods | under 1% | about 12 years |
| `sudasa` | 24 periods again (two cycles), PVR book method; re-measure | – | – |
| `kalachakra` | 37% of sequences present | 0% | about 87 years |

Large shifts mostly come from periods moving between cycles. Pinning 5.0.6's "true sidereal" year
instead was rejected: it moves Vimshottari dates by up to 5 days.

## Front-end migration

### What to change

1. Identify planets by `id` (7 = Rahu, 8 = Ketu), nakshatras by `index` (1–28), signs by `sign_index`.
   Panchanga has `tithi_index`, `nakshatra_index`, `yoga_index` and `karana_index`.
2. Where only a string exists (`charts` house arrays, dasha `lord`, `varsha.chart`, gochar `name` and
   `nakshatra`, panchanga `vaara` and `lunar_month`), accept both old and new spellings until the backend is released.
3. Render, or ignore, the new `D150` chart.
4. Stop relying on `chart_style` to change English names. `north` and `south` now return identical names;
   the field is still accepted and echoed in `meta`. To keep Tamil-style English on the south layout, map it
   in the client using the tables below.
5. Expect panchanga `vaara`, `yoga` and `lunar_month` in the requested language (previously always English).
   For `ta` and `ml`, PyJHora's month list uses the regional solar month names.
6. Clear stored dasha results and any cached labels.

`/languages` still lists `en`, `hi`, `ta`, `te`, `ka`, `ml`. Any other `language` value is treated as `en`.

### Non-English strings

Planet, sign, nakshatra, tithi and karana changes are listed below. They are upstream spelling corrections,
plus a Hindi tithi list that had empty entries, so 4.8.7 returned the wrong name for later tithis.

| Language | Field | Index (1-based) | Old | New |
|---|---|---|---|---|
| `hi` | nakshatra | 5 | म्रृगशीर्षा | मृगशीर्षा |
| `hi` | nakshatra | 9 | अश्लेषा | आश्लेषा |
| `hi` | tithi | 11 | (empty) | एकादशी |
| `hi` | tithi | 12 | एकादशी | द्वादशी |
| `hi` | tithi | 13 | द्वादशी | त्रयोदशी |
| `hi` | tithi | 14 | त्रयोदशी | चतुर्दशी |
| `hi` | tithi | 15 | चतुर्दशी | पूर्णिमा |
| `hi` | tithi | 16 | पूर्णिमा | प्रतिपदा |
| `hi` | tithi | 17 | प्रतिपदा | द्वितीया |
| `hi` | tithi | 18 | द्वितीया | तृतीया |
| `hi` | tithi | 19 | तृतीया | चतुर्थी |
| `hi` | tithi | 20 | चतुर्थी | पञ्चमी |
| `hi` | tithi | 21 | पञ्चमी | षष्ठी |
| `hi` | tithi | 22 | षष्ठी | सप्तमी |
| `hi` | tithi | 23 | सप्तमी | अष्टमी |
| `hi` | tithi | 24 | अष्टमी | नवमी |
| `hi` | tithi | 25 | नवमी | दशमी |
| `hi` | tithi | 26 | दशमी | एकादशी |
| `hi` | tithi | 27 | (empty) | द्वादशी |
| `hi` | tithi | 28 | एकादशी | त्रयोदशी |
| `hi` | tithi | 29 | द्वादशी | चतुर्दशी |
| `hi` | tithi | 30 | त्रयोदशी | अमावस्या |
| `hi` | karana | 1 | किमस्तुग्ना | किंस्तुघ्न |
| `hi` | karana | 2 | बावा | बव |
| `hi` | karana | 5 | तैतिला | तैतिल |
| `hi` | karana | 6 | गारा | गर |
| `hi` | karana | 7 | वनिजा | वणिज |
| `hi` | karana | 8 | विष्टी (भद्रा) | विष्टि (भद्रा) |
| `hi` | karana | 58 | शकुना | शकुनि |
| `hi` | karana | 59 | चतुष्पाद | चतुष्पद |
| `hi` | karana | 60 | नागा | नाग |
| `ka` | karana | 1 | ಕಿಮಸ್ತುಗ್ನ | ಕಿಂಸ್ತುಘ್ನ |
| `ka` | karana | 3 | ಬಲವ | ಬಾಲವ |
| `ka` | karana | 7 | ವನಿಜ | ವಣಿಜ |
| `ka` | karana | 12 | ತಟಿಲ | ತೈತಿಲ |
| `ka` | karana | 13 | ಗಾರ | ಗರ |
| `ka` | karana | 15 | ವಿಷ್ಟಿ (ಭದ್ರ) | ವಿಷ್ಟಿ(ಭದ್ರ) |
| `ka` | karana | 16 | ಬಾವ | ಬವ |
| `ka` | karana | 22 | ವಿಷ್ಟಿ ( ಭದ್ರ) | ವಿಷ್ಟಿ (ಭದ್ರ) |
| `ka` | karana | 24 | ಬಲವ್ | ಬಾಲವ |
| `ka` | karana | 32 | ಕಾಗೆ | ಕೌಲವ |
| `ka` | karana | 58 | ಶಕುನ | ಶಕುನಿ |

Karaka labels now follow BPHS 32.13-17 and PVR §8.2 Table 13 in every language. The 4th karaka is Matri (mother), where PyJHora says Maitra (friend), and the 8th is Dara (spouse). English: `Maitra Karaka` → `Matri Karaka`, `Dhatha Karaka` → `Dara Karaka`. Positions 4 and 8 in `ta`, `te`, `ka` and `ml` change the same way.

Hindi karaka labels (old 4.8.7 → new):

| Old | New |
|---|---|
| आत्मा कारक | आत्मकारक |
| अमात्य कारक | अमात्यकारक |
| भ्रात्रि कारक | भ्रातृकारक |
| मैत्र कारक | मातृकारक |
| पितृ कारक | पितृकारक |
| पुत्र कारक | पुत्रकारक |
| ज्ञानी कारक | ज्ञातिकारक |
| धत्था कारक | दारकारक |

### English strings

Dasha `lord` values change only for Rahu and Ketu. Indexes below are 1-based except where noted;
repeated names are listed once.

#### Planets, `south`

| `id` | Old | New |
|---|---|---|
| 7 | Raagu | Rahu |
| 8 | Kethu | Ketu |

#### Nakshatra, `south`

| Index | Old | New |
|---|---|---|
| 1 | Aswini | Ashwini |
| 3 | Karthigai | Krittika |
| 5 | Mrigasheesham | Mrigashira |
| 6 | Thiruvaathirai | Ardra |
| 7 | Punarpoosam | Punarvasu |
| 8 | Poosam | Pushya |
| 9 | Aayilyam | Ashlesha |
| 10 | Makam | Magha |
| 11 | Pooram | Purva Phalguni |
| 12 | Uthiram | Uttara Phalguni |
| 13 | Hastham | Hasta |
| 14 | Chithirai | Chitra |
| 15 | Swaathi | Swati |
| 16 | Visaakam | Vishakha |
| 17 | Anusham | Anuradha |
| 18 | Kaettai | Jyeshtha |
| 19 | Moolam | Mula |
| 20 | Pooraadam | Purva Ashadha |
| 21 | Uthiraadam | Uttara Ashadha |
| 22 | Thiruvonam | Shravana |
| 23 | Avittam | Dhanishta |
| 24 | Sadhayam | Shatabhisha |
| 25 | Poorattathi | Purva Bhadrapada |
| 26 | Uthirattathi | Uttara Bhadrapada |
| 27 | Revathi | Revati |
| 28 | Abhijith | Abhijit |

#### Nakshatra, `north`

| Index | Old | New |
|---|---|---|
| 1 | Ashvini | Ashwini |
| 5 | Mrigashirsha | Mrigashira |
| 15 | Svati | Swati |
| 20 | Purvashadha | Purva Ashadha |
| 21 | Uttarashadha | Uttara Ashadha |
| 23 | Dhanishtha | Dhanishta |

#### Tithi

| Index | Old | New |
|---|---|---|
| 1 | Prathamai | Pratipada |
| 2 | Thuthiyai | Dwitiya |
| 3 | Thiruthiyai | Tritiya |
| 4 | Chathurthi | Chaturthi |
| 6 | Shasti | Shashthi |
| 7 | Sapthami | Saptami |
| 8 | Astami | Ashtami |
| 10 | Dhasami | Dashami |
| 11 | Egadhasi | Ekadashi |
| 12 | Dhuvadhasi | Dwadashi |
| 13 | Thirayodasi | Trayodashi |
| 14 | Sathuradasi | Chaturdashi |
| 15 | Pournami | Purnima |
| 16 | Pirathamai | Pratipada |
| 30 | Amavasai | Amavasya |

#### Karana

| Index | Old | New |
|---|---|---|
| 1 | Kimstugna | Kimstughna |
| 3 | Baalava | Balava |
| 4 | kaulava | Kaulava |
| 15 | Vishti(Bhadra) | Vishti (Bhadra) |
| 58 | Sakuna | Shakuni |

#### Yoga

| Index | Old | New |
|---|---|---|
| 7 | Sukarman | Sukarma |

#### Lunar month

| Index | Old | New |
|---|---|---|
| 8 | Kartika | Karttika |


## Backend changes

- **Install:** PyJHora 5.0.6 pins PyQt6 and older `numpy`, `pytz` and `timezonefinder`. It is installed with
  `--no-deps` from `requirements-nodeps.txt`; `pip check` reports those pins as unmet.
  Existing local environments need `pip install --no-deps -r requirements-nodeps.txt`.
- **`/horoscope`:** charts come from `charts.divisional_chart()`. In 5.0.6, `jhora.horoscope.main.Horoscope`
  fails (`lunar_month` unpacking, an undefined `kshaya_maasa`, a `tri_sphuta()` signature mismatch) and
  `jhora.horoscope.info.Horoscope` returns only D1 and D9.
- **Dasha:** every system calls `get_dhasa_antardhasa(dob, tob, place, ...)`.
- **Settings:** 5.0.6's `jhora/__init__.py` names `initialize_runtime` without calling it, so its settings files
  are not applied on import. If upstream fixes that, library defaults will change; `tests/test_pyjhora_compat.py`
  checks the settings this service pins.
- **Thread state:** every service entry point is wrapped in `config.with_engine_state`, which sets the ayanamsa and ephemeris path in the calling thread. `tests/test_pyjhora_compat.py::test_worker_thread_computes_with_lahiri` guards it.
- **Cache:** key prefixes are `:v3`. Deployments that set `*_CACHE_KEY_PREFIX` keep their own value, so bump them too.

## Release and rollback

1. Astrological sign-off on dasha, dignity, arudha and lunar month changes (karaka and dasha-method conventions follow PVR's book).
2. Release a front end that accepts both spellings.
3. Build the image and smoke-test it, then deploy.

Roll back by redeploying the previous revision, or by reverting the merge.

## Known issues not addressed here

- **Concurrent requests in different languages can return mixed-language or wrong results.** PyJHora keeps the
  language in global state. This happens on both 4.8.7 and 5.0.6; English-only concurrency matched serial
  results in testing. The deploy script's concurrency of 2 allows it. Fix separately.
- `suppress_third_party_stdout()` is not thread-safe and can leave stdout redirected after concurrent requests
  (also present before).
