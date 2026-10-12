#!/usr/bin/python3
# SPDX-License-Identifier: MIT
"""Install the panel with two independently built upstream executables."""
import argparse
import os
from pathlib import Path
import shutil
import subprocess


def unit_quote(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"').replace("%", "%%") + '"'


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("color_binary", type=Path)
    parser.add_argument("sync_binary", type=Path)
    args = parser.parse_args()
    for binary in (args.color_binary, args.sync_binary):
        if not binary.is_file() or not os.access(binary, os.X_OK):
            parser.error(f"Not an executable file: {binary}")
    source = Path(__file__).resolve().parent
    data = Path(os.environ.get("XDG_DATA_HOME", Path.home()/".local/share"))/"dx-light-panel"
    config_root = Path(os.environ.get("XDG_CONFIG_HOME", Path.home()/".config"))
    config = config_root/"dx-light-panel"
    units = config_root/"systemd/user"
    applications = data.parent/"applications"
    bin_dir = Path.home()/".local/bin"
    for directory in (data/"backends", config, units, applications, bin_dir):
        directory.mkdir(parents=True, exist_ok=True)
    # Stop existing owned modes before replacing their executables/units.
    for mode in ("color", "sync"):
        service = f"dx-light-{mode}.service"
        state = subprocess.run(["systemctl", "--user", "show", "--property=LoadState", "--value", service],
                               check=True, capture_output=True, text=True, timeout=10)
        if state.stdout.strip() != "not-found":
            subprocess.run(["systemctl", "--user", "stop", service], check=True, timeout=30)
    for binary, name in ((args.color_binary, "rgb-controller"), (args.sync_binary, "quiklight")):
        shutil.copy2(binary, data/"backends"/name)
    for name in ("panel.py", "LICENSE"):
        shutil.copy2(source/name, data/name)
    shutil.copy2(source/"dx-light", bin_dir/"dx-light")
    (bin_dir/"dx-light").chmod(0o755)
    if not (config/"sync.toml").exists():
        shutil.copy2(source/"sync.toml", config/"sync.toml")
    for mode, executable, extra, other in (
        ("color", "rgb-controller", "", "sync"),
        ("sync", "quiklight", " --config " + unit_quote(str(config/"sync.toml")), "color"),
    ):
        ordering = "Before=dx-light-sync.service\n" if mode == "color" else ""
        (units/f"dx-light-{mode}.service").write_text(
            f"[Unit]\nDescription=DX Light {mode} mode\nConflicts=dx-light-{other}.service\n"
            f"After=graphical-session.target\n{ordering}\n[Service]\nType=exec\n"
            f"ExecStart={unit_quote(str(data/'backends'/executable))}{extra}\nTimeoutStopSec=5\n")
    desktop_command = unit_quote(str(bin_dir/"dx-light"))
    (applications/"dx-light-linux.desktop").write_text(
        "[Desktop Entry]\nType=Application\nName=DX Light\n"
        "Comment=Still color and screen sync for ROBOBLOQ lights\n"
        f"Exec={desktop_command} ui\nIcon=preferences-color\nTerminal=false\nCategories=Utility;\n")
    subprocess.run(["systemctl", "--user", "daemon-reload"], check=True, timeout=30)
    print(f"Installed. Open DX Light from your application menu, or run {bin_dir/'dx-light'}")


if __name__ == "__main__":
    main()
