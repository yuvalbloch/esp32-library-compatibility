"""Shared settings and helpers for the ESP32 compile farm.

Everything heavy (cores, library store, build dirs, logs, results DB) lives in
FARM (an ASCII-only path outside OneDrive): the ESP32 toolchains break on paths
with spaces or non-ASCII characters, and OneDrive should not sync GBs of builds.
The code and the published site live in the project folder.
"""
import json
import os
import re
import sqlite3
import time
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
FARM = Path(os.environ.get("ESP32FARM", r"C:\esp32farm" if os.name == "nt" else os.path.expanduser("~/esp32farm")))
CLI = FARM / "bin" / ("arduino-cli.exe" if os.name == "nt" else "arduino-cli")
CLI_VERSION = "1.6.0"
CORE_INDEX_URL = "https://espressif.github.io/arduino-esp32/package_esp32_index.json"
STORE = FARM / "L"          # extracted libraries: L/<id>/<LibFolder>/
BUILDS = FARM / "b"         # per-worker build dirs
CACHE = FARM / "cache"      # core build cache, per core version
LOGS = FARM / "logs"        # one gzipped log per result row
DB_PATH = FARM / "results.db"
INDEX_DIR = FARM / "dl"     # library_index.json (+ daily snapshots)
PLAN_PATH = FARM / "plan.json"
SITE = PROJECT / "site"
SELECTION = PROJECT / "selection-data" / "selection.json"

# ---- test scope (from the charter) ----
# One column per core *line*: the newest stable release of that line. farm/update.py moves a line to a
# newer release when Espressif publishes one (cores.json in the farm dir, saved with the results).
CORE_LINES = ["2.0", "3.0", "3.3", "4"]
DEFAULT_CORES = {"2.0": "2.0.17", "3.0": "3.0.7", "3.3": "3.3.12", "4": "4.0.0"}
BASELINE_LINE, TARGET_LINE = "3.3", "4"   # regression = pass on the baseline -> fail on the target
CORES_PATH = FARM / "cores.json"


def core_line(version):
    """'3.3.13' -> '3.3', '4.1.0' -> '4'; None if the version belongs to no tracked line."""
    for line in sorted(CORE_LINES, key=len, reverse=True):
        if version == line or version.startswith(line + "."):
            return line
    return None


def load_core_map():
    try:
        with open(CORES_PATH, encoding="utf-8") as f:
            m = json.load(f)
        return {l: m.get(l, DEFAULT_CORES[l]) for l in CORE_LINES}
    except (OSError, ValueError):
        return dict(DEFAULT_CORES)


_core_map = load_core_map()
CORES = [_core_map[l] for l in CORE_LINES]
BASELINE_CORE = _core_map[BASELINE_LINE]
TARGET_CORE = _core_map[TARGET_LINE]
CHIPS = ["esp32", "esp32s3", "esp32c3"]
VERSIONS_PER_LIB = 4         # latest + 3 previous releases
EXAMPLES_PER_LIB = 2
BIG_APP_OPTION = "PartitionScheme=huge_app"   # retry option when a sketch is too big
COMPILE_TIMEOUT = 20 * 60    # seconds

STATUSES = ["pass", "fail", "dep_fail", "n/a", "config", "infra_error"]


def core_config(core):
    return FARM / "cores" / core / "arduino-cli.yaml"


def core_platform_dir(core):
    return FARM / "cores" / core / "data" / "packages" / "esp32" / "hardware" / "esp32" / core


def child_env():
    """Environment for arduino-cli/gcc: ASCII temp dir (the user profile path is not ASCII)."""
    env = dict(os.environ)
    tmp = str(FARM / "tmp")
    env["TMP"] = env["TEMP"] = env["TMPDIR"] = tmp
    return env


def slug(text):
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", text).strip("_")


def version_key(v):
    """Sort key for library version strings like 1.2.10, 2.0.0-beta1."""
    parts = re.split(r"[.\-+]", v)
    key = []
    for p in parts:
        m = re.match(r"^(\d+)(.*)$", p)
        if m:
            key.append((1, int(m.group(1)), m.group(2)))
        else:
            key.append((0, 0, p))   # pre-release tags sort below numbers
    return key


def is_prerelease(v):
    return bool(re.search(r"(alpha|beta|rc|pre|dev)", v, re.I))


def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=1, ensure_ascii=False)
    os.replace(tmp, path)


SCHEMA = """
CREATE TABLE IF NOT EXISTS results (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  lib           TEXT NOT NULL,
  lib_version   TEXT NOT NULL,
  core          TEXT NOT NULL,
  chip          TEXT NOT NULL,
  example       TEXT NOT NULL,
  options       TEXT NOT NULL DEFAULT '',
  status        TEXT NOT NULL,
  first_error   TEXT,
  error_file    TEXT,
  signature     TEXT,
  root_cause    TEXT,
  deps          TEXT,          -- JSON {name: version} of every extra library given to the compiler
  duration_s    REAL,
  log_file      TEXT,
  cli_version   TEXT,
  created_at    TEXT NOT NULL,
  UNIQUE (lib, lib_version, core, chip, example, options)
);
CREATE TABLE IF NOT EXISTS extras (       -- libraries an example needs that its library does not declare
  lib TEXT, lib_version TEXT, example TEXT, deps TEXT,
  PRIMARY KEY (lib, lib_version, example)
);
CREATE TABLE IF NOT EXISTS index_seen (   -- (library, version) pairs already planned; drives the daily diff
  lib TEXT, lib_version TEXT, first_seen TEXT, PRIMARY KEY (lib, lib_version)
);
"""


def db():
    FARM.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB_PATH, timeout=60)
    con.row_factory = sqlite3.Row
    con.executescript(SCHEMA)
    return con


def now():
    return time.strftime("%Y-%m-%dT%H:%M:%S")
