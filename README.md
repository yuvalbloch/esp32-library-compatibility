# ESP32 Arduino Library Compatibility

**Which Arduino libraries still compile on Arduino-ESP32 core 4.0, and which versions should you pin?**

Arduino-ESP32 core **4.0.0** was released on 2026-11-19. It runs on ESP-IDF 6.x, which removed the legacy drivers, changed the crypto API and renamed many headers. Espressif's own CI compiles about ten external libraries against it. Nobody has checked the rest of the ecosystem yet.

This project compiles popular libraries against several core versions and chips, publishes the results as a table, and gives you a **pin tool** that writes a lockfile with library versions known to build.

**The table: https://yuvalbloch.com/wild-west/esp32-table/**

> **Status (2026-11-22):** first full run done: 62 libraries, about 5,800 compiles. The newest release of 25 libraries builds on core 4.0.0 for all three chips. 19 libraries compile on core 3.3.12 but fail on 4.0.0 for at least one chip, in their newest release. The table updates itself every night.

## How this was made

This is a side project by Yuval Bloch, built as an experiment in AI-driven development: an AI (Claude) planned and wrote all the code, and I reviewed and approved each step. I am not an embedded developer. That is why the project has one rule it never bends (below): no human or AI decides a result. If something looks wrong, please [open a "Wrong result" issue](../../issues/new?template=wrong-result.yml).

## The one rule

**Every ✅ and ❌ comes from a real compile log.** Nobody sets a result by hand, human or AI. Every cell in the table links to the full log that produced it, including the exact `arduino-cli` command, so you can reproduce it.

## What is tested

| | |
|---|---|
| **Cores** | Arduino-ESP32 `2.0.17`, `3.0.7`, `3.3.12`, `4.0.0` |
| **Chips** | ESP32 (Xtensa LX6), ESP32-S3 (Xtensa LX7), ESP32-C3 (RISC-V) |
| **Libraries** | 62 popular libraries from the Arduino Library Manager ([the list](docs/initial-library-set.md)) |
| **Library versions** | the newest release and the 3 releases before it |
| **Test** | compile 1–2 of the library's own example sketches. This is a build test only; no hardware is involved |

Other chips (S2, C6, H2, P4, C5) will be added later, for libraries that pass on these three.

## Reading the table

| Symbol | Meaning |
|---|---|
| ✓ | The example compiled and linked |
| ✓⚙ | Compiles, but only with a bigger flash partition (`PartitionScheme=huge_app`) |
| ◐ | Some examples compile and some fail |
| ✗ | Fails to compile |
| dep | A library it depends on fails, not the library itself |
| — | Not applicable: the chip lacks a feature the library needs (e.g. Bluetooth Classic on C3) |
| ⚙ | Needs specific board settings or a specific board definition |
| ? | The farm had a problem (download, timeout). It will be retried |

A **red outline** marks a **regression**: the same library version and example compiled on core 3.3.12 and fails on core 4.0.0 for the same chip. That is the main signal the table exists to find.

✓ means *it builds*, not *it works*. Runtime behaviour can still differ between cores. ✗ is a strong signal: the code cannot be built with that setup.

## The pin tool

Choose your chip, your core and your libraries. For each library the tool picks the newest version that compiled in our tests and writes a lockfile:

- an `arduino-cli` [sketch profile](https://arduino.github.io/arduino-cli/latest/sketch-project-file/) (`sketch.yaml`), which you build with `arduino-cli compile --profile <name>`
- a PlatformIO `lib_deps` block

If no tested version of a library builds on your core, it suggests the newest core on which all of your libraries do.

## Results are permanent facts

Each result is keyed by *(library, library version, core version, chip, example, board options)* and never changes. When a maintainer fixes a library, the fix arrives as a **new library version with new rows**. The old rows stay true, so the table never goes stale. This history is also what the pin tool uses.

A daily job checks the Library Manager for new releases of the tracked libraries and compiles only those. A new core version adds a column and triggers one full run.

## Contributing

- **Add a library:** open an [“Add a library” issue](../../issues/new?template=add-library.yml).
- **A maintainer fixed something:** open a [“Recheck” issue](../../issues/new?template=recheck.yml). New releases are also picked up automatically within a day.
- **A result looks wrong:** open a [“Wrong result” issue](../../issues/new?template=wrong-result.yml) and include the log link from the table.

See [CONTRIBUTING.md](CONTRIBUTING.md) for details.

## Documentation

| Document | What it covers |
|---|---|
| [docs/methodology.md](docs/methodology.md) | Exactly how each result is produced: isolation, example choice, dependencies, status rules, regressions, limits |
| [docs/library-selection.md](docs/library-selection.md) | How the 62 libraries were chosen (popularity × breakage risk) |
| [docs/initial-library-set.md](docs/initial-library-set.md) | The wave-1 library list with scores and risk reasons |
| [docs/running-the-farm.md](docs/running-the-farm.md) | How to run the compile farm yourself |
| [docs/background.md](docs/background.md) | Primer for software developers new to ESP32 and Arduino: chips, ESP-IDF, FQBNs, why libraries break |

## Repository layout

```
farm/               the compile farm (Python 3.11 + arduino-cli)
  prepare.py          build the test plan: library versions, example sketches, dependencies
  run.py              run the compiles in parallel, store results and logs (resumable)
  classify.py         the fixed rules that turn a compile log into a status
  export.py           export results to the website
  update.py           daily job: new library releases, retries, re-export
  store.py            library download (checksum-verified), example picking, dependency resolution
  examples_override.json   hand-picked example sketches where the automatic choice is poor
site/               the static website (table, regressions, error groups, pin tool)
selection-data/     library selection script and its full output
docs/               documentation
```

## Related

- [Espressif External Libraries Test](https://github.com/espressif/arduino-esp32/blob/master/.github/workflows/lib.json) compiles a small curated set upstream. This project complements it with wider coverage, older cores and pin advice. The libraries Espressif checks are included here too, marked **Espressif CI**, as a calibration check.
- [Arduino-ESP32 migration guide 2.x → 3.0](https://docs.espressif.com/projects/arduino-esp32/en/latest/migration_guides/2.x_to_3.0.html)

## License

Code: [MIT](LICENSE). Results data (the table and logs): [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). Use it freely; please link back.
