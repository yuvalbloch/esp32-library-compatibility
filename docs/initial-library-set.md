# Initial library set: wave 1

_Generated 2026-11-21 by following [the library selection method](library-selection.md). Data sources: Arduino Library Manager index, PlatformIO registry (stars and download rank), Espressif `lib.json` test config._

## Summary

- **50 libraries that Espressif does NOT check** (the new coverage this table adds), plus
- **12 libraries Espressif already checks**: they also go in the table, marked, and serve as a calibration check.
- **Total wave 1: 62 libraries.**

### How we got from 10,000 libraries to 50

| Step | Libraries left |
|---|---|
| All libraries in the Arduino Library Manager | 10,485 |
| G1 + G2: claim ESP32 support, not built into the core | 8,740 |
| Have popularity data (PlatformIO top 800 for ESP32, or used by 5+ other libraries) | 675 |
| G4: duplicates and forks removed | 662 |
| Top ~260 by popularity, downloaded and code-scanned | 263 |
| G3 + G5: have example sketches, not AVR-only | 257 |
| **Selected (not checked by Espressif)** | **50** |

## Part A: 50 libraries Espressif does not check

**Risk** = how likely 4.0 broke it, based on what its code uses (High / Medium / Low / None). **Score** = final weighted score, 0–100.

| # | Library | Version | Category | Score | ⭐ Stars | Risk | What the code touches | Why it is in |
|---|---|---|---|---|---|---|---|---|
| 1 | [LovyanGFX](https://github.com/lovyan03/LovyanGFX) | 1.3.0 | Displays | 96 | 1,799 | High | removed/renamed IDF headers, old IDF driver headers, timer/PWM/RMT/I2S/DMA, other IDF internals, core-version checks | Score rank #1 |
| 2 | [M5Unified](https://github.com/m5stack/M5Unified) | 0.3.0 | Displays | 94 | 724 | High | removed/renamed IDF headers, old IDF driver headers, timer/PWM/RMT/I2S/DMA, other IDF internals, core-version checks | Score rank #2 |
| 3 | [NimBLE-Arduino](https://github.com/h2zero/NimBLE-Arduino) | 2.5.2 | Bluetooth | 92 | 1,134 | Medium | direct crypto (mbedTLS), other IDF internals, core-version checks | Must-include (plan 2.5) |
| 4 | [ESP8266Audio](https://github.com/earlephilhower/ESP8266Audio) | 2.4.3 | Audio | 92 | 2,417 | High | removed/renamed IDF headers, old IDF driver headers, timer/PWM/RMT/I2S/DMA, other IDF internals, core-version checks | Score rank #4 |
| 5 | [RadioLib](https://github.com/jgromes/RadioLib) | 8.0.0 | Networking/Web | 89 | 2,648 | High | old IDF driver headers, timer/PWM/RMT/I2S/DMA, other IDF internals, core-version checks | Score rank #5 |
| 6 | [Adafruit TinyUSB Library](https://github.com/adafruit/Adafruit_TinyUSB_Arduino) | 3.8.1 | Utilities | 89 | 654 | High | removed/renamed IDF headers, old IDF driver headers, other IDF internals, core-version checks | Score rank #6 |
| 7 | [M5GFX](https://github.com/m5stack/M5GFX) | 0.3.0 | Displays | 89 | 389 | High | removed/renamed IDF headers, old IDF driver headers, other IDF internals, core-version checks | Score rank #7 |
| 8 | [WiFiManager](https://github.com/tzapu/WiFiManager) | 2.0.17 | Networking/Web | 88 | 6,510 | Medium | removed/renamed IDF headers, other IDF internals, core-version checks | Must-include (plan 2.5) |
| 9 | [Simple FOC](https://github.com/askuric/Arduino-FOC) | 2.4.0 | Motors/Servos | 88 | 2,679 | High | removed/renamed IDF headers, old IDF driver headers, timer/PWM/RMT/I2S/DMA, other IDF internals, core-version checks | Score rank #9 |
| 10 | [TFT_eSPI](https://github.com/Bodmer/TFT_eSPI) | 2.5.43 | Displays | 88 | 3,087 | Medium | removed/renamed IDF headers, timer/PWM/RMT/I2S/DMA, other IDF internals | Must-include (plan 2.5) |
| 11 | [OneWire](https://github.com/PaulStoffregen/OneWire) | 2.3.8 | Sensors | 87 | 633 | High | removed/renamed IDF headers, old IDF driver headers, other IDF internals, core-version checks | Score rank #11 |
| 12 | [ESP32Encoder](https://github.com/madhephaestus/ESP32Encoder) | 5.0.0 | Utilities | 87 | 374 | High | removed/renamed IDF headers, old IDF driver headers, timer/PWM/RMT/I2S/DMA, other IDF internals, core-version checks | Score rank #12 |
| 13 | [Blynk](https://github.com/Blynk-Technologies/blynk-library) | 1.4.0 | Networking/Web | 87 | 3,991 | Low | other IDF internals, core-version checks | Score rank #13 |
| 14 | [ESP32 HUB75 LED MATRIX PANEL DMA Display](https://github.com/mrcodetastic/ESP32-HUB75-MatrixPanel-DMA) | 3.1.0 | LEDs | 86 | 1,615 | High | removed/renamed IDF headers, old IDF driver headers, timer/PWM/RMT/I2S/DMA, other IDF internals, core-version checks | Score rank #14 |
| 15 | [WebSockets](https://github.com/Links2004/arduinoWebSockets) | 2.7.2 | Networking/Web | 86 | 2,017 | Medium | removed/renamed IDF headers, other IDF internals, core-version checks | Score rank #15 |
| 16 | [FastAccelStepper](https://github.com/gin66/FastAccelStepper) | 2.0.1 | Motors/Servos | 85 | 524 | High | removed/renamed IDF headers, old IDF driver headers, timer/PWM/RMT/I2S/DMA, other IDF internals, core-version checks | Score rank #16 |
| 17 | [NeoPixelBus by Makuna](https://github.com/Makuna/NeoPixelBus) | 2.8.4 | LEDs | 84 | 1,206 | High | removed/renamed IDF headers, old IDF driver headers, timer/PWM/RMT/I2S/DMA, other IDF internals, core-version checks | Score rank #17 |
| 18 | [TaskScheduler](https://github.com/arkhipenko/TaskScheduler) | 4.1.1 | Utilities | 83 | 1,658 | Medium | timer/PWM/RMT/I2S/DMA, other IDF internals, core-version checks | Score rank #18 |
| 19 | [SensorLib](https://github.com/lewisxhe/SensorLib) | 0.5.2 | Sensors | 82 | 257 | High | removed/renamed IDF headers, timer/PWM/RMT/I2S/DMA, other IDF internals, core-version checks | Score rank #19 |
| 20 | [lvgl](https://github.com/lvgl/lvgl) | 9.6.0 | Displays | 82 | 24,704 | Low | other IDF internals | Score rank #20 |
| 21 | [IRremoteESP8266](https://github.com/markszabo/IRremoteESP8266) | 2.9.0 | Sensors | 80 | 3,332 | Medium | timer/PWM/RMT/I2S/DMA, core-version checks | Score rank #21 |
| 22 | [EspSoftwareSerial](https://github.com/plerup/espsoftwareserial) | 8.1.0 | Utilities | 77 | 702 | Low | other IDF internals | Score rank #22 |
| 23 | [M5Stack](https://github.com/m5stack/M5Stack) | 0.4.6 | Utilities | 77 | 1,071 | High | removed/renamed IDF headers, old IDF driver headers, timer/PWM/RMT/I2S/DMA, other IDF internals, core-version checks | Score rank #23 |
| 24 | [Button2](https://github.com/LennartHennigs/Button2) | 2.7.0 | Utilities | 76 | 560 | Low | timer/PWM/RMT/I2S/DMA | Score rank #24 |
| 25 | [LibSSH-ESP32](https://github.com/ewpa/LibSSH-ESP32) | 5.10.0 | Networking/Web | 76 | 378 | Medium | direct crypto (mbedTLS), other IDF internals, core-version checks | Score rank #25 |
| 26 | [Adafruit SPIFlash](https://github.com/adafruit/Adafruit_SPIFlash) | 5.1.3 | Storage/Files | 76 | 198 | Low | other IDF internals, core-version checks | Score rank #26 |
| 27 | [HomeSpan](https://github.com/HomeSpan/HomeSpan) | 2.1.8 | Networking/Web | 76 | 2,085 | High | removed/renamed IDF headers, old IDF driver headers, timer/PWM/RMT/I2S/DMA, direct crypto (mbedTLS), other IDF internals, core-version checks | Score rank #27 |
| 28 | [ElegantOTA](https://github.com/ayushsharma82/ElegantOTA) | 4.0.0 | Networking/Web | 76 | 1,004 | Low | other IDF internals | Score rank #28 |
| 29 | [XPowersLib](https://github.com/lewisxhe/XPowersLib) | 0.3.3 | Utilities | 75 | 125 | Low | other IDF internals, core-version checks | Score rank #29 |
| 30 | [wolfssl](https://github.com/wolfSSL/Arduino-wolfSSL) | 5.8.4 | Networking/Web | 74 | 2,242 | High | removed/renamed IDF headers, old IDF driver headers, other IDF internals, core-version checks | Score rank #30 |
| 31 | [bb_spi_lcd](https://github.com/bitbank2/bb_spi_lcd) | 2.9.10 | Displays | 74 | 238 | High | removed/renamed IDF headers, timer/PWM/RMT/I2S/DMA, other IDF internals, core-version checks | Score rank #31 |
| 32 | [FirebaseClient](https://github.com/mobizt/FirebaseClient) | 2.2.13 | Networking/Web | 74 | 276 | Medium | direct crypto (mbedTLS), core-version checks | Score rank #32 |
| 33 | [MobaTools](https://github.com/MicroBahner/MobaTools) | 3.1.3 | LEDs | 72 | 147 | High | removed/renamed IDF headers, old IDF driver headers, timer/PWM/RMT/I2S/DMA, other IDF internals, core-version checks | Score rank #33 |
| 34 | [StreamUtils](https://github.com/bblanchon/ArduinoStreamUtils) | 1.9.2 | Utilities | 72 | 282 | Low | core-version checks | Score rank #34 |
| 35 | [OneWireNg](https://github.com/pstolarz/OneWireNg) | 0.14.1 | Sensors | 71 | 100 | Low | other IDF internals, core-version checks | Score rank #35 |
| 36 | [Adafruit SleepyDog Library](https://github.com/adafruit/Adafruit_SleepyDog) | 1.8.4 | Utilities | 71 | 244 | Low | other IDF internals, core-version checks | Score rank #36 |
| 37 | [Heltec ESP32 Dev-Boards](https://github.com/HelTecAutomation/Heltec_ESP32) | 2.1.6 | Networking/Web | 70 | 863 | High | removed/renamed IDF headers, old IDF driver headers, timer/PWM/RMT/I2S/DMA, other IDF internals | Score rank #37 |
| 38 | [Adafruit Protomatter](https://github.com/adafruit/Adafruit_Protomatter) | 1.7.1 | LEDs | 69 | 84 | High | removed/renamed IDF headers, old IDF driver headers, timer/PWM/RMT/I2S/DMA, other IDF internals, core-version checks | Score rank #38 |
| 39 | [InkplateLibrary](https://github.com/e-radionicacom/Inkplate-6-Arduino-library) | 11.2.1 | Displays | 69 | 308 | High | removed/renamed IDF headers, old IDF driver headers, direct crypto (mbedTLS), other IDF internals | Score rank #39 |
| 40 | [Sqlite3Esp32](https://github.com/siara-cc/esp32_arduino_sqlite3_lib) | 2.5.0 | Storage/Files | 69 | 345 | Medium | removed/renamed IDF headers, other IDF internals | Score rank #40 |
| 41 | [M5Core2](https://github.com/m5stack/M5Core2) | 0.2.0 | Utilities | 68 | 266 | High | removed/renamed IDF headers, old IDF driver headers, timer/PWM/RMT/I2S/DMA, other IDF internals, core-version checks | Score rank #41 |
| 42 | [Firebase Arduino Client Library for ESP8266 and ESP32](https://github.com/mobizt/Firebase-ESP-Client) | 4.4.17 | Networking/Web | 68 | 472 | Low | other IDF internals, core-version checks | Score rank #42 |
| 43 | [SimpleFOCDrivers](https://github.com/simplefoc/Arduino-FOC-drivers) | 1.0.9 | Motors/Servos | 68 | 188 | High | removed/renamed IDF headers, old IDF driver headers, timer/PWM/RMT/I2S/DMA, other IDF internals | Score rank #43 |
| 44 | [HeatpumpIR](https://github.com/ToniA/arduino-heatpumpir) | 1.0.41 | Sensors | 67 | 431 | Medium | timer/PWM/RMT/I2S/DMA, other IDF internals, core-version checks | Score rank #44 |
| 45 | [ESP32-BLE-Gamepad](https://github.com/lemmingDev/ESP32-BLE-Gamepad) | 0.8.0 | Bluetooth | 65 | 1,585 | Low | other IDF internals | Category balance (plan 2.4) |
| 46 | [NonBlockingRTTTL](https://github.com/end2endzone/NonBlockingRTTTL) | 1.4.0 | Audio | 60 | 19 | Medium | timer/PWM/RMT/I2S/DMA, core-version checks | Category balance (plan 2.4) |
| 47 | [ArduinoJson](https://github.com/bblanchon/ArduinoJson) | 7.4.3 | Utilities | 57 | 7,124 | None | plain Arduino / C++ only | Must-include (plan 2.5) |
| 48 | [ESP8266 Influxdb](https://github.com/tobiasschuerg/InfluxDB-Client-for-Arduino) | 3.13.2 | Storage/Files | 56 | 365 | Low | other IDF internals, core-version checks | Category balance (plan 2.4) |
| 49 | [PubSubClient](https://github.com/knolleary/pubsubclient) | 2.8.0 | Networking/Web | 50 | 3,760 | None | plain Arduino / C++ only | Must-include (plan 2.5) |
| 50 | [DFRobotDFPlayerMini](https://github.com/DFRobot/DFRobotDFPlayerMini) | 1.0.6 | Audio | 41 | 241 | None | plain Arduino / C++ only | Category balance (plan 2.4) |

**By category:** Networking/Web 12 · Utilities 11 · Displays 7 · Sensors 5 · LEDs 4 · Audio 3 · Motors/Servos 3 · Storage/Files 3 · Bluetooth 2

**By risk:** High 23 · Medium 11 · Low 13 · None 3

## Part B: libraries Espressif already checks (also in our table, marked)

Source: `.github/workflows/lib.json` in espressif/arduino-esp32, the configuration of their External Libraries Test.

| Library | Version | Category | Score | Risk | Note |
|---|---|---|---|---|---|
| [FastLED](https://github.com/FastLED/FastLED) | 3.10.10 | LEDs | 97 | High | Checked by Espressif |
| [IRremote](https://github.com/z3t0/Arduino-IRremote) | 4.7.1 | Sensors | 91 | Medium | Checked by Espressif |
| [Adafruit NeoPixel](https://github.com/adafruit/Adafruit_NeoPixel) | 1.15.5 | LEDs | 88 | Medium | Checked by Espressif |
| [ESP Async WebServer](https://github.com/ESP32Async/ESPAsyncWebServer) | 3.12.1 | Networking/Web | 88 | High | Checked by Espressif |
| [ESP32Servo](https://github.com/madhephaestus/ESP32Servo) | 3.2.1 | Motors/Servos | 87 | Medium | Checked by Espressif |
| [ArduinoBLE](https://github.com/arduino-libraries/ArduinoBLE) | 2.1.1 | Bluetooth | 82 | Low | Checked by Espressif |
| [Async TCP](https://github.com/ESP32Async/AsyncTCP) | 3.6.1 | Networking/Web | 80 | Low | Checked indirectly: Espressif compiles it as a dependency of ESP Async WebServer |
| [MFRC522](https://github.com/miguelbalboa/rfid) | 1.4.12 | Sensors | 52 | None | Checked by Espressif |
| [ESP32IMDB](https://github.com/Xorlent/ESP32IMDB) | 1.2.0 | Storage/Files | 47 | Low | In Espressif's config, but missing from their published results page (LIBRARIES_TEST.md) |
| [EthernetESP32](https://github.com/Networking-for-Arduino/EthernetESP32) | 1.0.2 | Networking/Web | 37 | Medium | Checked by Espressif |
| [WS2812FX](https://github.com/kitesurfer1404/WS2812FX) | 1.4.7 | LEDs | 35 | None | Checked by Espressif |
| [ZACwire for TSic](https://github.com/lebuni/ZACwire-Library) | 2.0.0 | Sensors | 22 | None | Checked by Espressif |

## Next in line (for wave 2, or if you want to swap)

Adafruit TCS34725 (Sensors), UniversalTelegramBot (Networking/Web), ServoEasing (Motors/Servos), QNEthernet (Networking/Web), Painless Mesh (Networking/Web), esp_dmx (Networking/Web), home-assistant-integration (Networking/Web), M5StickCPlus (Utilities), USB Host Shield Library 2.0 (Utilities), ESP Mail Client (Networking/Web), Firebase ESP32 Client (Networking/Web), MCCI LoRaWAN LMIC library (Networking/Web), PubSubClient3 (Networking/Web), ServoESP32 (Motors/Servos), Adafruit GFX Library (Displays)

## Removed by the gates (from the scanned group)

- **TinyWireM**: G5: AVR-only code, no ESP32 path
- **SSD1306Ascii**: G5: AVR-only code, no ESP32 path
- **base64**: G3: no example sketches
- **libdivide**: G3: no example sketches
- **HaierProtocol**: G3: no example sketches
- **EthernetENC**: G3: no example sketches

## Notes and known limitations

1. **Bluetooth has 2 libraries, not 3.** The category-balance rule asks for 3, but no third Bluetooth library was among the ~260 libraries scanned. Wave 2 will look deeper.
2. **M5Stack has 4 libraries** (M5Unified, M5GFX, M5Stack, M5Core2). Each scored high on its own (popular, and they use the chip's internals heavily). There is no "maximum per vendor" rule.
3. **ArduinoJson and PubSubClient are in through the must-include rule, not the score.** They are very popular but use only plain C++, so their risk is "None" (score rank #64 and #88). Users look them up, so they are included.
4. **Where the numbers come from:** stars and last-release dates come from the PlatformIO registry, which mirrors GitHub star counts. Download popularity is PlatformIO's download rank, because the Arduino Library Manager does not publish download counts.
5. **Categories are assigned automatically** from each library's description, with obvious mistakes fixed by hand. A few borderline labels may remain. Board-support packages (M5Stack, Heltec) are filed under Utilities or Networking.
6. **The risk column is an estimate** that decides the order of testing, never the result. Every ✅/❌ in the table comes from a real compile log.

Want a library added? Open an [“Add a library” issue](../../../issues/new?template=add-library.yml).

## Files

- [selection-data/selection.json](../selection-data/selection.json): every number behind this list (all 6 scores per library, risk reasons, next-in-line, removed duplicates)
- [selection-data/select_libs.py](../selection-data/select_libs.py): the script that produced it (re-run it to refresh the list)
