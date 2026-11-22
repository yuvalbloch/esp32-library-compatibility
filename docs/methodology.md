# Methodology: how every result is produced

This document describes exactly what the farm does. If the code and this document disagree, that is a bug; please open an issue.

## 1. The test matrix

| Dimension | Values |
|---|---|
| Core | `esp32:esp32` **2.0.17**, **3.0.7** (last 3.0.x), **3.3.12**, **4.0.0** |
| Chip / FQBN | `esp32:esp32:esp32`, `esp32:esp32:esp32s3`, `esp32:esp32:esp32c3`, default board options |
| Library versions | newest stable release + the 3 stable releases before it (pre-releases are skipped) |
| Examples | 1–2 of the library's own example sketches (§3) |
| Compiler | `arduino-cli` 1.6.0; warnings at the Arduino IDE default (`--warnings none`) |

**Baseline and target.** A *regression* means: on core **3.3.12** an example compiles, and on core **4.0.0** the same example, same library version, same chip fails (`fail` or `dep_fail`). 3.3.12 was the newest 3.x release when the plan was made (3.3.13 came out later and is not yet a column).

## 2. Isolation

- **One sealed install per core.** Each core version has its own `arduino-cli` data directory and config file. Nothing is shared between cores except the download cache.
- **Exact library versions per compile.** Libraries are not installed with `arduino-cli lib install` (which allows only one version at a time). Each library version is downloaded from the URL in the Library Manager index, its SHA-256 checksum is verified, and it is extracted into its own folder. Each compile receives exactly the folders it needs through `--libraries` flags, and nothing else (the sketchbook library folder is empty).
- **Libraries bundled in the core** (WiFi, BLE, SD, Preferences, …) come from the core under test, as in the Arduino IDE.
- **Core build cache.** The precompiled Arduino core is cached per core version, chip and board options. This only speeds things up; it does not change results.

## 3. Choosing example sketches

The examples are picked once per library from its newest version. Older versions use the same sketches when they still exist, so versions are compared like for like.

1. **Espressif-checked libraries** use the same sketches as Espressif's External Libraries Test (`lib.json`), so the two sets of results can be compared.
2. **Hand-picked overrides** ([`farm/examples_override.json`](../farm/examples_override.json)) are used where the automatic choice would pick something unrepresentative, for example a library-specific build test or an ESP32-specific example.
3. **Otherwise, automatic:** the most "basic" example (names like `Basic`, `Simple`, `HelloWorld`, `Blink`, `strandtest`), plus the best ESP32-specific example if one exists. Examples for other platforms (ESP8266, AVR, RP2040, STM32, …) and examples that need extra hardware setup (SD card, PSRAM, camera, Ethernet) are ranked down.

Which examples are compiled is a choice of *what to test*. It never affects *how a result is judged*.

## 4. Dependencies

- **Declared dependencies.** A library's `depends=` list (from the Library Manager index) is resolved recursively. Each dependency gets its newest stable version that satisfies the declared constraint. Dependencies that are bundled in the core under test are skipped.
- **Undeclared libraries used by an example.** Many examples include a library their own library does not declare (for example a display example that needs a graphics library). If a compile fails with `fatal error: X.h: No such file or directory`, the farm adds the Library Manager library that provides `X.h` and compiles again, up to 4 times. This is **not** done when the missing header:
  - contains a path (`driver/rmt.h`, `rom/gpio.h`, …),
  - looks like an ESP-IDF or core header (`esp_*`, `soc*`, `hal*`, `driver*`, `freertos*`, `lwip*`, `mbedtls*`, …), or
  - is provided by a library bundled in any tested core.

  This way a header that 4.0 removed is reported as a failure and never "fixed" by pulling in some other library. Libraries added this way are remembered per (library, version, example) and given to the same example on every core and chip.
- Every library given to the compiler, with its version, is listed in the log header and stored with the result.

## 5. From log to status

The status is derived mechanically from the compiler's exit code and the log, by the fixed rules in [`farm/classify.py`](../farm/classify.py):

| Status | Rule |
|---|---|
| `pass` | `arduino-cli compile` exited with code 0. A build that exits 0 is always `pass`; a build that exits non-zero is never `pass`. |
| `config` | The log says the program is too big for the flash partition (`Sketch too big`, `region … overflowed`), **or** the first error is an `#error` asking for a specific board or board setting (select the correct board, enable PSRAM, USB mode, …). |
| `n/a` | The first error is an `#error` saying the chip lacks a feature (Bluetooth Classic not available, not supported on ESP32-C3, …) and the message is *not* about the core or ESP-IDF version. |
| `dep_fail` | The first compiler error is located in a dependency's source files, not in the library under test or the sketch. |
| `fail` | Any other compile or link error. |
| `infra_error` | The compile timed out (20 min), or the log has no compiler error at all (download or tool problem). Retried once immediately and again on the next run; never shown as ✗. |

**Too big for the default partition.** When a build is `config` because it is too big, the farm compiles it again with `PartitionScheme=huge_app`. Both rows are stored. The table shows ✓⚙ when the second one passes.

**Root-cause labels.** Failures are also given a human-readable label ("Legacy ESP-IDF driver header removed", "Old LEDC (PWM) API", "Crypto (mbedTLS / PSA) API change", …) by matching the first error against a list of patterns. Labels group errors in the *Error groups* view. They are explanations only and never change a status.

## 6. Results are immutable

Each compile produces one database row keyed by *(library, library version, core, chip, example, board options)* and one gzipped log. Rows are never edited or overwritten. The only exception is `infra_error` rows, which are replaced when the retry succeeds, because they describe the farm rather than the code. A library fix shows up as a new library version with new rows.

## 7. What the table shows per cell

A cell is one *(library version, core, chip)* and may cover two examples:

- ✓ if every example that ran passed (✓⚙ if one needed `huge_app`)
- ◐ if at least one example passed and at least one failed
- ✗ / dep if none passed and at least one failed
- otherwise ⚙ / — / ?

Clicking a cell shows each example's own status, its first error and a link to its log.

## 8. Reproducing a result

Each published log starts with a header like this:

```
# library: FastLED 3.10.10
# example: examples/Blink
# core: esp32:esp32@4.0.0
# fqbn: esp32:esp32:esp32s3
# other libraries given to the compiler: {}
# arduino-cli: arduino-cli  Version: 1.6.0 ...
# command: arduino-cli --config-file ... compile --fqbn esp32:esp32:esp32s3 --libraries ... <sketch>
```

To reproduce: install that core version in a clean `arduino-cli` setup, download the listed library versions, and run the same `compile` command.

## 9. Limits

- **Build-only.** No hardware is involved. ✓ does not prove the library works at runtime.
- **Examples are a sample.** A library can pass its examples and still fail in code paths they do not use.
- **Default board options.** Libraries that need PSRAM, a special partition table or a specific board definition (board-support libraries such as M5Stack, Heltec, Inkplate) may show ⚙ rather than ✓ or ✗.
- **The risk score** used to choose and order libraries ([library selection](library-selection.md)) only decides the order of testing, never a result.
