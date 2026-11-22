"""Turn a real compile log into a status. Fixed, mechanical rules only.

The status comes from the compiler's exit code and the first error line in the
log. The rules below only decide *which* non-pass status a failed build gets
(fail / dep_fail / n/a / config / infra_error); a build that exits 0 is always
`pass`, and a build that exits non-zero is never `pass`.

`root_cause` is a human-readable explanation label for grouping in the triage
report. It never changes the status.
"""
import re

ERR_LINE = re.compile(
    r"^(?P<file>(?:[A-Za-z]:)?[^:\n]+?):(?P<line>\d+)(?::(?P<col>\d+))?:\s+(?:fatal )?error:\s+(?P<msg>.+)$", re.M)
LINK_ERR = re.compile(r"undefined reference to [`'\"]?([^'`\"\n]+)|multiple definition of [`'\"]?([^'`\"\n]+)")
LD_FAIL = re.compile(r"collect2(?:\.exe)?: error: ld returned")
TOO_BIG = re.compile(r"Sketch too big|text section exceeds available space|will not fit in region|region [`'][^'`]+['`] overflowed")
MISSING_HDR = re.compile(r"^(?P<h>[^:\s]+): No such file or directory")
INFRA = re.compile(r"Error initializing instance|platform not installed|Platform '[^']+' not found|Access is denied|"
                   r"The process cannot access the file|fork/exec|resource temporarily unavailable|"
                   r"context deadline exceeded|no space left on device|cannot open output file", re.I)

# #error text that means "this chip cannot do this" -> n/a
NA_FEATURE = re.compile(
    r"Bluetooth is not enabled|Serial Bluetooth not available|BT(?: classic)? (?:is )?not (?:available|supported)|"
    r"Bluetooth Classic|SOC_BT_CLASSIC|no DAC|DAC (?:is )?not (?:available|supported)|touch (?:is )?not supported|"
    r"(?:not (?:supported|available)|unsupported|doesn.?t support|does not support|only (?:works|supported|available))"
    r".{0,60}(?:ESP32-?[SCHP]\d|ESP32[SCHP]\d|this (?:chip|SoC|target|MCU|processor)|RISC-?V|single.core)|"
    r"(?:ESP32-?[SCHP]\d|ESP32[SCHP]\d|this (?:chip|SoC|target)|RISC-?V).{0,40}(?:not (?:supported|available)|unsupported)",
    re.I)
# #error text that is about the core / ESP-IDF version -> a real incompatibility, stays `fail`
CORE_VERSION = re.compile(r"\bcore\b|arduino-esp32|ESP-?IDF|\bIDF\b|version|3\.x|2\.x|4\.x|v[2345]\b", re.I)
# #error text that asks for different board options or a specific board -> config
NEEDS_CONFIG = re.compile(
    r"(?:select|choose|wrong|incorrect|correct|unsupported|unknown).{0,30}board|board.{0,30}(?:select|not (?:defined|selected))|"
    r"enable PSRAM|PSRAM.{0,30}(?:must|need|enable|required)|partition scheme|USB CDC On Boot|USB Mode|"
    r"TinyUSB.{0,30}(?:select|enable)|USB stack", re.I)
# #error text that asks the user to edit the sketch or a config file before it can build -> config
NEEDS_USER_EDIT = re.compile(
    r"please (?:go and )?(?:specify|define|set|uncomment|configure|edit|enter|fill|change)|\buncomment\b|"
    r"(?:must|need to) (?:be )?(?:defined|configured|set|specified)|\b[A-Z][A-Z0-9_]{3,} is required\b", re.I)
# a missing header that is a user-written configuration file (e.g. LVGL's lv_conf.h) -> config
USER_CONFIG_HDR = re.compile(r"(?:^|/)(?:lv_conf|lv_drv_conf|user_settings|my_private_config|User_Setup)\.h$")

# Explanation labels for the triage report (first match wins). Labels only; never a verdict.
ROOT_CAUSES = [
    (r"driver/(timer|rmt|i2s|adc|dac|pcnt|mcpwm|sigmadelta|sigma_delta|temp_sensor|can|periph_ctrl|touch_pad|ledc_legacy)\.h",
     "Legacy ESP-IDF driver header removed"),
    (r"esp32\w*/rom/|rom/(ets_sys|gpio|crc|md5_hash|lldesc)\.h|soc_memory_types\.h|esp_spi_flash\.h|spi_flash\.h|"
     r"esp_intr\.h|hwcrypto/|esp_secure_boot|soc/\w+_struct\.h|soc/dport|soc/(rtc|sens|syscon)_reg|esp_private/",
     "Removed or moved ESP-IDF internal header"),
    (r"ledcSetup|ledcAttachPin|ledcDetachPin|ledcChangeFrequency.*arguments|ledc_channel_t.*\bchannel\b",
     "Old LEDC (PWM) API (changed in core 3.0)"),
    (r"timerAlarmWrite|timerAlarmEnable|timerAlarmDisable|timerAttachInterrupt|timerBegin|hw_timer_t",
     "Old hardware-timer API (changed in core 3.0)"),
    (r"mbedtls|MBEDTLS|psa_|esp_sha|sha256_|md5", "Crypto (mbedTLS / PSA) API change"),
    (r"rmt_|RMT_|rmt_item32_t|rmt_config_t", "RMT driver API change"),
    (r"i2s_|I2S_", "I2S driver API change"),
    (r"adc1_|adc2_|ADC_ATTEN|adc_bits_width|esp_adc_cal", "ADC driver API change"),
    (r"gpio_pad_select_gpio|gpio_matrix_|GPIO\.(out|enable|in)|GPIO_PIN_MUX_REG|PIN_FUNC_SELECT|REG_WRITE|DPORT_",
     "Direct register / GPIO-matrix access changed"),
    (r"\[-Werror|-Werror=", "Compiler warning treated as error"),
    (r"esp_wifi|WiFiClass|WiFiGeneric|WiFiSTA|wifi_|tcpip_adapter|esp_netif|ETH\.|eth_", "Wi-Fi / network API change"),
    (r"\bBLE|esp_gap|esp_gatt|esp_bt|NimBLE|nimble", "Bluetooth API change"),
    (r"FreeRTOS|xTask|portMUX|portENTER|xQueue|xSemaphore|vTask|configTICK", "FreeRTOS API change"),
    (r"esp_sleep|esp_deep_sleep|gpio_wakeup|rtc_gpio", "Sleep / wake-up API change"),
    (r"std::string|String", "String type change (std::string vs Arduino String)"),
    (r"#error", "Library refuses this configuration (#error)"),
    (r"No such file or directory", "Missing header"),
    (r"undefined reference|multiple definition|ld returned", "Link error"),
    (r"was not declared in this scope|has no member named|is not a member of|no matching function|"
     r"too (few|many) arguments|invalid conversion|cannot convert|does not name a type|incomplete type|redefinition|conflicting",
     "API removed, renamed or changed"),
]
ROOT_CAUSES = [(re.compile(p), label) for p, label in ROOT_CAUSES]


def norm_path(p):
    return p.replace("\\", "/").lower()


def first_error(log):
    m = ERR_LINE.search(log)
    if m:
        return m.group("file").strip(), m.group("msg").strip()
    m = LINK_ERR.search(log)
    if m:
        return "", ("undefined reference to " if m.group(1) else "multiple definition of ") + (m.group(1) or m.group(2))
    if LD_FAIL.search(log):
        return "", "ld returned 1 exit status"
    return None, None


def signature(msg):
    """Error message with paths/numbers stripped, so identical root causes group together."""
    s = re.sub(r"(?:[A-Za-z]:)?[\\/][^\s'\"`:]+[\\/]", "", msg)
    s = re.sub(r"\b0x[0-9a-fA-F]+\b|\b\d+\b", "N", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s[:200]


def root_cause(msg, log=""):
    text = msg or ""
    for rx, label in ROOT_CAUSES:
        if rx.search(text):
            return label
    return "Other compile error"


def missing_header(msg):
    m = MISSING_HDR.match(msg or "")
    return m.group("h") if m else None


def classify(returncode, log, timed_out=False, dep_roots=()):
    """-> dict(status, first_error, error_file, signature, root_cause)"""
    out = {"status": None, "first_error": None, "error_file": None, "signature": None, "root_cause": None}
    if timed_out:
        out.update(status="infra_error", first_error="compile timed out", root_cause="Farm problem (timeout)")
        return out
    if returncode == 0:
        out["status"] = "pass"
        return out
    efile, msg = first_error(log)
    if TOO_BIG.search(log):
        m = TOO_BIG.search(log)
        out.update(status="config", first_error=m.group(0), signature="sketch too big for default partition",
                   root_cause="Program too big for the default flash partition")
        return out
    if msg is None:
        m = INFRA.search(log)
        out.update(status="infra_error", first_error=(m.group(0) if m else "no compiler error found in log"),
                   root_cause="Farm problem")
        return out
    out.update(first_error=msg, error_file=efile, signature=signature(msg), root_cause=root_cause(msg, log))
    status = "fail"
    if efile:
        p = norm_path(efile)
        if any(p.startswith(norm_path(str(r)) + "/") for r in dep_roots):
            status = "dep_fail"
    hdr = missing_header(msg)
    if msg.startswith("#error"):
        if NA_FEATURE.search(msg) and not CORE_VERSION.search(msg):
            status = "n/a"
        elif NEEDS_CONFIG.search(msg):
            status = "config"
        elif NEEDS_USER_EDIT.search(msg) and not CORE_VERSION.search(msg):
            status = "config"
            out["root_cause"] = "Example must be edited or configured by the user first"
    elif hdr and USER_CONFIG_HDR.search(hdr):
        status = "config"
        out["root_cause"] = "Library needs a user configuration file"
    elif NA_FEATURE.search(msg) and re.search(r"Bluetooth is not enabled|Serial Bluetooth not available", msg):
        status = "n/a"
    out["status"] = status
    return out
