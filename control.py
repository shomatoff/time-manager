#!/usr/bin/env python3
"""Desktop window for the GNOME Shell Pomodoro timer."""

import json
import math
import subprocess
import threading
import time
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
from gi.repository import Gdk, Gio, GLib, Gtk

from indicator import PanelIndicator
from timer_core import advance_state, empty_state


SCHEMA_ID = "org.gnome.shell.extensions.pomodoro-ubuntu"
SCHEMA_DIR = (
    Path.home()
    / ".local/share/gnome-shell/extensions/pomodoro-ubuntu@chainjas.local/schemas"
)
BACKGROUND = SCHEMA_DIR.parent / "black-hole.jpg"
SOUND_FILES = {
    "break": SCHEMA_DIR.parent / "break-start.oga",
    "focus": SCHEMA_DIR.parent / "break-end.oga",
}


def play_transition_sound(phase):
    """Play a short sound through the desktop sound theme without blocking the timer."""
    event = "message-new-instant" if phase == "break" else "complete"

    def worker():
        try:
            result = subprocess.run(
                ["canberra-gtk-play", "-i", event],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                timeout=5, check=False,
            )
            if result.returncode == 0:
                return
        except (OSError, subprocess.TimeoutExpired):
            pass
        try:
            subprocess.run(
                ["pw-play", str(SOUND_FILES[phase])],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                timeout=5, check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            pass

    threading.Thread(target=worker, daemon=True).start()


def read_state(settings):
    try:
        state = json.loads(settings.get_string("session-state"))
        if (
            state["phase"] in ("focus", "break")
            and isinstance(state["deadlineMs"], (int, float))
            and state["deadlineMs"] > 0
            and isinstance(state["remainingMs"], (int, float))
            and state["remainingMs"] >= 0
            and isinstance(state["paused"], bool)
            and isinstance(state["completedFocus"], int)
            and state["completedFocus"] >= 0
        ):
            state["breakKind"] = "long" if state.get("breakKind") == "long" else "short"
            return state
    except (ValueError, TypeError, KeyError):
        pass
    return empty_state()


class PomodoroApp(Gtk.Application):
    def __init__(self):
        super().__init__(application_id="uz.chainjas.PomodoroUbuntu")
        source = Gio.SettingsSchemaSource.new_from_directory(
            str(SCHEMA_DIR), Gio.SettingsSchemaSource.get_default(), False
        )
        schema = source.lookup(SCHEMA_ID, False)
        if schema is None:
            raise RuntimeError("Pomodoro sozlamalari topilmadi. Avval install.sh ni ishga tushiring.")
        self.settings = Gio.Settings.new_full(schema, None, None)
        self.window = None
        self.break_window = None
        self.break_windows = []
        self.break_labels = []
        self.indicator = None
        self._updating_spins = False
        self._warned_deadline = 0
        self._paused_by_lock = False
        self.shell_extension_active = self._shell_extension_active()

    @staticmethod
    def _shell_extension_active():
        try:
            result = subprocess.run(
                ["gnome-extensions", "info", "pomodoro-ubuntu@chainjas.local"],
                capture_output=True, text=True, timeout=3, check=False,
            )
            return result.returncode == 0 and "State: ACTIVE" in result.stdout
        except (OSError, subprocess.TimeoutExpired):
            return False

    def do_activate(self):
        if self.window is not None:
            self.window.present()
            return
        self._build_window()
        self.hold()
        self.window.connect("close-request", self._hide_control_window)
        self._sync_owner()
        self.settings.connect("changed::session-state", lambda *_: self._render())
        self.settings.connect("changed::focus-minutes", lambda *_: self._settings_changed())
        self.settings.connect("changed::break-minutes", lambda *_: self._settings_changed())
        self.settings.connect("changed::long-break-minutes", lambda *_: self._settings_changed())
        self.settings.connect("changed::cycles-before-long", lambda *_: self._settings_changed())
        self.settings.connect("changed::sound-enabled", lambda *_: self._settings_changed())
        self.settings.connect("changed::pause-on-lock", lambda *_: self._settings_changed())
        self._screen_bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
        self._screen_signal_id = self._screen_bus.signal_subscribe(
            "org.gnome.ScreenSaver", "org.gnome.ScreenSaver", "ActiveChanged",
            "/org/gnome/ScreenSaver", None, Gio.DBusSignalFlags.NONE,
            self._on_screen_lock,
        )
        GLib.timeout_add_seconds(1, self._tick)
        GLib.timeout_add_seconds(3, self._poll_owner)
        self._render()
        self.window.present()

    def _hide_control_window(self, _window):
        self.window.set_visible(False)
        return True

    def _on_screen_lock(self, _bus, _sender, _path, _interface, _signal, parameters):
        if self.shell_extension_active or not self.settings.get_boolean("pause-on-lock"):
            return
        locked = parameters.unpack()[0]
        state = read_state(self.settings)
        if locked and state["phase"] != "idle" and not state["paused"]:
            self._paused_by_lock = True
            self._toggle_pause(None)
        elif not locked and self._paused_by_lock:
            self._paused_by_lock = False
            if state["phase"] != "idle" and state["paused"]:
                self._toggle_pause(None)

    def _poll_owner(self):
        self._sync_owner()
        return GLib.SOURCE_CONTINUE

    def _sync_owner(self):
        active = self._shell_extension_active()
        self.shell_extension_active = active
        if active:
            self._paused_by_lock = False
            if self.indicator is not None:
                self.indicator.close()
                self.indicator = None
            self._close_break_windows()
        elif self.indicator is None:
            self.indicator = PanelIndicator(
                lambda: self.window.present(),
                {"primary": lambda: self._start(None) if read_state(self.settings)["phase"] == "idle"
                 else self._toggle_pause(None),
                 "skip": lambda: self._skip_break(None),
                 "stop": lambda: self._stop(None)},
            )
        if self.window is not None:
            self._render()

    def _build_window(self):
        self.window = Gtk.ApplicationWindow(application=self, title="Pomodoro Ubuntu")
        self.window.set_default_size(440, 660)
        self.window.add_css_class("pomodoro-window")
        header = Gtk.HeaderBar()
        header.add_css_class("pomodoro-header")
        header.set_title_widget(Gtk.Label(label="Pomodoro Ubuntu"))
        self.window.set_titlebar(header)

        style = Gtk.CssProvider()
        style.load_from_data(b"""
            .pomodoro-window { background-color: #101a29; color: #f1f6fb; }
            headerbar.pomodoro-header { background-image: none; background-color: #101a29; color: #f1f6fb; border-bottom: 1px solid #2b3b4e; box-shadow: none; }
            headerbar.pomodoro-header label, headerbar.pomodoro-header button { color: #f1f6fb; }
            .pomodoro-content { padding: 22px; }
            .pomodoro-timer-card { background-color: #1b2e43; border: 1px solid #334c65; border-radius: 20px; padding: 20px; }
            .pomodoro-eyebrow { color: #9cb6ca; font-size: 12px; font-weight: 700; letter-spacing: 1px; }
            .pomodoro-time { font-size: 76px; font-weight: 750; color: #ffffff; }
            .pomodoro-status { font-size: 19px; font-weight: 700; color: #a4ead9; }
            .pomodoro-cycle { color: #b6c9d8; font-size: 14px; }
            .pomodoro-section-title { color: #dceaf3; font-size: 15px; font-weight: 700; }
            .pomodoro-duration-card { background-color: #1b2b3c; border: 1px solid #30465b; border-radius: 15px; padding: 14px; }
            .pomodoro-duration-title { color: #bbcedd; font-size: 13px; font-weight: 600; }
            .pomodoro-window spinbutton { background-color: #e9f2f4; color: #10283d; border-radius: 10px; }
            .pomodoro-window spinbutton text { color: #10283d; background-color: transparent; }
            .pomodoro-window spinbutton button { color: #10283d; background-image: none; background-color: #e9f2f4; border: none; border-left: 1px solid #859aa9; box-shadow: none; }
            .pomodoro-window spinbutton button image { color: inherit; -gtk-icon-shadow: none; }
            .pomodoro-window spinbutton button:hover { background-color: #cedfe6; }
            .pomodoro-window spinbutton button:active { background-color: #b6cfd9; }
            .pomodoro-window spinbutton button:disabled { color: #637886; background-color: #dde7ec; }
            .pomodoro-window spinbutton button { color: #000000; min-width: 28px; min-height: 30px; }
            .pomodoro-window spinbutton button:disabled { color: #344550; }
            .pomodoro-window spinbutton button label { color: inherit; font-family: sans-serif; font-size: 20px; font-weight: 800; opacity: 1; }
            .pomodoro-window spinbutton text { font-size: 17px; font-weight: 600; }
            .pomodoro-main-button { min-height: 46px; border-radius: 13px; font-weight: 700; background-image: none; background-color: #177460; color: #ffffff; border: 1px solid #3ca993; box-shadow: none; }
            .pomodoro-main-button:hover { background-color: #1b806b; }
            .pomodoro-main-button:active { background-color: #125c4d; }
            .pomodoro-secondary-button { min-height: 38px; border-radius: 10px; background-image: none; background-color: #22364a; color: #e7f0f6; border: 1px solid #456078; box-shadow: none; }
            .pomodoro-secondary-button:hover { background-color: #2d465e; }
            .pomodoro-secondary-button.destructive-action { color: #ffbdc2; border-color: #825361; }
            .pomodoro-window button:focus-visible, .pomodoro-window spinbutton:focus-within { outline: 2px solid #8bdcc8; outline-offset: 2px; }
            .pomodoro-advanced { color: #cad9e5; }
            .pomodoro-advanced-box { padding: 12px 2px 2px; }
            .pomodoro-hint { color: #91a9bb; font-size: 12px; }
            progressbar.pomodoro-progress trough { min-width: 2px; min-height: 7px; border: none; border-radius: 5px; background-image: none; background-color: #344d63; box-shadow: none; }
            progressbar.pomodoro-progress progress { min-width: 2px; min-height: 7px; border: none; border-radius: 5px; background-image: none; background-color: #57d5b3; box-shadow: none; }
            .pomodoro-break-dim { background-color: rgba(0, 0, 0, 0.30); }
            .pomodoro-break-card { background-color: rgba(8, 14, 24, 0.82); border-radius: 24px; padding: 38px 50px; }
            .pomodoro-break-title { color: #9bd8c7; font-size: 27px; font-weight: 700; }
            .pomodoro-break-time { color: white; font-size: 110px; font-weight: 700; }
            .pomodoro-break-detail { color: #e8f0f5; font-size: 20px; }
        """)
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(), style, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        content.add_css_class("pomodoro-content")
        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroll.set_child(content)
        self.window.set_child(scroll)

        timer_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        timer_card.add_css_class("pomodoro-timer-card")
        content.append(timer_card)
        eyebrow = Gtk.Label(label="POMODORO TAYMER", xalign=0)
        eyebrow.add_css_class("pomodoro-eyebrow")
        timer_card.append(eyebrow)
        self.status = Gtk.Label(label="Boshlashga tayyor", xalign=0)
        self.status.add_css_class("pomodoro-status")
        timer_card.append(self.status)
        self.time_label = Gtk.Label(label="25:00", xalign=0)
        self.time_label.add_css_class("pomodoro-time")
        timer_card.append(self.time_label)
        self.progress = Gtk.ProgressBar()
        self.progress.add_css_class("pomodoro-progress")
        timer_card.append(self.progress)
        self.cycle_label = Gtk.Label(label="Bajarilgan darslar: 0", xalign=0)
        self.cycle_label.add_css_class("pomodoro-cycle")
        timer_card.append(self.cycle_label)

        section_title = Gtk.Label(label="Vaqtlar · daqiqa", xalign=0)
        section_title.add_css_class("pomodoro-section-title")
        content.append(section_title)
        durations = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        content.append(durations)
        self.focus_spin = self._add_duration_card(durations, "Dars", 1, 180)
        self.break_spin = self._add_duration_card(durations, "Tanaffus", 1, 60)

        self.main_button = Gtk.Button(label="Boshlash")
        self.main_button.add_css_class("suggested-action")
        self.main_button.add_css_class("pomodoro-main-button")
        self.main_button.connect("clicked", self._primary_action)
        content.append(self.main_button)

        secondary = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        content.append(secondary)
        self.skip_button = Gtk.Button(label="Tanaffusni o‘tkazish")
        self.skip_button.add_css_class("pomodoro-secondary-button")
        self.skip_button.set_hexpand(True)
        self.skip_button.connect("clicked", self._skip_break)
        secondary.append(self.skip_button)
        self.stop_button = Gtk.Button(label="To‘xtatish")
        self.stop_button.add_css_class("pomodoro-secondary-button")
        self.stop_button.add_css_class("destructive-action")
        self.stop_button.set_hexpand(True)
        self.stop_button.connect("clicked", self._stop)
        secondary.append(self.stop_button)

        advanced = Gtk.Expander(label="Qo‘shimcha sozlamalar")
        advanced.add_css_class("pomodoro-advanced")
        advanced_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        advanced_box.add_css_class("pomodoro-advanced-box")
        advanced.set_child(advanced_box)
        content.append(advanced)
        self.long_break_spin = self._add_duration_row(advanced_box, "Uzun tanaffus (daqiqa)", 5, 60)
        self.cycles_spin = self._add_duration_row(advanced_box, "Har nechta darsdan so‘ng\n0 — uzun tanaffus o‘chiq", 0, 12)
        self.focus_spin.connect("value-changed", self._duration_changed, "focus-minutes")
        self.break_spin.connect("value-changed", self._duration_changed, "break-minutes")
        self.long_break_spin.connect("value-changed", self._duration_changed, "long-break-minutes")
        self.cycles_spin.connect("value-changed", self._duration_changed, "cycles-before-long")
        sound_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        sound_text = Gtk.Label(label="Tanaffus ovozi", xalign=0)
        sound_text.set_hexpand(True)
        sound_row.append(sound_text)
        self.sound_switch = Gtk.Switch()
        self.sound_switch.set_valign(Gtk.Align.CENTER)
        self.sound_switch.connect("notify::active", self._sound_changed)
        sound_row.append(self.sound_switch)
        advanced_box.append(sound_row)
        lock_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        lock_text = Gtk.Label(label="Ekran qulflanganda pauza", xalign=0)
        lock_text.set_hexpand(True)
        lock_row.append(lock_text)
        self.lock_switch = Gtk.Switch()
        self.lock_switch.set_valign(Gtk.Align.CENTER)
        self.lock_switch.connect("notify::active", self._lock_changed)
        lock_row.append(self.lock_switch)
        advanced_box.append(lock_row)
        self._sync_spins()

        hint = Gtk.Label(label="Oynani yopsangiz ham taymer yuqori panelda davom etadi.", xalign=0)
        hint.add_css_class("pomodoro-hint")
        hint.set_wrap(True)
        content.append(hint)

    @staticmethod
    def _add_duration_card(parent, text, minimum, maximum):
        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        card.add_css_class("pomodoro-duration-card")
        card.set_hexpand(True)
        label = Gtk.Label(label=text, xalign=0)
        label.add_css_class("pomodoro-duration-title")
        card.append(label)
        spin = Gtk.SpinButton.new_with_range(minimum, maximum, 1)
        spin.set_numeric(True)
        PomodoroApp._style_step_buttons(spin)
        spin.set_width_chars(3)
        spin.set_hexpand(True)
        spin.update_property([Gtk.AccessibleProperty.LABEL], [f"{text} daqiqalari"])
        card.append(spin)
        parent.append(card)
        return spin

    def _primary_action(self, _button):
        if read_state(self.settings)["phase"] == "idle":
            self._start(None)
        else:
            self._toggle_pause(None)

    @staticmethod
    def _style_step_buttons(spin):
        """Keep native spin gestures and keyboard behavior with theme-independent signs."""
        child = spin.get_first_child()
        while child is not None:
            if isinstance(child, Gtk.Button):
                down = child.has_css_class("down")
                if down or child.has_css_class("up"):
                    name = "Kamaytirish" if down else "Ko‘paytirish"
                    child.set_child(Gtk.Label(label="−" if down else "+"))
                    child.update_property([Gtk.AccessibleProperty.LABEL], [name])
                    child.set_tooltip_text(name)
            child = child.get_next_sibling()

    @staticmethod
    def _add_duration_row(parent, text, minimum, maximum):
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        label = Gtk.Label(label=text, xalign=0)
        label.set_hexpand(True)
        label.set_wrap(True)
        row.append(label)
        spin = Gtk.SpinButton.new_with_range(minimum, maximum, 1)
        spin.set_numeric(True)
        PomodoroApp._style_step_buttons(spin)
        spin.set_width_chars(2)
        spin.set_valign(Gtk.Align.CENTER)
        spin.update_property([Gtk.AccessibleProperty.LABEL], [text.split("\n")[0]])
        row.append(spin)
        parent.append(row)
        return spin

    def _settings_changed(self):
        self._sync_spins()
        if self._paused_by_lock and not self.settings.get_boolean("pause-on-lock"):
            self._paused_by_lock = False
            if read_state(self.settings)["paused"]:
                self._toggle_pause(None)
        self._render()

    def _sync_spins(self):
        self._updating_spins = True
        self.focus_spin.set_value(self.settings.get_int("focus-minutes"))
        self.break_spin.set_value(self.settings.get_int("break-minutes"))
        self.long_break_spin.set_value(self.settings.get_int("long-break-minutes"))
        self.cycles_spin.set_value(self.settings.get_int("cycles-before-long"))
        self.sound_switch.set_active(self.settings.get_boolean("sound-enabled"))
        self.lock_switch.set_active(self.settings.get_boolean("pause-on-lock"))
        self._updating_spins = False

    def _sound_changed(self, switch, _property):
        if not self._updating_spins:
            self.settings.set_boolean("sound-enabled", switch.get_active())

    def _lock_changed(self, switch, _property):
        if not self._updating_spins:
            self.settings.set_boolean("pause-on-lock", switch.get_active())

    def _duration_changed(self, spin, key):
        if not self._updating_spins:
            self.settings.set_int(key, spin.get_value_as_int())

    def _write_state(self, state):
        self.settings.set_string(
            "session-state", json.dumps(state, ensure_ascii=False, separators=(",", ":"))
        )
        self._render()

    def _start(self, _button):
        self._paused_by_lock = False
        now = int(time.time() * 1000)
        state = empty_state()
        state["phase"] = "focus"
        state["deadlineMs"] = now + self.settings.get_int("focus-minutes") * 60_000
        self._write_state(state)
        if self.window is not None:
            self.window.set_visible(False)

    def _toggle_pause(self, _button):
        state = read_state(self.settings)
        if state["phase"] == "idle":
            return
        now = int(time.time() * 1000)
        if state["paused"]:
            state["deadlineMs"] = now + state["remainingMs"]
            state["remainingMs"] = 0
            state["paused"] = False
        else:
            advance_state(state, self.settings.get_int("focus-minutes") * 60_000,
                          self.settings.get_int("break-minutes") * 60_000, now,
                          self.settings.get_int("long-break-minutes") * 60_000,
                          self.settings.get_int("cycles-before-long"))
            state["remainingMs"] = max(0, state["deadlineMs"] - now)
            state["paused"] = True
        self._write_state(state)

    def _skip_break(self, _button):
        state = read_state(self.settings)
        if state["phase"] != "break":
            return
        state["phase"] = "focus"
        state["deadlineMs"] = int(time.time() * 1000) + self.settings.get_int("focus-minutes") * 60_000
        state["remainingMs"] = 0
        state["paused"] = False
        state["breakKind"] = "short"
        self._write_state(state)

    def _extend_break(self, _button):
        state = read_state(self.settings)
        if state["phase"] != "break":
            return
        if state["paused"]:
            state["remainingMs"] += 60_000
        else:
            state["deadlineMs"] += 60_000
        self._write_state(state)

    def _break_key_pressed(self, _controller, keyval, _keycode, _state):
        if keyval == Gdk.KEY_Escape:
            self._skip_break(None)
            return True
        return False

    def _stop(self, _button):
        self._paused_by_lock = False
        self._write_state(empty_state())

    def _tick(self):
        if self.shell_extension_active:
            self._render()
            return GLib.SOURCE_CONTINUE
        state = read_state(self.settings)
        previous_phase = state["phase"]
        now = int(time.time() * 1000)
        self._warn_before_break(state, now)
        if advance_state(state, self.settings.get_int("focus-minutes") * 60_000,
                         self.settings.get_int("break-minutes") * 60_000, now,
                         self.settings.get_int("long-break-minutes") * 60_000,
                         self.settings.get_int("cycles-before-long")):
            if self._shell_extension_active():
                self._sync_owner()
                return GLib.SOURCE_CONTINUE
            self._write_state(state)
            if state["phase"] != previous_phase and self.settings.get_boolean("sound-enabled"):
                play_transition_sound(state["phase"])
        else:
            self._render()
        return GLib.SOURCE_CONTINUE

    def _warn_before_break(self, state, now):
        if (state["phase"] == "focus" and not state["paused"]
                and 0 < state["deadlineMs"] - now <= 30_000
                and state["deadlineMs"] != self._warned_deadline):
            self._warned_deadline = state["deadlineMs"]
            notice = Gio.Notification.new("Tanaffusga 30 soniya qoldi")
            notice.set_body("Ishingizni saqlang. Zarur bo‘lsa, taymerni pauzaga qo‘ying.")
            self.send_notification("pomodoro-break-soon", notice)

    def _render(self):
        if self.window is None:
            return
        state = read_state(self.settings)
        phase = state["phase"]
        if phase == "idle":
            seconds = self.settings.get_int("focus-minutes") * 60
        else:
            milliseconds = state["remainingMs"] if state["paused"] else \
                state["deadlineMs"] - int(time.time() * 1000)
            seconds = max(0, math.ceil(milliseconds / 1000))
        self.time_label.set_text(f"{seconds // 60:02d}:{seconds % 60:02d}")
        if phase == "break":
            duration = self.settings.get_int(
                "long-break-minutes" if state.get("breakKind") == "long" else "break-minutes"
            ) * 60
        else:
            duration = self.settings.get_int("focus-minutes") * 60
        self.progress.set_fraction(min(1.0, seconds / max(1, duration)))
        cycles = self.settings.get_int("cycles-before-long")
        self.cycle_label.set_text(
            f"Davr: {state['completedFocus'] % cycles}/{cycles}" if cycles > 0
            else f"Bajarilgan darslar: {state['completedFocus']}"
        )
        if self.indicator is not None:
            self.indicator.set_phase(phase, state["paused"])
            panel_text = f"{seconds // 60:02d}:{seconds % 60:02d}"
            if phase == "break":
                panel_text = f"Dam {panel_text}"
            elif state["paused"]:
                panel_text = f"P {panel_text}"
            self.indicator.set_label(panel_text)
        name = {"idle": "Boshlashga tayyor", "focus": "O‘qish vaqti", "break": "Tanaffus"}[phase]
        if phase == "break" and state.get("breakKind") == "long":
            name = "Uzun tanaffus"
        self.status.set_text(name + (" — pauza" if state["paused"] else ""))
        self.main_button.set_label(
            "Boshlash" if phase == "idle" else
            "Davom ettirish" if state["paused"] else "Pauza"
        )
        if phase == "idle" or state["paused"]:
            self.main_button.add_css_class("suggested-action")
        else:
            self.main_button.remove_css_class("suggested-action")
        self.skip_button.set_visible(phase == "break")
        self.stop_button.set_visible(phase != "idle")
        self.stop_button.get_parent().set_visible(phase != "idle")
        if not self.shell_extension_active:
            self._update_break_screen(phase, seconds, state["paused"])

    def _update_break_screen(self, phase, seconds, paused):
        if phase != "break":
            self._close_break_windows()
            return

        monitors = Gdk.Display.get_default().get_monitors()
        if len(self.break_windows) != monitors.get_n_items():
            self._close_break_windows()
            for index in range(monitors.get_n_items()):
                self._create_break_window(monitors.get_item(index))

        for time_label, pause_button, detail in self.break_labels:
            time_label.set_text(f"{seconds // 60:02d}:{seconds % 60:02d}")
            pause_button.set_label("Davom ettirish" if paused else "Pauza")
            detail.set_text("Taymer pauzada" if paused else "Ko‘zingizni dam oldiring")

    def _close_break_windows(self):
        for window in self.break_windows:
            window.close()
        self.break_windows = []
        self.break_labels = []
        self.break_window = None

    def _create_break_window(self, monitor):
        window = Gtk.Window(application=self, title="Tanaffus")
        window.set_decorated(False)
        window.set_default_size(900, 600)
        keys = Gtk.EventControllerKey()
        keys.connect("key-pressed", self._break_key_pressed)
        window.add_controller(keys)
        overlay = Gtk.Overlay()
        picture = Gtk.Picture.new_for_filename(str(BACKGROUND))
        picture.set_content_fit(Gtk.ContentFit.COVER)
        overlay.set_child(picture)
        dim = Gtk.Box()
        dim.add_css_class("pomodoro-break-dim")
        dim.set_hexpand(True)
        dim.set_vexpand(True)
        overlay.add_overlay(dim)

        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        card.add_css_class("pomodoro-break-card")
        card.set_halign(Gtk.Align.CENTER)
        card.set_valign(Gtk.Align.CENTER)
        title = Gtk.Label(label="TANAFFUS")
        title.add_css_class("pomodoro-break-title")
        card.append(title)
        time_label = Gtk.Label(label="05:00")
        time_label.add_css_class("pomodoro-break-time")
        card.append(time_label)
        detail = Gtk.Label(label="Ko‘zingizni dam oldiring")
        detail.add_css_class("pomodoro-break-detail")
        card.append(detail)
        buttons = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        buttons.set_halign(Gtk.Align.CENTER)
        pause_button = Gtk.Button(label="Pauza")
        pause_button.connect("clicked", self._toggle_pause)
        buttons.append(pause_button)
        extend_button = Gtk.Button(label="+1 daqiqa")
        extend_button.connect("clicked", self._extend_break)
        buttons.append(extend_button)
        skip_button = Gtk.Button(label="Darsga qaytish")
        skip_button.add_css_class("suggested-action")
        skip_button.connect("clicked", self._skip_break)
        buttons.append(skip_button)
        card.append(buttons)
        overlay.add_overlay(card)
        window.set_child(overlay)
        window.present()
        window.fullscreen_on_monitor(monitor)
        self.break_windows.append(window)
        self.break_labels.append((time_label, pause_button, detail))
        if self.break_window is None:
            self.break_window = window
            self.break_time_label = time_label
            self.break_pause_button = pause_button
            self.break_detail = detail


if __name__ == "__main__":
    raise SystemExit(PomodoroApp().run())
