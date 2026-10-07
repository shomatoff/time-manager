import os
import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

os.environ["GSETTINGS_BACKEND"] = "memory"
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from control import GLib, PomodoroApp, advance_state, empty_state, \
    play_transition_sound, read_state  # noqa: E402


class TimerStateTests(unittest.TestCase):
    def setUp(self):
        # Unit tests must not depend on the user's live GNOME extension state.
        owner = patch.object(PomodoroApp, "_shell_extension_active", return_value=False)
        owner.start()
        self.addCleanup(owner.stop)

    def test_focus_break_cycle(self):
        state = empty_state()
        state.update(phase="focus", deadlineMs=25 * 60_000)
        self.assertTrue(advance_state(state, 25 * 60_000, 5 * 60_000, 25 * 60_000))
        self.assertEqual(state["phase"], "break")
        self.assertEqual(state["deadlineMs"], 30 * 60_000)
        self.assertTrue(advance_state(state, 25 * 60_000, 5 * 60_000, 30 * 60_000))
        self.assertEqual(state["phase"], "focus")

    def test_window_commands_write_shared_state(self):
        app = PomodoroApp()
        with patch("control.time.time", return_value=1000):
            app._start(None)
            state = read_state(app.settings)
            self.assertEqual(state["phase"], "focus")
            self.assertEqual(state["deadlineMs"], 1000 * 1000 + 25 * 60_000)
            app._toggle_pause(None)
            self.assertTrue(read_state(app.settings)["paused"])
            app._toggle_pause(None)
            self.assertFalse(read_state(app.settings)["paused"])
        with patch("control.time.time", return_value=2500), \
             patch("control.play_transition_sound") as sound:
            app._tick()
            self.assertEqual(read_state(app.settings)["phase"], "break")
            sound.assert_called_once_with("break")
            app._tick()
            sound.assert_called_once()
            app._skip_break(None)
            self.assertEqual(read_state(app.settings)["phase"], "focus")
            app._stop(None)
            self.assertEqual(read_state(app.settings)["phase"], "idle")

    def test_long_break_and_extension(self):
        state = empty_state()
        state.update(phase="focus", deadlineMs=60_000, completedFocus=3)
        advance_state(state, 60_000, 60_000, 60_000, 15 * 60_000, 4)
        self.assertEqual(state["phase"], "break")
        self.assertEqual(state["breakKind"], "long")
        self.assertEqual(state["deadlineMs"], 16 * 60_000)

        app = PomodoroApp()
        app._write_state(state)
        with patch("control.time.time", return_value=60):
            app._extend_break(None)
        self.assertEqual(read_state(app.settings)["deadlineMs"], 17 * 60_000)

    def test_native_extension_takes_timer_ownership(self):
        app = PomodoroApp()
        app.window = object()
        app.indicator = Mock()
        fallback = Mock()
        app.break_windows = [fallback]
        app.break_window = fallback
        with patch.object(app, "_shell_extension_active", return_value=True), \
             patch.object(app, "_render"):
            app._sync_owner()
        self.assertTrue(app.shell_extension_active)
        self.assertIsNone(app.indicator)
        self.assertIsNone(app.break_window)
        fallback.close.assert_called_once()

        state = empty_state()
        state.update(phase="focus", deadlineMs=1)
        with patch.object(app, "_render"):
            app._write_state(state)
            app._tick()
        self.assertEqual(read_state(app.settings)["phase"], "focus")

    def test_optional_lock_pause_resumes_on_unlock(self):
        app = PomodoroApp()
        app.settings.set_boolean("pause-on-lock", True)
        state = empty_state()
        state.update(phase="focus", deadlineMs=1_060_000)
        app._write_state(state)
        with patch("control.time.time", return_value=1000):
            app._on_screen_lock(None, None, None, None, None,
                                GLib.Variant("(b)", (True,)))
        self.assertTrue(read_state(app.settings)["paused"])
        with patch("control.time.time", return_value=1010):
            app._on_screen_lock(None, None, None, None, None,
                                GLib.Variant("(b)", (False,)))
        self.assertFalse(read_state(app.settings)["paused"])
        self.assertEqual(read_state(app.settings)["deadlineMs"], 1_070_000)

    def test_break_warning_appears_once_per_deadline(self):
        app = PomodoroApp()
        app.send_notification = Mock()
        state = empty_state()
        state.update(phase="focus", deadlineMs=30_000)
        app._warn_before_break(state, 1_000)
        app._warn_before_break(state, 2_000)
        app.send_notification.assert_called_once()

    def test_sound_uses_packaged_file_if_theme_event_fails(self):
        class ImmediateThread:
            def __init__(self, target, daemon):
                self.target = target

            def start(self):
                self.target()

        failed = type("Result", (), {"returncode": 1})()
        succeeded = type("Result", (), {"returncode": 0})()
        with patch("control.threading.Thread", ImmediateThread), \
             patch("control.subprocess.run", side_effect=[failed, succeeded]) as run:
            play_transition_sound("break")
        self.assertEqual(run.call_args_list[0].args[0][:2],
                         ["canberra-gtk-play", "-i"])
        self.assertEqual(run.call_args_list[1].args[0][0], "pw-play")


if __name__ == "__main__":
    unittest.main()
