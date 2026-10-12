"""Exercise installation and command ordering without real lights or services."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class InstallAndModes(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.home = self.base/"home with spaces"
        self.home.mkdir()
        self.tools = self.base/"tools"
        self.tools.mkdir()
        self.log = self.base/"calls"
        self.env = dict(os.environ, HOME=str(self.home),
                        XDG_CONFIG_HOME=str(self.home/"config"),
                        XDG_DATA_HOME=str(self.home/"data"),
                        XDG_RUNTIME_DIR=str(self.base),
                        PATH=str(self.tools)+":"+os.environ["PATH"], CALL_LOG=str(self.log))
        for key in ("DISPLAY", "XAUTHORITY"):
            self.env.pop(key, None)
        systemctl = self.tools/"systemctl"
        systemctl.write_text('''#!/usr/bin/python3
import os, sys
with open(os.environ["CALL_LOG"], "a") as out:
    out.write(" ".join(sys.argv[1:])+"\\n")
if "show" in sys.argv:
    print("not-found")
if os.environ.get("FAIL_STOP") and "stop" in sys.argv:
    sys.exit(1)
''')
        systemctl.chmod(0o755)
        self.backend = self.tools/"backend"
        self.backend.write_text('#!/bin/sh\nprintf "backend %s\\n" "$*" >> "$CALL_LOG"\n')
        self.backend.chmod(0o755)
        subprocess.run(["/usr/bin/python3", str(ROOT/"install.py"), str(self.backend),
                        str(self.backend)], env=self.env, check=True, capture_output=True)
        self.log.write_text("")
        self.command = self.home/".local/bin/dx-light"

    def invoke(self, mode, **extra):
        return subprocess.run([str(self.command), mode], env=dict(self.env, **extra),
                              capture_output=True, text=True)

    def test_sync_stops_color_before_start(self):
        self.assertEqual(self.invoke("sync").returncode, 0)
        self.assertEqual(self.log.read_text().splitlines(), [
            "--user stop dx-light-color.service", "--user start dx-light-sync.service"])

    def test_color_stops_sync_before_start(self):
        self.assertEqual(self.invoke("color").returncode, 0)
        self.assertEqual(self.log.read_text().splitlines(), [
            "--user stop dx-light-sync.service", "--user start dx-light-color.service"])

    def test_failed_stop_prevents_second_writer(self):
        self.assertNotEqual(self.invoke("sync", FAIL_STOP="1").returncode, 0)
        self.assertNotIn("start", self.log.read_text())

    def test_off_stops_both_before_device_command(self):
        self.assertEqual(self.invoke("off").returncode, 0)
        calls = self.log.read_text().splitlines()
        self.assertEqual(calls[0], "--user stop dx-light-color.service dx-light-sync.service")
        self.assertTrue(calls[1].startswith("backend --config "))
        self.assertTrue(calls[1].endswith(" --off"))

    def test_failed_stop_does_not_write_off_frame(self):
        self.assertNotEqual(self.invoke("off", FAIL_STOP="1").returncode, 0)
        self.assertNotIn("backend", self.log.read_text())

    def test_fresh_install_quotes_paths_and_keeps_config(self):
        config = self.home/"config/dx-light-panel/sync.toml"
        self.assertNotIn('monitor = "HDMI-0"', config.read_text())
        config.write_text("brightness = 42\n")
        subprocess.run(["/usr/bin/python3", str(ROOT/"install.py"), str(self.backend),
                        str(self.backend)], env=self.env, check=True, capture_output=True)
        self.assertEqual(config.read_text(), "brightness = 42\n")
        unit = (self.home/"config/systemd/user/dx-light-sync.service").read_text()
        self.assertIn('ExecStart="'+str(self.home), unit)
        self.assertIn(' --config "'+str(config)+'"', unit)
        self.assertNotIn("[Install]", unit)


if __name__ == "__main__":
    unittest.main()
