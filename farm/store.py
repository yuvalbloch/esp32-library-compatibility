"""Library store: the Library Manager index, downloading/extracting exact library
versions, picking example sketches, and resolving dependencies."""
import hashlib
import re
import shutil
import threading
import urllib.request
import zipfile
from pathlib import Path

from common import INDEX_DIR, STORE, FARM, load_json, slug, version_key, is_prerelease

_index = None
_lock = threading.Lock()
_key_locks = {}


def index():
    """{name: {version: entry}} from library_index.json."""
    global _index
    if _index is None:
        raw = load_json(INDEX_DIR / "library_index.json")["libraries"]
        out = {}
        for e in raw:
            out.setdefault(e["name"], {})[e["version"]] = e
        _index = out
    return _index


def versions(name):
    """All released versions of a library, newest first."""
    return sorted(index().get(name, {}), key=version_key, reverse=True)


def pick_versions(name, n):
    vs = versions(name)
    stable = [v for v in vs if not is_prerelease(v)] or vs
    return stable[:n]


def _satisfies(v, constraint):
    """Library Manager dependency constraints: '=1.2', '>=1.0', '>1', '<2', '<=2' (space or && separated)."""
    if not constraint:
        return True
    for part in re.split(r"\s*(?:&&|,|\s)\s*", constraint.strip()):
        m = re.match(r"^(>=|<=|>|<|=|\^|~)?\s*v?([\w.\-+]+)$", part)
        if not m:
            continue
        op, ref = m.group(1) or "=", m.group(2)
        a, b = version_key(v), version_key(ref)
        ok = {"=": a == b, ">=": a >= b, ">": a > b, "<=": a <= b, "<": a < b,
              "^": a >= b, "~": a >= b}[op]
        if not ok:
            return False
    return True


def resolve_dep_version(name, constraint=None):
    vs = versions(name)
    if not vs:
        return None
    stable = [v for v in vs if not is_prerelease(v)] or vs
    for v in stable:
        if _satisfies(v, constraint):
            return v
    return stable[0]


def deps_closure(name, version, skip=()):
    """Declared dependencies (recursive) -> {dep_name: version}. Unknown names are ignored."""
    out, todo, seen = {}, [(name, version)], set()
    while todo:
        n, v = todo.pop()
        if (n, v) in seen:
            continue
        seen.add((n, v))
        entry = index().get(n, {}).get(v)
        for d in (entry or {}).get("dependencies") or []:
            dn = d["name"]
            if dn == name or dn in out or dn in skip or dn not in index():
                continue
            dv = resolve_dep_version(dn, d.get("version"))
            out[dn] = dv
            todo.append((dn, dv))
    return out


def lib_dir(name, version):
    """Store dir holding exactly one library folder (passed to arduino-cli via --libraries)."""
    return STORE / (slug(name)[:28] + "-" + slug(version))


def lib_root(name, version):
    return lib_dir(name, version) / slug(name)


def ensure(name, version):
    """Download + verify + extract a library version into the store (idempotent, thread-safe)."""
    root = lib_root(name, version)
    if (root / ".ok").exists():
        return root
    with _lock:
        key_lock = _key_locks.setdefault((name, version), threading.Lock())
    with key_lock:
        if (root / ".ok").exists():
            return root
        entry = index()[name][version]
        zdir = FARM / "dl" / "zips"
        zdir.mkdir(parents=True, exist_ok=True)
        zpath = zdir / entry["archiveFileName"]
        algo, want = entry["checksum"].split(":", 1)
        if not zpath.exists() or _hash(zpath, algo) != want.lower():
            req = urllib.request.Request(entry["url"], headers={"User-Agent": "esp32-compat-farm"})
            with urllib.request.urlopen(req, timeout=300) as r, open(zpath, "wb") as f:
                shutil.copyfileobj(r, f)
            got = _hash(zpath, algo)
            if got != want.lower():
                zpath.unlink()
                raise RuntimeError(f"checksum mismatch for {name}@{version}")
        d = lib_dir(name, version)
        if d.exists():
            shutil.rmtree(d)
        tmp = d.parent / (d.name + ".tmp")
        if tmp.exists():
            shutil.rmtree(tmp)
        with zipfile.ZipFile(zpath) as z:
            z.extractall(tmp)
        tops = [p for p in tmp.iterdir()]
        src = tops[0] if len(tops) == 1 and tops[0].is_dir() else tmp
        d.mkdir(parents=True)
        shutil.move(str(src), str(root))
        shutil.rmtree(tmp, ignore_errors=True)
        (root / ".ok").write_text("ok")
        return root


def _hash(path, algo):
    h = hashlib.new(algo.lower().replace("-", ""))
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


# ---------------- examples ----------------
OTHER_PLATFORMS = re.compile(
    r"esp8266|8266|avr|atmega|attiny|arduino[_ ]?(uno|mega|nano|due|zero)|uno|mega2560|teensy|rp2040|rp2350|pico|"
    r"stm32|nrf5|nrf52|samd|sam21|portenta|giga|renesas|wio|seeed|rak4631|mkr|wiz|w5500|enc28j60", re.I)
CANONICAL = re.compile(r"^(basics?|simple|simpletest|hello_?world|helloworld|blink|strandtest|minimal|basic_?usage|"
                       r"getting_?started|demo|first_?test|\d*_?simple\w*|\w*_basic|basic\w*|simple\w*)$", re.I)
BASIC = re.compile(r"basic|simple|hello|minimal|getting|blink", re.I)
NEEDS_EXTRAS = re.compile(r"psram|sd_?card|sdcard|_sd\b|ethernet|\beth\b|eth$|camera|a2dp|lte|gsm|modem|spiffs|littlefs", re.I)
ESP32_GENERIC = re.compile(r"esp32(?![-_ ]?[schp]\d)", re.I)
ESP32_VARIANT = re.compile(r"esp32[-_ ]?[schp]\d", re.I)


def list_examples(root):
    """Relative paths (posix) of example sketch folders: dirs containing <dirname>.ino."""
    out = []
    for exdir in ("examples", "Examples", "example"):
        base = root / exdir
        if not base.is_dir():
            continue
        for ino in base.rglob("*.ino"):
            if ino.stem == ino.parent.name:
                out.append(ino.parent.relative_to(root).as_posix())
        break
    return sorted(set(out))


# Read the sketch itself, not only its folder name: examples written for another board fail
# on any ESP32 for reasons that have nothing to do with the library.
# Each rule is narrow on purpose: it must only demote sketches that cannot build on a plain ESP32 board.
SRC_ESP8266_ONLY = re.compile(r"#\s*include\s*[<\"]ESP8266(?:WiFi|WebServer|HTTPClient|mDNS|httpUpdate)\w*\.h[>\"]")
SRC_ESP32_NET = re.compile(r"#\s*include\s*[<\"](?:WiFi|WebServer|HTTPClient|ESPmDNS|HTTPUpdate)\.h[>\"]")
SRC_ESP32 = re.compile(r"ESP32|ARDUINO_ARCH_ESP32", re.I)


def sketch_source(root, rel):
    d = root / rel
    text = []
    for f in sorted(d.iterdir()) if d.is_dir() else []:
        if f.suffix.lower() in (".ino", ".h", ".cpp", ".c") and f.is_file():
            try:
                text.append(f.read_text(encoding="utf-8", errors="replace"))
            except OSError:
                pass
    return "\n".join(text)


def example_score(rel, root=None):
    leaf = rel.rsplit("/", 1)[-1]
    s = 0
    if OTHER_PLATFORMS.search(rel):
        s -= 10
    if NEEDS_EXTRAS.search(rel):
        s -= 4
    if ESP32_GENERIC.search(rel):
        s += 2
    if ESP32_VARIANT.search(rel):
        s -= 3
    if CANONICAL.match(leaf):
        s += 5
    elif BASIC.search(leaf):
        s += 3
    s -= rel.count("/") * 0.5
    if root is not None:
        src = sketch_source(root, rel)
        esp_aware = bool(SRC_ESP32.search(src))
        if SRC_ESP8266_ONLY.search(src) and not esp_aware and not SRC_ESP32_NET.search(src):
            s -= 10
    return s


_overrides = None


def overrides():
    """farm/examples_override.json: {library name: [example paths]} hand-picked where the heuristic is poor."""
    global _overrides
    if _overrides is None:
        p = Path(__file__).with_name("examples_override.json")
        _overrides = load_json(p) if p.exists() else {}
    return _overrides


def pick_examples(root, n, prefer=(), name=None):
    """Up to n examples: the most 'basic' one, plus the best ESP32-specific one if there is one.
    Reuse `prefer` (the picks from the newest version) when they still exist, so the same
    sketches are compared across library versions."""
    exs = list_examples(root)
    forced = list(overrides().get(name, []))
    chosen = []
    for e in forced + list(prefer):
        if e in exs and e not in chosen and len(chosen) < n:
            chosen.append(e)
    score = {e: example_score(e, root) for e in exs}
    ranked = sorted(exs, key=lambda e: (-score[e], e))
    if not chosen and ranked:
        chosen.append(ranked[0])
    if len(chosen) < n:
        esp = [e for e in ranked if e not in chosen and ESP32_GENERIC.search(e) and score[e] > -3]
        rest = [e for e in ranked if e not in chosen and score[e] > -5]
        for e in esp[:1] + rest:
            if len(chosen) >= n:
                break
            if e not in chosen:
                chosen.append(e)
    return chosen


# ---------------- header -> library (for examples that use undeclared libraries) ----------------
def header_providers():
    """{header: [library names]} from providesIncludes (latest entry of each library)."""
    out = {}
    for name, vs in index().items():
        latest = max(vs, key=version_key)
        for h in vs[latest].get("providesIncludes") or []:
            out.setdefault(h, []).append(name)
    return out


# Well-known headers whose library does not declare providesIncludes and whose name differs from the header.
HEADER_HINTS = {
    "Adafruit_GFX.h": "Adafruit GFX Library", "Adafruit_Sensor.h": "Adafruit Unified Sensor",
    "Adafruit_I2CDevice.h": "Adafruit BusIO", "Adafruit_BusIO_Register.h": "Adafruit BusIO",
    "SoftwareSerial.h": "EspSoftwareSerial", "Adafruit_NeoPixel.h": "Adafruit NeoPixel",
    "PubSubClient.h": "PubSubClient", "ArduinoJson.h": "ArduinoJson", "U8g2lib.h": "U8g2",
    "Adafruit_SSD1306.h": "Adafruit SSD1306", "DallasTemperature.h": "DallasTemperature",
    "FastLED.h": "FastLED", "TFT_eSPI.h": "TFT_eSPI", "LiquidCrystal_I2C.h": "LiquidCrystal I2C",
    "AsyncTCP.h": "Async TCP", "ESPAsyncWebServer.h": "ESP Async WebServer", "SdFat.h": "SdFat",
    "TinyGPS++.h": "TinyGPSPlus", "RTClib.h": "RTClib", "DHT.h": "DHT sensor library",
}


def _norm(s):
    return re.sub(r"[^a-z0-9]", "", s.lower())


def header_candidates(header, providers):
    """Ranked library names that may provide `header`: a known hint, a library named like the header,
    then libraries that declare it in providesIncludes. The caller must check the header really is in it."""
    idx = index()
    out = []
    if header in HEADER_HINTS and HEADER_HINTS[header] in idx:
        out.append(HEADER_HINTS[header])
    stem = _norm(header.rsplit(".", 1)[0])
    byname = {_norm(n): n for n in idx}
    for k in (stem, stem + "library", stem + "arduino", "arduino" + stem, stem + "lib"):
        if k in byname:
            out.append(byname[k])
    out += sorted(providers.get(header, []), key=lambda c: (-len(versions(c)), c))
    seen = []
    for c in out:
        if c not in seen:
            seen.append(c)
    return seen


def has_header(root, header):
    """True if the library folder really contains `header` (where the compiler would find it)."""
    return (root / header).is_file() or (root / "src" / header).is_file()
