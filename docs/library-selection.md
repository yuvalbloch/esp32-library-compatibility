# How libraries are chosen

The Arduino Library Manager lists more than 10,000 libraries. The table starts with the ones ESP32 users are most likely to look up after the 4.0 update: libraries that are **popular** and that had a **real chance of breaking**. The result is the [wave-1 list](initial-library-set.md) (62 libraries). The table will grow to about 200, then 500.

The selection is implemented in [`selection-data/select_libs.py`](../selection-data/select_libs.py). Its full output, with every score and reason, is in [`selection-data/selection.json`](../selection-data/selection.json).

## 1. Gates (yes/no filters)

| Gate | Rule | How it is checked |
|---|---|---|
| **G1. Claims ESP32 support** | The library says it runs on ESP32 | `architectures` in the Library Manager index contains `esp32` or `*` |
| **G2. Not part of the core** | WiFi, BLE, Preferences, … ship inside the core and are tested by Espressif | Name compared with the libraries bundled in cores 3.3.12 and 4.0.0 |
| **G3. Has something to compile** | Testing means compiling the library's own examples | An `examples/` folder with at least one sketch |
| **G4. Not a duplicate** | Popular libraries have many forks | Libraries providing the same main header, or forks of the same project, are grouped and the most popular copy is kept |
| **G5. Not irrelevant to ESP32** | `*` is often wrong | The source is scanned for code that only works on other chips (`avr/io.h`, `__AVR__` without an ESP32 branch) |

## 2. Scores (ranking)

Each factor is converted to a percentile rank (0–100) so that one huge number, such as a 24,000-star project, cannot dominate. The final score is the weighted average.

| Factor | Weight | Measured by |
|---|---|---|
| **S1. Stars** | 20% | GitHub stars (via the PlatformIO registry) |
| **S2. Downloads** | 15% | PlatformIO download rank (the Arduino Library Manager publishes no download counts). Unlisted libraries get a neutral score, not zero |
| **S3. Used by other libraries** | 15% | How many libraries in the index name it in `depends`. Breaking a foundation library breaks everything built on it |
| **S4. Breakage risk** | 35% | Automatic scan of the source (§3) |
| **S5. Maintained** | 10% | Time since the last release |
| **S6. Multi-chip code** | 5% | Number of chip-specific branches (`CONFIG_IDF_TARGET_ESP32S3`, …) |

Popularity (S1–S3) counts for 50% in total. Risk alone is the largest single factor, because a table where everything says "nothing changed" is less useful than one that finds what broke.

## 3. Breakage risk scan

The newest version of each candidate is downloaded and its source searched for known danger signs:

| Danger sign | Why it matters | Weight |
|---|---|---|
| Includes legacy ESP-IDF driver headers (`driver/rmt.h`, `driver/timer.h`, `driver/i2s.h`, `driver/adc.h`, …) | ESP-IDF 6 removed the legacy drivers | high |
| Uses headers removed or renamed in ESP-IDF 5–6 (e.g. `soc_memory_types.h`) | The file no longer exists | high |
| Calls mbedTLS directly | 4.0 changed the crypto layer | medium |
| Uses timer, PWM (LEDC), RMT, I²S or DMA APIs | These broke in the 2.x → 3.x transition | medium |
| Has core-version guards (`ESP_ARDUINO_VERSION`, `ESP_IDF_VERSION`) | Sensitive to core changes (and a sign of maintenance) | low |
| Only plain Arduino APIs or pure C++ | Very likely to survive | zero |

**The risk score only decides which libraries are tested first. It never decides a result.** After each wave, the scan is compared with what actually broke, and signs it missed are added.

## 4. Balance rules

- **Categories.** The list should serve everyone, not only LED users. Each category (LEDs, Displays, Sensors, Networking/Web, Bluetooth, Audio, Motors/Servos, Storage/Files, Utilities) should have at least 3 libraries; if one is short, its best candidate replaces the lowest-scoring library of an over-full category.
- **Must-include.** Libraries checked by Espressif's External Libraries Test are always included, as a calibration check against Espressif's own results. Very well-known names (FastLED, Adafruit NeoPixel, ArduinoJson, TFT_eSPI, PubSubClient, NimBLE-Arduino, ESPAsyncWebServer, WiFiManager) are always included too.
- **Never removed for passing.** "Still works on 4.0" is useful information, so passing libraries stay in the table.

## 5. Known limits

- No official download numbers exist for the Arduino Library Manager, so popularity is estimated.
- Stars favour older libraries. Newer libraries that many users switched to may rank too low; [requests](../../../issues/new?template=add-library.yml) help correct this.
- The risk scan is a heuristic. It sets the testing order only.
