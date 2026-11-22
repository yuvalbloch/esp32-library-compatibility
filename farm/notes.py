"""Explanatory notes shown next to results. Notes never change a status.

1. Chip hardware notes: when a build fails and its first error is about a peripheral that the chip
   does not have (facts from Espressif's datasheets), the cell gets a note such as "ESP32-C3 has no
   touch sensor". The ✗ stays: the sketch really does not compile on that chip, but the reader learns
   that the library cannot be expected to support it there.
2. Library notes (farm/library_notes.json): short hand-written context for libraries whose examples
   are made for one specific board or need special settings.
"""
import re
from pathlib import Path

from common import load_json

CHIP_LABEL = {"esp32": "ESP32", "esp32s3": "ESP32-S3", "esp32c3": "ESP32-C3"}

# (peripheral description, error pattern)
PERIPHERALS = {
    "touch": ("touch sensor", r"\btouchRead\b|\btouchAttachInterrupt\b|\btouch_pad_|SOC_TOUCH"),
    "pcnt": ("pulse counter (PCNT)", r"\bpcnt|PCNT"),
    "sdmmc": ("SD/MMC host", r"\bSD_MMC\b|\bsdmmc_"),
    "mcpwm": ("motor-control PWM (MCPWM)", r"\bmcpwm|MCPWM"),
    "dac": ("DAC", r"\bdac_|\bdacWrite\b|\bDAC_CHAN"),
    "usb_otg": ("USB-OTG (needed for USB device mode)", r"Adafruit_USBD_|TinyUSBDevice|\btud_|\bTUD_|\btusb_|USB-OTG"),
    "i2s_parallel": ("parallel I2S / LCD peripheral", r"I2s1X8|I2sParallel|i2s_parallel|Bus_Parallel"),
}

# Peripherals each chip does NOT have.
LACKS = {
    "esp32": {"usb_otg"},
    "esp32s3": {"dac"},
    "esp32c3": {"touch", "pcnt", "sdmmc", "mcpwm", "dac", "usb_otg", "i2s_parallel"},
}

_RX = {k: re.compile(p) for k, (_, p) in PERIPHERALS.items()}


def hardware_note(chip, status, first_error):
    if status not in ("fail", "dep_fail") or not first_error:
        return ""
    for p in sorted(LACKS.get(chip, ())):
        if _RX[p].search(first_error):
            return f"{CHIP_LABEL.get(chip, chip)} has no {PERIPHERALS[p][0]}; this failure is expected on this chip."
    return ""


_lib_notes = None


def library_note(name):
    global _lib_notes
    if _lib_notes is None:
        p = Path(__file__).with_name("library_notes.json")
        _lib_notes = load_json(p) if p.exists() else {}
    return _lib_notes.get(name, "")
