# ESP32 Arduino Library Compatibility

Which popular Arduino libraries compile on **Arduino-ESP32 core 4.0.0** (ESP-IDF 6.x), compared with 3.3.12, 3.0.7 and 2.0.17, on ESP32, ESP32-S3 and ESP32-C3, plus a pin tool that tells you which library versions to use.

**Every ✅/❌ comes from a real compile log.** Results are immutable facts keyed by (library, library version, core, chip, example, board options).

- `farm/` – the compile farm (Python + arduino-cli): `prepare.py` (plan), `run.py` (compile), `classify.py` (log → status rules), `export.py` (site data), `update.py` (daily job)
- `site/` – the static website (table, regressions, error groups, pin tool)
- `selection-data/`, `library-selection-plan.md`, `initial-library-set.md` – how the libraries were chosen
- `background.md` – domain primer

Ask for a library to be added, or for a recheck after a fix, by opening an issue.
