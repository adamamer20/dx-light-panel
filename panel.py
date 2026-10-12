#!/usr/bin/python3
# SPDX-License-Identifier: MIT
"""A native mode picker for separately installed DX Light controllers."""
import os
from pathlib import Path
import subprocess
import threading

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import GLib, Gtk


class Panel(Gtk.Application):
    def __init__(self):
        super().__init__(application_id="local.dxlight.controls")
        self.window = None
        self.status = None
        self.buttons = []
        self.busy = False

    def do_activate(self):
        if self.window is not None:
            self.window.present()
            return
        self.window = Gtk.ApplicationWindow(application=self, title="DX Light")
        self.window.set_default_size(390, 270)
        self.window.set_border_width(20)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        self.window.add(box)
        label = Gtk.Label()
        label.set_markup("<big><b>Control your lights</b></big>")
        box.pack_start(label, False, False, 0)
        for text, mode in [("Still color — open color picker", "color"),
                           ("Sync with screen", "sync"), ("Turn lights off", "off")]:
            button = Gtk.Button(label=text)
            button.connect("clicked", self.choose, mode)
            self.buttons.append(button)
            box.pack_start(button, False, False, 0)
        self.status = Gtk.Label(label="Checking mode…")
        self.status.set_line_wrap(True)
        box.pack_start(self.status, False, False, 0)
        hint = Gtk.Label(label="Screen sync uses your primary monitor by default. "
                        "Closing this window keeps the lights running.")
        hint.set_line_wrap(True)
        box.pack_start(hint, False, False, 0)
        self.window.show_all()
        self.refresh()
        GLib.timeout_add_seconds(2, self.refresh)

    def choose(self, button, mode):
        self.busy = True
        self.status.set_text("Switching mode…")
        for control in self.buttons:
            control.set_sensitive(False)
        threading.Thread(target=self.switch, args=(mode,), daemon=True).start()

    def switch(self, mode):
        try:
            result = subprocess.run([str(Path.home()/".local/bin/dx-light"), mode],
                                    capture_output=True, text=True, timeout=60)
            error = result.stderr.strip() if result.returncode else ""
            if result.returncode and not error:
                error = f"Mode command exited with status {result.returncode}."
        except (OSError, subprocess.TimeoutExpired) as exc:
            error = str(exc)
        GLib.idle_add(self.finished, error)

    def finished(self, error):
        self.busy = False
        for control in self.buttons:
            control.set_sensitive(True)
        if error:
            dialog = Gtk.MessageDialog(transient_for=self.window,
                message_type=Gtk.MessageType.ERROR, buttons=Gtk.ButtonsType.CLOSE,
                text="Could not switch lighting mode")
            dialog.format_secondary_text(error + "\nCheck device permissions and the service logs.")
            dialog.run()
            dialog.destroy()
        self.refresh()
        return False

    def refresh(self):
        if self.status is None or self.busy:
            return True
        try:
            result = subprocess.run(["systemctl", "--user", "show", "--property=ActiveState",
                                     "--value", "dx-light-sync.service", "dx-light-color.service"],
                                    capture_output=True, text=True, timeout=3, check=True)
            states = result.stdout.split()
            if len(states) != 2:
                raise ValueError("Unexpected service status response")
            sync, color = states
            if "failed" in states:
                text = "Controller failed — check logs or try another mode"
            elif sync == "active":
                text = "Screen sync is running"
            elif color == "active":
                text = "Still color — use the color picker"
            else:
                text = "No controller running — pick a mode above"
            self.status.set_text(text)
        except (OSError, subprocess.SubprocessError, ValueError):
            self.status.set_text("Cannot read services — run the installer first")
        return True


if __name__ == "__main__":
    Panel().run()
