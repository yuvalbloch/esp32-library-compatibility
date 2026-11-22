"""Select the initial library set for the ESP32 compatibility table.
Usage: python select_libs.py <data_dir>
Implements library-selection-plan.md (gates G1-G5, scores S1-S6, category balance, must-include).
"""
import json, os, re, sys, glob, zipfile, subprocess, datetime
from concurrent.futures import ThreadPoolExecutor

D = sys.argv[1]
ZIPS = os.path.join(D, 'zips'); os.makedirs(ZIPS, exist_ok=True)
TODAY = datetime.datetime(2026, 11, 21)

def repo_name(x):
    r = (x.get('repository') or '').rstrip('/').replace('.git', '')
    return norm(r.split('/')[-1]) if r else ''

def repo_owner(x):
    r = (x.get('repository') or '').rstrip('/').replace('.git', '').split('/')
    return r[-2].lower() if len(r) >= 2 else ''

def norm(s):
    return re.sub(r'[^a-z0-9]', '', s.lower())

def vkey(v):
    return [int(p) if p.isdigit() else 0 for p in re.split(r'[.\-+]', v)]

# ---------- load Arduino index, latest version per library ----------
idx = json.load(open(os.path.join(D, 'library_index.json'), encoding='utf-8'))['libraries']
latest, nversions = {}, {}
for x in idx:
    n = x['name']; nversions[n] = nversions.get(n, 0) + 1
    if n not in latest or vkey(x['version']) > vkey(latest[n]['version']):
        latest[n] = x
print('Arduino index: %d libraries' % len(latest))

# ---------- Espressif tested + bundled ----------
esp_tested, esp_tested_repos = set(), set()
for e in json.load(open(os.path.join(D, 'lib.json'), encoding='utf-8')):
    if e.get('name'): esp_tested.add(norm(e['name']))
    else:
        parts = e['source-url'].rstrip('/').replace('.git', '').split('/')
        esp_tested_repos.add((parts[-2].lower(), norm(parts[-1])))
    # 'required-libs' (AsyncTCP) are compiled in their test as a dependency -> counted as (indirectly) tested
    for r in e.get('required-libs', []):
        parts = r['source-url'].rstrip('/').replace('.git', '').split('/')
        esp_tested_repos.add((parts[-2].lower(), norm(parts[-1])))
def is_esp_tested(n, x):
    return norm(n) in esp_tested or (repo_owner(x), repo_name(x)) in esp_tested_repos
bundled = set(norm(x['name']) for x in json.load(open(os.path.join(D, 'bundled.json'), encoding='utf-8')) if '.' not in x['name'])

# ---------- G1 / G2 ----------
def arch_ok(x):
    a = [s.lower() for s in x.get('architectures', [])]
    return '*' in a or any('esp32' in s for s in a)
elig = {n: x for n, x in latest.items() if arch_ok(x) and norm(n) not in bundled}
print('G1+G2 (claims ESP32, not bundled in core): %d' % len(elig))

# ---------- S3 reverse dependencies ----------
revdeps = {}  # dependency -> set of dependent repo owners
for n, x in latest.items():
    for dep in x.get('dependencies', []):
        k = norm(dep['name'])
        revdeps.setdefault(k, set()).add(repo_owner(x) or n)
def rd_count(n, x):  # distinct OTHER authors depending on it (stops one author inflating own libs)
    return len(revdeps.get(norm(n), set()) - {repo_owner(x)})

# ---------- PlatformIO popularity (S1 stars, S2 download rank, S5 date) ----------
pio = {}
for f in sorted(glob.glob(os.path.join(D, 'pio_*.json'))):
    for it in json.load(open(f, encoding='utf-8'))['items']:
        k = norm(it['name'])
        if k not in pio or it['popularity_rank'] < pio[k]['popularity_rank']:
            pio[k] = it

name_count = {}
for n in latest:
    name_count[norm(n)] = name_count.get(norm(n), 0) + 1
    if repo_name(latest[n]) and repo_name(latest[n]) != norm(n):
        name_count[repo_name(latest[n])] = name_count.get(repo_name(latest[n]), 0) + 1
def pio_match(n, x):
    for k in (norm(n), repo_name(x)):
        it = pio.get(k)
        if it and it['owner']['username'].lower() == repo_owner(x):
            return it
    it = pio.get(norm(n))
    if it and name_count.get(norm(n), 0) == 1:
        return it
    return None

pool = []
for n, x in elig.items():
    it = pio_match(n, x)
    rd = rd_count(n, x)
    if it or rd >= 5:
        pool.append({'name': n, 'x': x, 'pio': it, 'revdeps': rd})
print('Pool with popularity data (in PlatformIO top 800 or >=5 reverse deps): %d' % len(pool))

def pct(values):
    """value -> percentile rank 0..100 (ties share rank)."""
    s = sorted(values)
    return lambda v: 100.0 * sum(1 for t in s if t < v) / max(1, len(s) - 1)

stars = [p['pio']['stars_count'] for p in pool if p['pio']]
ranks = [-p['pio']['popularity_rank'] for p in pool if p['pio']]
P1, P2, P3 = pct(stars), pct(ranks), pct([p['revdeps'] for p in pool])
for p in pool:
    p['S1'] = P1(p['pio']['stars_count']) if p['pio'] else 50.0
    p['S2'] = P2(-p['pio']['popularity_rank']) if p['pio'] else 50.0
    p['S3'] = P3(p['revdeps'])
    p['pop'] = (20 * p['S1'] + 15 * p['S2'] + 15 * p['S3']) / 50

# ---------- G4 dedupe (same main header or same repo name) ----------
# Keep the "real" copy: the one PlatformIO links to the same GitHub owner beats a name-alike fork
pool.sort(key=lambda p: (p['pio'] is None, -p['pop']))
seen, dedup, dropped_dupes = {}, [], []
for p in pool:
    keys = {'n:' + norm(p['name'])}
    inc = p['x'].get('providesIncludes') or []
    if inc: keys.add('h:' + inc[0].lower())
    if repo_name(p['x']): keys.add('r:' + repo_name(p['x']))
    hit = next((seen[k] for k in keys if k in seen), None)
    if hit:
        dropped_dupes.append((p['name'], hit)); continue
    for k in keys: seen[k] = p['name']
    dedup.append(p)
dedup.sort(key=lambda p: -p['pop'])
print('After G4 dedupe: %d (dropped %d duplicates/forks)' % (len(dedup), len(dropped_dupes)))

# ---------- download top N + Espressif-tested for the code scan ----------
TOPN = 260
scan = dedup[:TOPN] + [p for p in dedup[TOPN:] if is_esp_tested(p['name'], p['x'])]
for n in latest:  # Espressif-tested libs lacking popularity data still go in
    if is_esp_tested(n, latest[n]) and not any(norm(p['name']) == norm(n) for p in scan):
        scan.append({'name': n, 'x': latest[n], 'pio': None, 'revdeps': rd_count(n, latest[n]),
                     'S1': 50.0, 'S2': 50.0, 'S3': 0.0, 'pop': 0.0})

def fetch(p):
    path = os.path.join(ZIPS, p['x']['archiveFileName'])
    if not os.path.exists(path) or os.path.getsize(path) == 0:
        subprocess.call(['curl', '-s', '-L', '-o', path, p['x']['url']])
    p['zip'] = path
with ThreadPoolExecutor(12) as ex:
    list(ex.map(fetch, scan))

# ---------- S4 risk / S6 multi-chip / G3 / G5 ----------
RISK = [  # (points, label, regex)
    (3, 'includes legacy ESP-IDF driver header', r'#\s*include\s*[<"]driver/(rmt|timer|ledc|i2s|adc|dac|pcnt|mcpwm|sigmadelta|periph_ctrl|can|touch_pad|rtc_io)\.h'),
    (3, 'uses ESP-IDF headers removed/renamed in IDF 5-6', r'#\s*include\s*[<"](soc/soc_memory_types\.h|soc_memory_types\.h|esp_spi_flash\.h|esp_adc_cal\.h|esp32/rom/[^">]+|rom/[^">]+|esp_int_wdt\.h|hal/gpio_ll\.h|soc/[a-z_]+_struct\.h|soc/[a-z_]+_reg\.h)'),
    (2, 'calls mbedTLS crypto directly', r'\bmbedtls_\w+\s*\('),
    (2, 'drives timer/PWM/RMT/I2S/DMA hardware APIs', r'\b(ledcSetup|ledcAttachPin|ledcAttach|ledc_\w+|timerBegin|timerAlarm\w*|timerAttachInterrupt|gptimer_\w+|rmt_\w+|i2s_\w+|mcpwm_\w+|pcnt_\w+|gdma_\w+|spi_bus_\w+|lcd_panel_\w+|esp_lcd_\w+)\s*\('),
    (1, 'has core-version guards (ESP_ARDUINO_VERSION / ESP_IDF_VERSION)', r'\b(ESP_ARDUINO_VERSION|ESP_IDF_VERSION)\w*'),
    (1, 'includes other ESP-IDF internals', r'#\s*include\s*[<"](esp_\w+\.h|freertos/\w+\.h|soc/\w+\.h|hal/\w+\.h|esp_private/\w+\.h)'),
]
RISK = [(pt, lb, re.compile(rx)) for pt, lb, rx in RISK]
CHIP = re.compile(r'CONFIG_IDF_TARGET_(ESP32\w*)')
SRC_EXT = ('.h', '.hpp', '.c', '.cpp', '.cc', '.ino', '.pde', '.tpp', '.ipp')

def scan_zip(p):
    risk_hits, chips, n_ex, esp_mention, avr_only = set(), set(), 0, False, False
    try:
        z = zipfile.ZipFile(p['zip'])
    except Exception as e:
        p['scan_error'] = str(e); return
    avr_hdr = False
    for name in z.namelist():
        low = name.lower()
        if low.endswith(('.ino', '.pde')) and '/examples/' in '/' + low: n_ex += 1
        if not low.endswith(SRC_EXT) or z.getinfo(name).file_size > 2_000_000: continue
        t = z.read(name).decode('utf-8', 'ignore')
        for pt, lb, rx in RISK:
            if rx.search(t): risk_hits.add((pt, lb))
        chips |= set(CHIP.findall(t))
        if re.search(r'ESP32|ESP_PLATFORM|ARDUINO_ARCH_ESP32|ESP8266|__XTENSA__|ARDUINO_ARCH_\w+', t): esp_mention = True
        if re.search(r'#\s*include\s*[<"]avr/(io|interrupt|wdt|sleep|power)\.h', t) and '/examples/' not in '/' + low: avr_hdr = True
    p['risk_hits'] = sorted(risk_hits, reverse=True)
    p['risk_raw'] = min(10, sum(pt for pt, _ in risk_hits))
    p['chips'] = len(chips)
    p['n_examples'] = n_ex
    p['avr_only'] = avr_hdr and not esp_mention

for p in scan: scan_zip(p)

excluded = []
cand = []
for p in scan:
    why = None
    if p.get('scan_error'): why = 'download failed'
    elif p['n_examples'] == 0: why = 'G3: no example sketches'
    elif p['avr_only']: why = 'G5: AVR-only code, no ESP32 path'
    (excluded.append((p['name'], why)) if why else cand.append(p))

# ---------- S5 maintenance ----------
def months_since(p):
    if not p['pio']: return None
    d = datetime.datetime.strptime(p['pio']['version']['released_at'][:10], '%Y-%m-%d')
    return (TODAY - d).days / 30.4

PR, PM, PC = pct([p['risk_raw'] for p in cand]), pct([-(months_since(p) or 0) for p in cand if p['pio']]), pct([p['chips'] for p in cand])
for p in cand:
    p['S4'] = PR(p['risk_raw'])
    m = months_since(p)
    p['S5'] = PM(-m) if m is not None else 50.0
    p['months'] = m
    p['S6'] = PC(p['chips'])
    p['score'] = (20 * p['S1'] + 15 * p['S2'] + 15 * p['S3'] + 35 * p['S4'] + 10 * p['S5'] + 5 * p['S6']) / 100
    p['esp_tested'] = is_esp_tested(p['name'], p['x'])

# ---------- categories ----------
CATS = [
    ('Bluetooth', r'\b(ble|bluetooth|nimble|gamepad)'),
    ('LEDs', r'(neopixel|ws28\d\d|fastled|addressable|\bled strip|\bleds?\b|apa102|sk6812|hub75)'),
    ('Displays', r'(display|tft|oled|lcd|gfx|lvgl|e-?paper|eink|e-ink|ssd13|st77|ili9|u8g2|7-segment|matrix)'),
    ('Audio', r'(audio|\bi2s\b|\bmp3\b|\bsound\b|speaker|dfplayer|microphone|\bwav\b|\btones?\b|buzzer|rtttl|\bmidi\b)'),
    ('Motors/Servos', r'(servo|motor|stepper|pwm driver|pca9685)'),
    ('Networking/Web', r'(wifi|wi-fi|mqtt|http|web|tcp|udp|ethernet|websocket|ota\b|telegram|firebase|ntp|modbus|lora|espnow|esp-now|network|cloud|blynk|email|smtp)'),
    ('Storage/Files', r'(\bsd\b|sd card|eeprom|flash|file ?system|littlefs|spiffs|fram|storage)'),
    ('Sensors', r'(sensor|temperature|humidity|pressure|accelerometer|gyro|imu|bme|bmp|dht|ds18b20|onewire|one-wire|adc\b|rfid|mfrc|gps|ultrasonic|distance|light sensor|ambient light|color sensor|ir\b|infrared|irremote|rtc|clock|touch)'),
]
def category(p):
    x = p['x']
    t = ' '.join([p['name'], x.get('sentence', '')]).lower()
    t = re.sub(r'nano 33 ble( sense)?|nano ble', 'nano-board', t)  # board names are not a Bluetooth feature
    ac = x.get('category', '')
    if re.search(r'usb\b|power management|\bpmu\b|watchdog', t): return 'Utilities'
    if re.search(r'\b(ssl|tls|ssh)\b|wolfssl|homekit|open sound control', t): return 'Networking/Web'
    for c, rx in CATS:
        if re.search(rx, t): return c
    if ac == 'Display': return 'Displays'
    if ac == 'Sensors': return 'Sensors'
    if ac == 'Data Storage': return 'Storage/Files'
    if ac == 'Communication': return 'Networking/Web'
    return 'Utilities'
for p in cand: p['cat'] = category(p)

# ---------- final selection: all Espressif-tested + 50 untested ----------
cand.sort(key=lambda p: -p['score'])
tested = [p for p in cand if p['esp_tested']]
untested = [p for p in cand if not p['esp_tested']]
N, MINCAT = 50, 3
# Plan 2.5 must-include names (FastLED, Adafruit NeoPixel, ESPAsyncWebServer are Espressif-tested, so they are in 'tested')
MUST = ['ArduinoJson', 'TFT_eSPI', 'PubSubClient', 'NimBLE-Arduino', 'WiFiManager']
for p in untested: p['must'] = p['name'] in MUST
sel = [p for p in untested if p['must']]
for p in untested:
    if len(sel) >= N: break
    if p not in sel: sel.append(p)
for c, _ in CATS + [('Utilities', '')]:
    while sum(1 for p in sel if p['cat'] == c) < MINCAT:
        nxt = next((p for p in untested if p['cat'] == c and p not in sel), None)
        if not nxt: break
        counts = {}
        for p in sel: counts[p['cat']] = counts.get(p['cat'], 0) + 1
        victim = next((p for p in sorted(sel, key=lambda q: q['score']) if counts[p['cat']] > MINCAT and p['cat'] != c and not p.get('must')), None)
        if not victim: break
        sel.remove(victim); sel.append(nxt); nxt['swapped_in'] = True
sel.sort(key=lambda p: -p['score'])

def row(p):
    return {
        'name': p['name'], 'version': p['x']['version'], 'versions_released': nversions[p['name']],
        'repo': p['x'].get('repository', ''), 'category': p['cat'], 'espressif_tested': p['esp_tested'],
        'score': round(p['score'], 1), 'S1_stars_pct': round(p['S1']), 'S2_downloads_pct': round(p['S2']),
        'S3_revdeps_pct': round(p['S3']), 'S4_risk_pct': round(p['S4']), 'S5_fresh_pct': round(p['S5']), 'S6_chips_pct': round(p['S6']),
        'stars': p['pio']['stars_count'] if p['pio'] else None, 'pio_rank': p['pio']['popularity_rank'] if p['pio'] else None,
        'revdeps': p['revdeps'], 'risk_raw': p['risk_raw'], 'risk_reasons': [lb for _, lb in p['risk_hits']],
        'months_since_release': round(p['months'], 1) if p['months'] is not None else None,
        'chip_branches': p['chips'], 'examples': p['n_examples'], 'swapped_in_for_category': p.get('swapped_in', False), 'must_include': p.get('must', False),
    }

out = {
    'generated': TODAY.strftime('%Y-%m-%d'),
    'funnel': {'index': len(latest), 'g1_g2': len(elig), 'pool': len(pool), 'dedup': len(dedup), 'scanned': len(scan), 'candidates': len(cand)},
    'untested_selected': [row(p) for p in sel],
    'espressif_tested': [row(p) for p in tested],
    'espressif_list': sorted(esp_tested),
    'next_in_line': [row(p) for p in untested if p not in sel][:30],
    'excluded_after_scan': excluded,
    'dupes_dropped_top': [d for d in dropped_dupes if d[1] in [p['name'] for p in dedup[:120]]][:40],
    'top100_names': [p['name'] for p in cand[:100]],
    'untested_rank': {p['name']: i + 1 for i, p in enumerate(untested)},
}
json.dump(out, open(os.path.join(D, 'selection.json'), 'w', encoding='utf-8'), indent=1, ensure_ascii=False)
print(json.dumps(out['funnel']))
for p in tested: print('TESTED  %5.1f %-28s %s' % (p['score'], p['name'], p['cat']))
for i, p in enumerate(sel, 1):
    print('%2d %5.1f %-34s %-15s risk=%2d stars=%s rd=%d %s' % (i, p['score'], p['name'], p['cat'], p['risk_raw'],
          p['pio']['stars_count'] if p['pio'] else '-', p['revdeps'], ('[cat swap]' if p.get('swapped_in') else '') + ('[must]' if p.get('must') else '') + (' #%d' % (untested.index(p) + 1))))
print('EXCLUDED', excluded[:40])
