# Running the compile farm

The farm is a few Python scripts around `arduino-cli`. It runs on Linux and Windows. It needs Python 3.11+. The farm itself uses no extra Python packages, but on Linux the older cores (2.0.17, 3.0.x) run `esptool.py` with your `python3` and need **pyserial** (`pip install pyserial`), just as the Arduino IDE does.

The cloud version runs on GitHub Actions ([`.github/workflows/farm.yml`](../.github/workflows/farm.yml)): a plan job splits the pending compiles into chunks, up to 20 machines compile in parallel (one core version per machine), and a publish job merges the results into the `results` branch and deploys the site. It runs daily and can be started by hand from the Actions tab.

## Disk and time

- **Disk:** about 25 GB. The four cores with their toolchains take ~3–7 GB each, plus the library store, the logs and the build cache.
- **Paths:** keep the farm directory on a short path **without spaces or non-ASCII characters**. The ESP32 toolchains fail on such paths. The default is `~/esp32farm` on Linux and `C:\esp32farm` on Windows. Override it with the `ESP32FARM` environment variable.
- **Time:** a full wave-1 run is ~5,800 compiles. With the core cache warm, a small example takes ~20–30 s of CPU on Linux; large libraries take several minutes. On Windows, compiles are several times slower (process start-up and antivirus scanning).

## Steps

```bash
# 1. Install arduino-cli and the four cores (each in its own sealed data directory)
python3 farm/setup_cores.py

# 2. Build the test plan: download the Library Manager index, the library versions
#    (checksum-verified), pick the example sketches, resolve dependencies
python3 farm/prepare.py --refresh

# 3. Compile. Resumable: re-running skips everything already done.
python3 farm/run.py --latest-only        # newest version of every library first (the headline)
python3 farm/run.py                       # then everything else

# 4. Export results and logs for the website, then open site/index.html through a web server
python3 farm/export.py
python3 -m http.server -d site 8000
```

On Windows use `py -3.11` instead of `python3`.

### Useful options for `run.py`

| Option | Effect |
|---|---|
| `--workers N` | parallel compiles (default 6) |
| `--only "FastLED" "ArduinoJson"` | only these libraries |
| `--cores 3.3.12 4.0.0` / `--chips esp32c3` | subset of the matrix |
| `--limit 20` | stop after 20 compiles (pilot) |
| `--retry-infra` | re-run cells that hit a farm problem |

### Daily update

```bash
python3 farm/update.py            # new library releases -> plan -> compile -> retry farm problems -> export
python3 farm/update.py --dry-run  # only list what is new
```

### After changing the farm

```bash
python3 farm/reclassify.py --dry-run                      # what a classify.py rule change would change
python3 farm/reclassify.py                                # apply it to stored logs (never touches a pass)
python3 farm/invalidate.py --missing-header Foo.h         # farm-bug correction: recompile those failures
```

The cloud workflow runs `reclassify.py` on every publish, and takes `invalidate_headers` as a manual input. Record every correction in [methodology.md](methodology.md#corrections).

`update.py` also reports new Arduino-ESP32 core releases. Adding a core column is a scope decision: add the version to `CORES` in [`farm/common.py`](../farm/common.py), run `setup_cores.py`, then `run.py`.

## Where things are

| Path (under the farm directory) | Contents |
|---|---|
| `bin/arduino-cli` | pinned arduino-cli |
| `cores/<version>/` | one sealed arduino-cli data dir + config per core |
| `cache/<version>/` | precompiled-core cache and build folders |
| `L/` | library store: one folder per library version |
| `plan.json` | the test plan (libraries, versions, examples, dependencies) |
| `results.db` | SQLite: `results` (one row per compile), `extras` (undeclared libraries examples need), `index_seen` (library versions already planned) |
| `logs/<core>/<id>.log.gz` | the full log of every compile |

## How the pieces fit

```
selection.json ─▶ prepare.py ─▶ plan.json ─▶ run.py ──▶ arduino-cli compile ──▶ log
                                               │                                  │
                                               └──── classify.py (fixed rules) ◀──┘
                                               ▼
                                          results.db ─▶ export.py ─▶ site/data/results.json + site/logs/
```

The status rules are described in [methodology.md](methodology.md).
