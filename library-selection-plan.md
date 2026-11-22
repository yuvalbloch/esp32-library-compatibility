# Plan: choosing which libraries go into the compatibility table

_Written 2026-11-21 for the Wild West project #1 (ESP32 compatibility table). Written for a non-technical approver: every technical idea has a "simple words" note._

---

## 1. The goal

Pick the **top 50 libraries** (later 200, then 500) that the table should test first.

A good list answers one question: **"Which libraries will the most ESP32 users look up after the 4.0 update?"**

That means a library should be in the table if:

1. **Many people use it** (popularity), and
2. **There is a real chance it broke** (risk), so the answer is actually news.

A library everyone uses that cannot break (for example, a pure math library) is still worth including, but it is less urgent than a popular library that controls LEDs or timers.

---

## 2. The factors

There are two kinds of factors: **gates** (yes/no filters that remove libraries) and **scores** (numbers that rank the libraries that remain).

### 2.1 Gates: who is allowed in at all

| Gate | Simple words | How I check it |
|---|---|---|
| **G1. Claims to support ESP32** | The library says it works on ESP32 | The `architectures` field in the official library list contains `esp32` or `*` (meaning "everything") |
| **G2. Not part of the core itself** | Some libraries (WiFi, BLE, Preferences) come inside the ESP32 package. Espressif tests those already | Compare the name against the list of libraries bundled with core 3.3.12 and 4.0.0 |
| **G3. Has something we can compile** | We test by compiling the library's own example programs. No examples = nothing to test | The downloaded library has an `examples/` folder with at least one sketch |
| **G4. Not a duplicate** | Popular libraries often have many copies (forks) under slightly different names | Group libraries that provide the same main header file or point to forks of the same project; keep the most popular copy (keep a second copy only if it is also very popular) |
| **G5. Not ESP32-irrelevant** | The `*` label is often wrong. A library made only for a different chip (e.g. AVR registers) is noise | Scan the source for code that only works on other chips (`avr/io.h`, `__AVR__` without any ESP32 branch) |

G1 is a weak filter (many libraries say `*` without meaning it), so G5 exists to catch the obvious mistakes.

### 2.2 Scores: ranking who goes first

| Factor | Weight | Simple words | How I measure it |
|---|---|---|---|
| **S1. GitHub stars** | 20% | How many people "bookmarked" the project. A rough fame score | GitHub API, using the repository link stored in the library list |
| **S2. Downloads** | 15% | How many people actually install it | The Arduino Library Manager does **not** publish download counts. The PlatformIO registry (the other popular tool) does show download statistics, so I use that where the library is listed there. Libraries not listed there get a neutral score, not zero |
| **S3. Used by other libraries** | 15% | If 30 other libraries depend on this one, breaking it breaks all 30. These are "foundation" libraries | Count how many libraries in the official list name it in their `depends` field |
| **S4. Breakage risk** | 35% | Does the code touch the parts of ESP32 that changed in 4.0? This is the factor that makes the table useful, because it points at the libraries whose answer is most likely "it broke" | Automatic scan of the library's source code (details in 2.3) |
| **S5. Recently maintained** | 10% | Is someone still taking care of it? | Date of the last release and last code change on GitHub |
| **S6. Multi-chip interest** | 5% | Does the library try to support several ESP32 chips? Those are more likely to have chip-specific code that can break | Count chip names like `CONFIG_IDF_TARGET_ESP32S3` in the source |

**Why risk has the largest single weight:** popularity is split across three signals (S1–S3 = 50% together), so popularity still counts most overall. Risk alone is 35% because a table full of "✅ nothing changed" is less valuable than one that finds the breaks.

**How the numbers are combined:** stars and downloads differ hugely (one library has 6,000 stars, most have 20). To stop one giant number from deciding everything, each factor is turned into a **rank from 0 to 100** ("this library is more popular than 90% of the others" = 90). Then the weighted average is the final score.

### 2.3 How breakage risk (S4) is measured

I download the latest version of each library and search its code for known danger signs. Each sign adds points:

| Danger sign | Simple words | Points |
|---|---|---|
| Includes ESP-IDF driver headers directly (`driver/rmt.h`, `driver/timer.h`, `driver/ledc.h`, `driver/i2s.h`, `driver/adc.h`) | It skips the safe Arduino layer and talks to the chip's internals, which 4.0 changed | high |
| Uses headers known to be renamed or removed in ESP-IDF 6 (e.g. `soc_memory_types.h`) | It uses a file that no longer exists | high |
| Calls the crypto library (`mbedtls_...`) directly | 4.0 changed the crypto layer | medium |
| Uses timers, PWM (`ledc...`), RMT, I²S or DMA functions | These are the hardware parts that broke last time | medium |
| Has version checks like `ESP_ARDUINO_VERSION` | Someone already adapted it once. It shows the library is sensitive to core changes (and also that it is maintained) | low |
| Only uses plain Arduino functions or pure C++ | Very likely to survive | zero |

The list of danger signs starts from the 2.x → 3.x lessons and the ESP-IDF 6.0 migration guide, and it gets better once the first compile results come in (see step 7).

### 2.4 Category balance (a rule, not a weight)

The table should be useful to everyone, not only to LED hobbyists. After ranking, I check the top 50 against these categories and make sure each has at least 3 libraries:

LEDs · Displays · Sensors · Networking/Web · Bluetooth · Audio · Motors/Servos · Storage/Files · Utilities (JSON, time, etc.)

If a category is missing, the best-scoring library in that category replaces the lowest-scoring library in an over-full category.

### 2.5 Must-include list

A short hand-picked list goes in no matter what the score says:

- **The ~10 libraries Espressif already tests.** They act as a calibration check: if my results disagree with Espressif's, something is wrong with my setup.
- **Well-known names** a user would expect to see (FastLED, Adafruit NeoPixel, ArduinoJson, TFT_eSPI, PubSubClient, NimBLE-Arduino, ESPAsyncWebServer, WiFiManager). If the scoring does not rank these high on its own, that is a sign the scoring is broken, and I fix the scoring rather than only forcing them in.

---

## 3. Step-by-step plan

| Step | What happens | Output you will see |
|---|---|---|
| **1. Download the universe** | Download the official Arduino library list (`library_index.json`, all ~7,000+ libraries) | Count of libraries |
| **2. Apply gates G1–G2** | Cheap filters using only the list | "X of Y libraries remain" |
| **3. Collect popularity data (S1–S3)** | GitHub stars, PlatformIO downloads, dependency counts | A spreadsheet with numbers per library |
| **4. Take the top ~300 by popularity and download them** | Only these get the expensive code scan | — |
| **5. Apply gates G3–G5 and measure risk (S4–S6)** | Scan each downloaded library | Risk score + the reason ("uses driver/rmt.h") |
| **6. Combine scores, apply category balance and must-include** | Final ranking | **Ranked list of 50 with one-line reasons, for your approval** |
| **7. Learn from the first results** | After wave 1 compiles, compare the risk score with what really broke. Libraries that broke without being flagged → add new danger signs | A short report: "risk scan caught 80% of real breaks" |
| **8. Grow to 200, then 500** | Same process, next places in the ranking | Updated list |

Libraries are **never removed** because they compile fine. "Still works on 4.0" is useful information too.

---

## 4. How we will know the list is good

| Check                             | Pass condition                                                                                                   |
| --------------------------------- | ---------------------------------------------------------------------------------------------------------------- |
| Sanity: famous names present      | All names from 2.5 appear naturally in the top 100                                                               |
| Calibration                       | Espressif's ~10 tested libraries get the same pass/fail from us as from them                                     |
| Risk scan accuracy (after wave 1) | Most real 4.0 breaks were in libraries the scan marked medium/high risk                                          |
| Community reaction                | Few "why is X missing?" requests in the first weeks. Every such request is logged and used to adjust the weights |

---

## 5. Decisions I need from you

1. **Weights:** do you agree with popularity 50% / risk 35% / maintenance 10% / multi-chip 5%? (Simple choice: "more famous libraries first" vs "more likely-broken libraries first".)
2. **Abandoned libraries:** a popular library nobody maintains any more is exactly where users need the table most, because no fix is coming. I suggest **keeping them** (maintenance is only 10%). Agree?
3. **Size of wave 1:** 50 libraries is what the general plan says. With 4 core versions × 3 chips × ~3 library versions × 1–2 examples, that is about 1,500–3,000 compiles. OK to start there?

---

## 6. Known limits (said honestly)

- **No official download numbers** exist for the Arduino Library Manager, so popularity is estimated from stars, PlatformIO downloads and dependencies.
- **Stars favor old libraries.** A newer library that everyone switched to may rank too low. The "recently maintained" factor and community requests partly fix this.
- **The risk scan is a guess.** It decides the order of testing, never the result. Every ✅/❌ in the table still comes only from a real compile log.
