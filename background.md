# ESP32 compatibility table: background for a software developer

_Written 2026-11-21. Assumes you know programming, build systems, package managers, semver and CI. Assumes you know nothing about electronics or Arduino. Software analogies are used wherever they fit._

---

## 1. The problem in software terms

- **ESP32** is a family of cheap microcontrollers with built-in Wi-Fi.
- **Arduino-ESP32** (the "core") is the SDK, runtime and standard library you program them with.
- **Arduino libraries** are third-party packages built against that SDK. They come from a central index with **no lockfiles by default**, and most users just install "latest".
- SDK **4.0.0** shipped on **2026-11-19**. It's a semver major on top of a new underlying OS/SDK (**ESP-IDF 6.x**), so expect API removals.
- Upstream CI checks only about 10 third-party packages against it. The rest of the ecosystem's compatibility is unknown.
- **Project:** a build matrix of popular packages × package versions × SDK versions × target chips, published as a compatibility table, plus a resolver that suggests version pins.

This is a classic **ecosystem compatibility matrix** problem, like crater runs for Rust or Python wheel compatibility tables. The only unusual part is the embedded domain.

---

## 2. Microcontrollers: the mental model shift

A microcontroller (MCU) is not a small PC. The key differences:

|PC / server|Microcontroller (ESP32)|
|---|---|
|GBs of RAM, an MMU and virtual memory|~320–512 KB of on-chip SRAM, sometimes plus a few MB of external **PSRAM**|
|A disk|4–16 MB of **flash**; your program is stored and run from it|
|A full OS with processes and a loader|One statically linked firmware image; usually **FreeRTOS** (a small real-time scheduler, tasks ≈ threads, no process isolation)|
|Hardware behind drivers in the kernel|Your code (or a library) configures hardware **directly** through registers, or through a thin driver layer|
|Install an app|**Flash** a new firmware image over USB|
|Dynamic linking|Everything compiled and linked into one binary; **no ABI stability needed, but every API change is a compile break**|

That last row is why this project works. Incompatibilities surface at **compile time**, which you can test cheaply without hardware.

### Flash partitions

Flash is split into a **partition table**: app slots (often two, for over-the-air updates), a key-value store (NVS) and a filesystem. A large program may not fit the default app slot. "Choose a bigger partition scheme" is a common build option, and a common cause of **false failures** in your table (the program is too large rather than incompatible).

---

## 3. Peripherals: the hardware vocabulary libraries depend on

Most library breakage comes from changes in how code talks to these on-chip hardware blocks ("peripherals"). Think of them as built-in devices with memory-mapped registers.

|Peripheral|What it does|Typical libraries that use it|
|---|---|---|
|**GPIO**|Pins you set high/low or read (1 bit of digital I/O)|Everything|
|**I²C**|Slow 2-wire bus to talk to sensors (addressed devices on a shared bus)|Most sensor drivers|
|**SPI**|Fast 4-wire bus, used for displays, SD cards and radios|Display drivers (TFT_eSPI), SD|
|**UART**|Serial port|GPS modules, debugging (`Serial`)|
|**ADC**|Reads an analog voltage as a number|Analog sensors, battery monitoring|
|**LEDC (PWM)**|Generates square waves with adjustable duty cycle: LED dimming, motor speed, servos|Servo, buzzer and dimming libraries|
|**Hardware timers**|Precise interrupts at intervals|Timing-sensitive libraries|
|**RMT**|Generates and reads precisely timed pulse trains|**Addressable LED strips** (FastLED, NeoPixel), IR remotes|
|**I²S**|Digital audio stream|Audio playback and microphones|
|**DMA**|Moves data between peripherals and memory without the CPU|Fast displays, audio|
|**Wi-Fi / Bluetooth**|Radios, with a network stack (lwIP) on top|Networking, MQTT, BLE libraries|

**Rule of thumb:** the closer a library sits to timers, LEDC, RMT, I²S or DMA, the more likely a major-version SDK change breaks it. Pure-logic libraries (JSON, math) and libraries that only use the portable Arduino APIs (`digitalWrite`, the `Wire` I²C class, the `SPI` class) usually survive.

---

## 4. The chips

|Chip|CPU architecture|Radios|Notes|
|---|---|---|---|
|ESP32|Xtensa LX6, dual core|Wi-Fi, BT Classic + BLE|Most common|
|ESP32-S2|Xtensa LX7, single core|Wi-Fi only|Native USB|
|ESP32-S3|Xtensa LX7, dual core|Wi-Fi, BLE|Vector instructions; popular for displays and cameras|
|ESP32-C3|RISC-V, single core|Wi-Fi, BLE|Cheap, popular|
|ESP32-C6|RISC-V|Wi-Fi 6, BLE, 802.15.4 (Zigbee/Thread)||
|ESP32-C5|RISC-V|Dual-band Wi-Fi 6, BLE, 802.15.4||
|ESP32-H2|RISC-V|BLE, 802.15.4, **no Wi-Fi**||
|ESP32-P4|RISC-V, high-performance|**No radio**|Multimedia|

Implications for the build matrix:

- **Two ISAs and two compiler toolchains** (Xtensa GCC and RISC-V GCC). Inline assembly, ISA-specific intrinsics and `#ifdef CONFIG_IDF_TARGET_ESP32` branches mean code can pass on one family and fail on the other. That's why the plan uses one representative chip per family first: ESP32 and S3 for Xtensa, C3 for RISC-V.
- **Feature availability differs per chip.** For example, a Bluetooth Classic library can't build for C3. That cell is **N/A**, not a failure. You need a per-chip capability map so you don't report false regressions.
- **Peripheral counts differ per chip** (number of timers, RMT channels and so on), so even some portable code has chip-specific branches.

---

## 5. The software stack

```
┌───────────────────────────────────────────────┐
│ Sketch (user app)                              │
├───────────────────────────────────────────────┤
│ Third-party Arduino libraries                  │ ← tested
├───────────────────────────────────────────────┤
│ Arduino-ESP32 core: Arduino API + bundled libs │ ← changed (4.0)
│   (WiFi, BLE, Preferences, LittleFS, ...)      │
├───────────────────────────────────────────────┤
│ ESP-IDF: drivers, FreeRTOS, lwIP, mbedTLS ...  │ ← root cause (6.x)
├───────────────────────────────────────────────┤
│ Hardware                                       │
└───────────────────────────────────────────────┘
```

### ESP-IDF

Espressif's native C SDK: a CMake/Ninja build, components, **menuconfig** (a Kconfig-style compile-time configuration, like the Linux kernel's), FreeRTOS, hardware drivers, lwIP networking and mbedTLS crypto. Major versions (4.4 → 5.x → 6.x) **remove deprecated APIs and headers**.

### Arduino-ESP32 core

A compatibility layer implementing the Arduino API on top of ESP-IDF, plus bundled libraries. Two details matter:

- **ESP-IDF ships precompiled** inside the core, with one fixed menuconfig per chip. Libraries can't change that configuration; they compile against fixed headers and link against prebuilt `.a` files. So results are deterministic given (core version, chip, board options).
- **Libraries can still `#include` ESP-IDF headers directly.** Many advanced libraries do this, bypassing the Arduino API to reach RMT, I²S or LEDC. **This is the most common source of breakage**, because those headers change on an ESP-IDF major version.

|Core|ESP-IDF|Status|
|---|---|---|
|2.0.x (last 2.0.17)|4.4|Legacy, still widely used|
|3.0–3.3.x (last 3.3.12)|5.1 → 5.5|Previous stable line; **the baseline for "is this a 4.0 regression?"**|
|4.0.0 (2026-11-19)|6.x|New major|

---

## 6. The Arduino build model (how a sketch becomes firmware)

This is the part a software developer usually finds unusual.

1. **The sketch** is a folder with a `.ino` file. It's essentially C++ with `setup()` and `loop()`. The build tool preprocesses it: it adds `#include <Arduino.h>`, generates function prototypes, and renames the file to `.cpp`.
2. **Library discovery happens by `#include`.** The builder scans your includes and looks for an installed library that provides each header. There's no manifest. Which library gets picked depends on what's installed, and there are priority rules when two provide the same header.
3. **Only one version of each library is installed at a time** (globally, in the default setup). That's another reason you need isolated environments per test.
4. **Everything compiles from source** (your sketch plus every library), then links with the precompiled core into one ELF file, which becomes a flashable `.bin`.
5. **Board options** are compile-time flags you choose per build, such as flash size, partition scheme, PSRAM on/off and USB mode. They're encoded in the **FQBN**.

### FQBN (Fully Qualified Board Name)

This is the target triple of the Arduino world: `vendor:architecture:board[:option=value,...]`.

```
esp32:esp32:esp32                    # classic ESP32
esp32:esp32:esp32s3                  # S3
esp32:esp32:esp32c3                  # C3
esp32:esp32:esp32s3:PSRAM=opi,PartitionScheme=huge_app
```

### Library metadata (`library.properties`)

```properties
name=FastLED
version=3.7.0
architectures=*          # claimed platforms: "esp32", "avr", "*" ...
depends=OtherLib         # weak dependency hint, names only
includes=FastLED.h
```

`architectures` is self-declared and often wrong (`*` is common), so it's only a first filter. `depends` lists names without version constraints, so there's **no real dependency resolution**. Pinning is the user's job, which is exactly the gap your pinning tool fills.

### The library index

`https://downloads.arduino.cc/libraries/library_index.json` is one JSON file listing every registered library and **every released version**, with `architectures`, `dependencies`, `provides_includes` (a header → library map) and download URLs. It's both your **package universe** and your **change feed**: compare it daily to detect new releases.

---

## 7. Tooling

|Tool|Role in the project|
|---|---|
|**arduino-cli**|Headless Arduino: installs cores and libraries, and compiles. The farm's engine.|
|**Board manager index**|`https://espressif.github.io/arduino-esp32/package_esp32_index.json`, where core versions and toolchains come from|
|**arduino/compile-sketches**|Official GitHub Action that compiles sketches with given platforms and library versions; a possible ready-made farm|
|**Espressif External Libraries Test**|Upstream CI over a small curated library set (results in `LIBRARIES_TEST.md`). Reuse its config, and position your project as complementary: wider coverage, older cores, pin advice.|
|**PlatformIO**|Alternative build system with real `lib_deps` version specs, popular with advanced users. The official ESP32 platform lagged on core 3.x, and the community **pioarduino** fork fills that gap. Support both output formats in the pin tool.|

Core commands:

```bash
arduino-cli config add board_manager.additional_urls \
  https://espressif.github.io/arduino-esp32/package_esp32_index.json
arduino-cli core update-index
arduino-cli core install esp32:esp32@3.3.12      # one core version per data dir
arduino-cli lib install "FastLED@3.7.0"
arduino-cli compile --fqbn esp32:esp32:esp32s3 path/to/example
```

**Isolation:** arduino-cli keeps one installed version of each core and library per data directory. Use a container or a separate `--config-file` / data directory per (core version) and per job. Cache the core build per FQBN (`--build-cache-path`), or the core gets recompiled for every sketch.

---

## 8. Why libraries break: concrete patterns

### 2.x → 3.x (ESP-IDF 4.4 → 5.1): a reference for what to expect

- **LEDC (PWM):** channel-based `ledcSetup()` / `ledcAttachPin()` were replaced by pin-based `ledcAttach()`.
- **Timers:** `timerBegin()` changed its signature, and `timerAlarmWrite()` and related calls were removed.
- **ADC:** several configuration functions were removed.
- **BLE:** some APIs changed from `std::string` to Arduino `String`.
- **Networking:** the Wi-Fi and Ethernet classes were restructured.
- **Legacy ESP-IDF drivers** (`driver/timer.h`, old RMT and ADC APIs) were deprecated. Libraries including them got warnings, which become errors now (see below).

### 3.x → 4.0 (ESP-IDF 5.x → 6.x): what Espressif says changed

- **Legacy drivers removed.** Old driver headers are gone, so expect `No such file or directory` and `'x' was not declared in this scope` errors.
- **Compiler warnings treated as errors.** Code that compiled with warnings may now fail. Check whether the Arduino core propagates this flag to library code; it changes the failure count a lot.
- **New crypto API layer.** Libraries that call mbedTLS directly (TLS clients, hashing) are at risk.
- **Default libc changed from Newlib to PicolibC.** This rarely breaks compilation, but low-level stdio and reentrancy hacks can.
- **Header renames and removals**, for example `soc_memory_types.h` → `esp_memory_utils.h`, plus sleep/wakeup API changes.
- Check the arduino-esp32 docs for a **3.x → 4.0 migration guide**. If one exists, it's the best seed for your error-signature list.

### How portable libraries handle it

```cpp
#if ESP_ARDUINO_VERSION >= ESP_ARDUINO_VERSION_VAL(3, 0, 0)
  ledcAttach(pin, freq, resolution);
#else
  ledcSetup(channel, freq, resolution);
  ledcAttachPin(pin, channel);
#endif
```

A library with these guards was maintained through the last break, which is a positive signal for 4.0 too.

---

## 9. What the table measures, and its failure taxonomy

**It's a build-only test, with no hardware in the loop.**

- ❌ (compile failure) is high-confidence: the library is unusable with that configuration.
- ✅ means it builds. Runtime behavior can still differ (timing, driver semantics). State this on the site.

|Status|Meaning|Common cause|
|---|---|---|
|`pass`|Example compiled and linked||
|`fail`|Compile or link error in this library|API removed or renamed|
|`dep_fail`|A dependency failed, not this library|Shared driver libraries|
|`n/a`|Chip lacks the required feature|BT Classic on C3, Wi-Fi on H2/P4|
|`config`|Needs board options (PSRAM, partition scheme, USB mode)|Big apps, camera and display examples|
|`infra_error`|The farm failed (download, timeout)|Retry|

**The signal that matters:** `pass` on 3.3.12 → `fail` on 4.0 is a **regression**. `fail` on both was already broken, so it's not news.

**Model results as immutable facts** keyed by (library, library version, core version, chip, example, board options), with the build log stored. A library fix is a new version, which means a new row. Nothing is ever overwritten.

---

## 10. Version pinning (the pin tool's output)

The Arduino IDE has no lockfile by default. arduino-cli supports **sketch profiles** in `sketch.yaml`, which is effectively a lockfile:

```yaml
profiles:
  esp32s3:
    fqbn: esp32:esp32:esp32s3
    platforms:
      - platform: esp32:esp32 (3.3.12)
    libraries:
      - FastLED (3.7.0)
      - ArduinoJson (7.2.0)
```

Build it with `arduino-cli compile --profile esp32s3`.

The PlatformIO equivalent goes in `platformio.ini`:

```ini
lib_deps =
    fastled/FastLED @ 3.7.0
```

**Resolver logic:**

1. Take (target core, chip, set of libraries). Libraries can also be inferred from `#include`s via `provides_includes`.
2. For each library, pick the highest version that passes for that target.
3. If none passes, recommend the highest core version on which all of them pass.

---

## 11. Glossary (embedded and Arduino terms only)

|Term|Meaning|
|---|---|
|MCU|Microcontroller: CPU + RAM + flash + peripherals on one chip|
|Firmware|The single binary image that runs on the MCU|
|Flashing|Writing firmware to the MCU's flash|
|Peripheral|On-chip hardware block (timer, SPI controller, ...)|
|GPIO|General-purpose digital pin|
|PWM / LEDC|Square-wave generation; LEDC is the ESP32 peripheral for it|
|RMT|ESP32 peripheral for precisely timed pulses (LED strips, IR)|
|I²C / SPI / UART|Serial buses for talking to external chips|
|PSRAM|External RAM on some boards; must be enabled per build|
|Partition scheme|How flash is split between app, data and filesystem|
|FreeRTOS|Small real-time scheduler under ESP-IDF|
|ESP-IDF|Espressif's native SDK under the Arduino core|
|Core / platform|The Arduino SDK for a chip family (`esp32:esp32`)|
|Sketch|An Arduino app (folder + `.ino`)|
|FQBN|Target identifier + board options|
|menuconfig / sdkconfig|ESP-IDF compile-time configuration (fixed inside the Arduino core)|
|Xtensa / RISC-V|The two CPU architectures across ESP32 chips|

---

## 12. Reading list (prioritized)

1. **Migration from 2.x to 3.0** (arduino-esp32 docs): the anatomy of a major break.
2. **Announcing ESP-IDF v6.0** (Espressif developer blog, March 2026): the breaking-changes section.
3. **ESP-IDF 6.0 migration guide**, the System and Peripherals sections: removed headers and APIs, a seed for error signatures.
4. **arduino-esp32 4.0 release notes**, plus a 3.x → 4.0 migration guide if published.
5. **Compatibility guide for the ESP32 Arduino core**: how libraries support several cores at once.
6. **arduino-cli docs**: the Library Specification, `compile`, sketch profiles (`sketch.yaml`).
7. **arduino/compile-sketches README** and Espressif's **External Libraries Test** setup.
8. **GitHub issue #8796** (espressif/arduino-esp32): real-world 3.x migration errors, useful as triage training data.

---

## 13. One hour hands-on (no hardware needed)

```bash
# 1. install arduino-cli, add the ESP32 index (section 7)
# 2. baseline
arduino-cli core install esp32:esp32@3.3.12
arduino-cli lib install "FastLED" "Adafruit NeoPixel" "ArduinoJson" "TFT_eSPI" "PubSubClient"
for ex in <one example per library>; do
  arduino-cli compile --fqbn esp32:esp32:esp32s3 "$ex"
done
# 3. switch core (use a separate data dir or container) to 4.0.0 and repeat
# 4. read one failure log end to end
```

After this you'll be able to recognize real breakage in the AI's reports.

---

## 14. Review checklist for the AI's plans

- Matrix definition: exact core versions, FQBNs + options, chips. How are `n/a` cells derived?
- Isolation: one environment per core version? Are library installs isolated per job?
- Dependency handling: how are `depends` and include-based discovery resolved? How is `dep_fail` separated from `fail`?
- Determinism: pinned toolchains, recorded tool versions, stored logs for every cell.
- Data model: immutable rows keyed by full configuration; regression = baseline pass → target fail.
- Incrementality: index diffing; only new (library version × target) cells are built.
- Cost: compiles per full run, time per compile with caching, total compute time.