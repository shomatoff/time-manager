"""Qt smoke tests run without a display on Linux and Windows."""
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from unittest.mock import patch
from desktop import Desktop, STYLE


class DesktopTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.app.setQuitOnLastWindowClosed(False)
        cls.app.setStyleSheet(STYLE)

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.settings = QSettings(str(Path(self.directory.name) / 'settings.ini'), QSettings.Format.IniFormat)
        self.settings.setValue('language', 'uz')
        self.window = Desktop(self.settings, testing=True)

    def tearDown(self):
        self.window.close()
        self.window.deleteLater()
        self.app.processEvents()
        self.directory.cleanup()

    def test_stepper_buttons_and_limits(self):
        control = self.window.steppers['focus']
        control.plus.click()
        self.assertEqual(self.window.options['focus'], 26)
        control.minus.click()
        self.assertEqual(self.window.options['focus'], 25)
        control.spin.setValue(1)
        self.assertFalse(control.minus.isEnabled())
        control.spin.setValue(180)
        self.assertFalse(control.plus.isEnabled())

    def test_start_pause_restore_stop(self):
        self.window.primary()
        self.assertEqual(self.window.state['phase'], 'focus')
        self.window.primary()
        remaining = self.window.state['remainingMs']
        self.assertTrue(self.window.state['paused'])
        restored = Desktop(self.settings, testing=True)
        self.assertEqual(restored.state['remainingMs'], remaining)
        restored.close()
        self.window.primary()
        self.assertFalse(self.window.state['paused'])
        self.window.stop()
        self.assertEqual(self.window.main_button.text(), 'Boshlash')

    def test_break_extend_skip_and_long_break(self):
        self.window.options['cycles'] = 4
        self.window.state.update(phase='focus', deadlineMs=int(time.time()*1000)-10, completedFocus=3)
        self.window.tick()
        self.assertEqual(self.window.state['phase'], 'break')
        self.assertEqual(self.window.state['breakKind'], 'long')
        deadline = self.window.state['deadlineMs']
        self.window.extend()
        self.assertEqual(self.window.state['deadlineMs'], deadline+60000)
        self.window.skip()
        self.assertEqual(self.window.state['phase'], 'focus')
        self.assertEqual(self.window.state['completedFocus'], 4)

    def test_corrupt_session_recovers(self):
        self.settings.setValue('session', '{broken')
        other = Desktop(self.settings, testing=True)
        self.assertEqual(other.state['phase'], 'idle')
        other.close()

    def test_language_switch_preserves_session_and_persists(self):
        self.window.primary()
        self.window.primary()
        before = dict(self.window.state)
        for code, expected in [('en', 'Resume'), ('ru', 'Продолжить'), ('uz', 'Davom ettirish')]:
            index = self.window.language_combo.findData(code)
            self.window.language_combo.setCurrentIndex(index)
            self.assertEqual(self.window.main_button.text(), expected)
            self.assertEqual(self.window.state, before)
            self.assertEqual(self.settings.value('language'), code)
        self.window.language_combo.setCurrentIndex(self.window.language_combo.findData('ru'))
        restored = Desktop(self.settings, testing=True)
        self.assertEqual(restored.language, 'ru')
        self.assertEqual(restored.main_button.text(), 'Продолжить')
        restored.close()

    def test_fullscreen_break_escape_closes_overlay(self):
        self.window.state.update(phase='break', deadlineMs=int(time.time()*1000)+60000)
        self.window.testing = False
        self.window.render()
        self.app.processEvents()
        self.assertEqual(len(self.window.breaks), len(self.app.screens()))
        overlay = self.window.breaks[0]
        self.assertTrue(overlay.isFullScreen())
        with patch.object(self.window, 'play'):
            QTest.keyClick(overlay, Qt.Key.Key_Escape)
            self.app.processEvents()
        self.assertEqual(self.window.state['phase'], 'focus')
        self.assertEqual(self.window.breaks, [])
        self.window.testing = True


if __name__ == '__main__':
    unittest.main()
