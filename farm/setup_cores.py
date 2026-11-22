"""One-time farm setup: download arduino-cli and install each core version in its own sealed data dir.

    py -3.11 farm/setup_cores.py              # all cores in common.CORES
    python3 farm/setup_cores.py 4.0.0 3.3.12  # only these

Safe to re-run: finished installs are skipped.
"""
import io
import os
import platform
import subprocess
import sys
import tarfile
import urllib.request
import zipfile

from common import FARM, CLI, CLI_VERSION, CORE_INDEX_URL, CORES, core_config, core_platform_dir, child_env


def get_cli():
    if CLI.exists():
        return
    system = {"Windows": "Windows", "Linux": "Linux", "Darwin": "macOS"}[platform.system()]
    arch = "64bit" if platform.machine().lower() in ("amd64", "x86_64") else "ARM64"
    ext = "zip" if system == "Windows" else "tar.gz"
    url = f"https://downloads.arduino.cc/arduino-cli/arduino-cli_{CLI_VERSION}_{system}_{arch}.{ext}"
    print("downloading", url)
    data = urllib.request.urlopen(url, timeout=300).read()
    CLI.parent.mkdir(parents=True, exist_ok=True)
    if ext == "zip":
        zipfile.ZipFile(io.BytesIO(data)).extract(CLI.name, CLI.parent)
    else:
        with tarfile.open(fileobj=io.BytesIO(data)) as t:
            t.extract(CLI.name, CLI.parent)
        os.chmod(CLI, 0o755)


def write_config(core):
    base = FARM / "cores" / core
    (base / "data").mkdir(parents=True, exist_ok=True)
    (base / "user").mkdir(parents=True, exist_ok=True)
    p = lambda x: str(x).replace("\\", "/")
    core_config(core).write_text(
        "board_manager:\n  additional_urls:\n    - " + CORE_INDEX_URL + "\n"
        f"directories:\n  data: {p(base / 'data')}\n  downloads: {p(FARM / 'staging')}\n  user: {p(base / 'user')}\n"
        "updater:\n  enable_notification: false\nnetwork:\n  connection_timeout: 600s\n"
        f"build_cache:\n  path: {p(FARM / 'cache' / core)}\n  compilations_before_purge: 0\n")


def install(core):
    if core_platform_dir(core).exists():
        print(f"core {core}: already installed")
        return
    write_config(core)
    cfg = ["--config-file", str(core_config(core))]
    subprocess.run([str(CLI), *cfg, "core", "update-index"], check=True, env=child_env())
    print(f"core {core}: installing (large download)…", flush=True)
    subprocess.run([str(CLI), *cfg, "core", "install", f"esp32:esp32@{core}", "--no-color"], check=True, env=child_env())


def main():
    (FARM / "tmp").mkdir(parents=True, exist_ok=True)
    get_cli()
    for core in sys.argv[1:] or CORES:
        install(core)


if __name__ == "__main__":
    main()
