#!/usr/bin/env python3
"""EN: Focus/rest timer for Windows and Linux.
UZ: Windows va Linux uchun dars va tanaffus vaqtini boshqaruvchi taymer.
"""
import json
import math
import sys
import time
from pathlib import Path

from PySide6.QtCore import QLockFile, QSettings, QStandardPaths, Qt, QTimer, QUrl, QLocale
from PySide6.QtGui import QColor, QIcon, QKeySequence, QPainter, QPixmap, QShortcut
from PySide6.QtMultimedia import QSoundEffect
from PySide6.QtNetwork import QLocalServer, QLocalSocket
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QFrame, QGridLayout, QHBoxLayout, QLabel,
    QMainWindow, QMenu, QMessageBox, QProgressBar, QPushButton, QScrollArea,
    QSpinBox, QSystemTrayIcon, QVBoxLayout, QWidget,
)
from timer_core import advance_state, empty_state
from translations import LANGUAGES, translate

ROOT = Path(__file__).resolve().parent
DEFAULTS = {'focus': 25, 'break': 5, 'long': 15, 'cycles': 0, 'sound': True}
STYLE = '''
QWidget { font-family: "Segoe UI", "DejaVu Sans"; font-size: 14px; color: #f1f6fb; }
QMainWindow, QScrollArea, QWidget#content { background: #101a29; }
QScrollArea { border: none; }
QFrame#timer { background: #1b2e43; border: 1px solid #334c65; border-radius: 20px; }
QFrame#duration { background: #1b2b3c; border: 1px solid #30465b; border-radius: 15px; }
QLabel { background: transparent; }
QLabel#eyebrow { color: #9cb6ca; font-size: 12px; font-weight: 700; }
QLabel#phase { color: #a4ead9; font-size: 19px; font-weight: 700; }
QLabel#time { color: white; font-size: 70px; font-weight: 700; }
QLabel#muted { color: #bbcedd; font-size: 13px; }
QPushButton { background: #22364a; border: 1px solid #456078; border-radius: 10px; padding: 10px; }
QPushButton:hover { background: #2d465e; }
QPushButton:pressed { background: #182b3d; }
QPushButton:focus { border: 2px solid #8bdcc8; }
QPushButton#primary { background: #177460; border-color: #3ca993; font-weight: 700; min-height: 26px; }
QPushButton#primary:hover { background: #1b806b; }
QPushButton#stop { color: #ffbdc2; border-color: #825361; }
QPushButton#step { background: #e9f2f4; color: black; font-size: 20px; font-weight: 800; border: 1px solid #859aa9; padding: 4px; min-width: 28px; }
QPushButton#step:hover { background: #cedfe6; }
QPushButton#step:disabled { color: #637886; background: #dde7ec; }
QSpinBox { background: #e9f2f4; color: #10283d; border: 1px solid #859aa9; border-radius: 8px; padding: 7px; font-size: 17px; font-weight: 600; }
QSpinBox:focus { border: 2px solid #177460; }
QProgressBar { border: none; border-radius: 4px; background: #344d63; max-height: 7px; }
QProgressBar::chunk { background: #57d5b3; border-radius: 4px; }
QComboBox { background: #22364a; color: #f1f6fb; border: 1px solid #456078; border-radius: 7px; padding: 6px; min-width: 100px; }
QComboBox QAbstractItemView { background: #22364a; color: #f1f6fb; selection-background-color: #177460; }
QCheckBox { spacing: 10px; padding: 6px 0; }
QCheckBox::indicator { width: 20px; height: 20px; border: 1px solid #8da8bf; border-radius: 5px; background: #22364a; }
QCheckBox::indicator:checked { background: #57d5b3; border: 4px solid #177460; }
'''


def label(text, name=None):
    result = QLabel(text)
    if name:
        result.setObjectName(name)
    return result


class Stepper(QWidget):
    def __init__(self, minimum, maximum, value, title, changed, translator=lambda text: text):
        super().__init__()
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(0)
        self.spin = QSpinBox()
        self.spin.setRange(minimum, maximum)
        self.spin.setValue(value)
        self.spin.setButtonSymbols(QSpinBox.ButtonSymbols.NoButtons)
        self.spin.setAccessibleName(translator(title))
        row.addWidget(self.spin, 1)
        self.minus, self.plus = QPushButton('−'), QPushButton('+')
        for button, name in ((self.minus, 'Kamaytirish'), (self.plus, 'Ko‘paytirish')):
            button.setObjectName('step')
            button.setAccessibleName(f'{translator(title)}: {translator(name)}')
            button.setToolTip(translator(name))
            button.setAutoRepeat(True)
            row.addWidget(button)
        self.minus.clicked.connect(self.spin.stepDown)
        self.plus.clicked.connect(self.spin.stepUp)
        self.spin.valueChanged.connect(changed)
        self.spin.valueChanged.connect(self.update_limits)
        self.update_limits()

    def update_limits(self):
        self.minus.setEnabled(self.spin.value() > self.spin.minimum())
        self.plus.setEnabled(self.spin.value() < self.spin.maximum())


class BreakWindow(QWidget):
    def __init__(self, owner, screen):
        super().__init__()
        self.owner = owner
        self.setWindowTitle(owner.tr_text('Tanaffus'))
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.image = QPixmap(str(ROOT / 'black-hole.jpg'))
        layout = QVBoxLayout(self)
        layout.addStretch()
        card = QFrame()
        card.setStyleSheet('QFrame { background: rgba(8,14,24,220); border-radius: 24px; }')
        box = QVBoxLayout(card)
        box.setContentsMargins(38, 30, 38, 30)
        box.setSpacing(16)
        title = label('Tanaffus', 'phase')
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        box.addWidget(title)
        self.clock = label('05:00', 'time')
        self.clock.setAlignment(Qt.AlignmentFlag.AlignCenter)
        box.addWidget(self.clock)
        self.detail = label('Ko‘zingizni dam oldiring', 'muted')
        self.detail.setAlignment(Qt.AlignmentFlag.AlignCenter)
        box.addWidget(self.detail)
        row = QHBoxLayout()
        for text, callback in [('Darsga qaytish', owner.skip), ('+1 daqiqa', owner.extend)]:
            button = QPushButton(text)
            button.clicked.connect(callback)
            row.addWidget(button)
        box.addLayout(row)
        self.pause = QPushButton('Pauza')
        self.pause.clicked.connect(owner.primary)
        box.addWidget(self.pause)
        box.addWidget(label('Esc — darsga qaytish', 'muted'), alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(card, alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addStretch()
        self.escape = QShortcut(QKeySequence('Escape'), self)
        self.escape.activated.connect(owner.skip)
        self.setScreen(screen)
        self.setGeometry(screen.geometry())
        owner.translate_widgets(self)
        self.showFullScreen()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor('#080e18'))
        if not self.image.isNull():
            scaled = self.image.scaled(self.size(), Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                                       Qt.TransformationMode.SmoothTransformation)
            painter.drawPixmap((self.width()-scaled.width())//2, (self.height()-scaled.height())//2, scaled)
        painter.fillRect(self.rect(), QColor(0, 0, 0, 80))

    def closeEvent(self, event):
        if self.owner.state['phase'] == 'break' and not self.owner.closing_breaks:
            event.ignore()
            self.owner.skip()
        else:
            event.accept()


class Desktop(QMainWindow):
    def __init__(self, settings=None, testing=False):
        super().__init__()
        self.testing = testing
        self.settings = settings or QSettings('PomodoroDesktop', 'Pomodoro')
        language = self.settings.value('language', QLocale.system().name().split('_')[0])
        self.language = language if language in LANGUAGES else 'en'
        self.options = {key: self.settings.value(key, default, type=type(default))
                        for key, default in DEFAULTS.items()}
        for key, lo, hi in [('focus', 1, 180), ('break', 1, 60), ('long', 5, 60), ('cycles', 0, 12)]:
            self.options[key] = min(hi, max(lo, self.options[key]))
        try:
            self.state = json.loads(self.settings.value('session', '{}'))
            assert self.state['phase'] in ('idle', 'focus', 'break')
            assert isinstance(self.state['paused'], bool)
            for key in ('deadlineMs', 'remainingMs', 'completedFocus'):
                assert isinstance(self.state[key], (int, float)) and math.isfinite(self.state[key]) and self.state[key] >= 0
        except (ValueError, TypeError, KeyError, AssertionError):
            self.state = empty_state()
        self.breaks = []
        self.closing_breaks = False
        self.warned = 0
        self.quitting = False
        self.setWindowTitle('Pomodoro')
        self.setWindowIcon(QIcon(str(ROOT / 'pomodoro.svg')))
        self.resize(470, 650)
        self.setMinimumWidth(430)
        self.build_ui()
        self.tray = QSystemTrayIcon(self.windowIcon(), self)
        menu = QMenu(self)
        self.tray_menu = menu
        self.tray_status = menu.addAction('Pomodoro')
        self.tray_status.setEnabled(False)
        menu.addAction('Oynani ochish', self.present)
        self.tray_primary = menu.addAction('Boshlash', self.primary)
        self.tray_skip = menu.addAction('Tanaffusni o‘tkazish', self.skip)
        menu.addAction('To‘xtatish', self.stop)
        menu.addSeparator()
        menu.addAction('Dasturdan chiqish', self.quit)
        for action in menu.actions():
            action.setProperty('sourceText', action.text())
            action.setText(self.tr_text(action.text()))
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(self.tray_activated)
        if not testing:
            self.tray.show()
        self.sounds = {}
        for phase, filename in [('break', 'break-start.wav'), ('focus', 'break-end.wav')]:
            sound = QSoundEffect(self)
            sound.setSource(QUrl.fromLocalFile(str(ROOT / filename)))
            sound.setVolume(0.55)
            self.sounds[phase] = sound
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.tick)
        if not testing:
            self.timer.start(250)
            QApplication.instance().screenAdded.connect(self.rebuild_breaks)
            QApplication.instance().screenRemoved.connect(self.rebuild_breaks)
        self.tick()

    def build_ui(self):
        content = QWidget()
        content.setObjectName('content')
        outer = QVBoxLayout(content)
        outer.setContentsMargins(22, 22, 22, 22)
        outer.setSpacing(16)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(content)
        self.setCentralWidget(scroll)
        language_row = QHBoxLayout()
        language_row.addWidget(label('Language / Язык / Til', 'muted'))
        language_row.addStretch()
        self.language_combo = QComboBox()
        self.language_combo.setAccessibleName('Language / Язык / Til')
        for code, name in LANGUAGES.items():
            self.language_combo.addItem(name, code)
        self.language_combo.setCurrentIndex(list(LANGUAGES).index(self.language))
        self.language_combo.currentIndexChanged.connect(self.change_language)
        language_row.addWidget(self.language_combo)
        outer.addLayout(language_row)
        card = QFrame()
        card.setObjectName('timer')
        box = QVBoxLayout(card)
        box.setContentsMargins(20, 20, 20, 20)
        box.addWidget(label('POMODORO TAYMER', 'eyebrow'))
        self.phase = label('Boshlashga tayyor', 'phase')
        self.clock = label('25:00', 'time')
        self.progress = QProgressBar()
        self.progress.setRange(0, 1000)
        self.progress.setTextVisible(False)
        self.cycle = label('', 'muted')
        for widget in (self.phase, self.clock, self.progress, self.cycle):
            box.addWidget(widget)
        outer.addWidget(card)
        outer.addWidget(label('Vaqtlar · daqiqa'))
        durations = QHBoxLayout()
        self.steppers = {}
        for key, title, maximum in [('focus', 'Dars', 180), ('break', 'Tanaffus', 60)]:
            duration = QFrame()
            duration.setObjectName('duration')
            column = QVBoxLayout(duration)
            column.addWidget(label(title, 'muted'))
            stepper = Stepper(1, maximum, self.options[key], title,
                              lambda value, k=key: self.configure(k, value), self.tr_text)
            self.steppers[key] = stepper
            column.addWidget(stepper)
            durations.addWidget(duration)
        outer.addLayout(durations)
        self.main_button = QPushButton('Boshlash')
        self.main_button.setObjectName('primary')
        self.main_button.clicked.connect(self.primary)
        outer.addWidget(self.main_button)
        row = QHBoxLayout()
        self.skip_button = QPushButton('Tanaffusni o‘tkazish')
        self.skip_button.clicked.connect(self.skip)
        self.stop_button = QPushButton('To‘xtatish')
        self.stop_button.setObjectName('stop')
        self.stop_button.clicked.connect(self.stop)
        row.addWidget(self.skip_button)
        row.addWidget(self.stop_button)
        outer.addLayout(row)
        more = QPushButton('Qo‘shimcha sozlamalar ▸')
        more.setCheckable(True)
        outer.addWidget(more)
        advanced = QWidget()
        grid = QGridLayout(advanced)
        grid.setContentsMargins(0, 0, 0, 0)
        for row, (key, title, lo, hi) in enumerate([
                ('long', 'Uzun tanaffus · daqiqa', 5, 60),
                ('cycles', 'Har nechta darsdan so‘ng\n0 — uzun tanaffus o‘chiq', 0, 12)]):
            text = label(title, 'muted')
            text.setWordWrap(True)
            grid.addWidget(text, row, 0)
            stepper = Stepper(lo, hi, self.options[key], title,
                              lambda value, k=key: self.configure(k, value), self.tr_text)
            self.steppers[key] = stepper
            grid.addWidget(stepper, row, 1)
        sound = QCheckBox('Tanaffus ovozi')
        sound.setChecked(self.options['sound'])
        sound.toggled.connect(lambda value: self.configure('sound', value))
        grid.addWidget(sound, 2, 0, 1, 2)
        advanced.hide()
        more.toggled.connect(advanced.setVisible)
        more.toggled.connect(lambda checked: more.setText(self.tr_text('Qo‘shimcha sozlamalar') + ' ' + ('▾' if checked else '▸')))
        outer.addWidget(advanced)
        hint = label('Oynani yopsangiz ham taymer tizim panelida davom etadi.\nVaqt o‘zgarishlari keyingi bosqichga qo‘llanadi.', 'muted')
        hint.setWordWrap(True)
        outer.addWidget(hint)
        outer.addStretch()
        self.translate_widgets(content)

    def tr_text(self, text, **values):
        return translate(self.language, text, **values)

    def translate_widgets(self, root):
        for widget in root.findChildren(QWidget):
            if isinstance(widget, (QLabel, QPushButton, QCheckBox)):
                widget.setText(self.tr_text(widget.text()))

    def change_language(self, index):
        self.language = self.language_combo.itemData(index)
        self.settings.setValue("language", self.language)
        self.close_breaks()
        self.build_ui()
        for action in self.tray_menu.actions():
            action.setText(self.tr_text(action.property("sourceText") or ""))
        self.render()

    def configure(self, key, value):
        self.options[key] = value
        self.settings.setValue(key, value)
        self.render()

    def save(self):
        self.settings.setValue('session', json.dumps(self.state))
        self.settings.sync()

    def primary(self):
        now = int(time.time() * 1000)
        if self.state['phase'] == 'idle':
            self.state = empty_state()
            self.state.update(phase='focus', deadlineMs=now+self.options['focus']*60000)
            if not self.testing and QSystemTrayIcon.isSystemTrayAvailable():
                self.hide()
        elif self.state['paused']:
            self.state['deadlineMs'] = now + self.state['remainingMs']
            self.state['paused'] = False
        else:
            self.state['remainingMs'] = max(0, self.state['deadlineMs']-now)
            self.state['paused'] = True
        self.save()
        self.tick()

    def stop(self):
        self.state = empty_state()
        self.save()
        self.tick()

    def skip(self):
        if self.state['phase'] != 'break':
            return
        self.state.update(phase='focus', paused=False, remainingMs=0, breakKind='short',
                          deadlineMs=int(time.time()*1000)+self.options['focus']*60000)
        self.save()
        self.play('focus')
        self.tick()

    def extend(self):
        if self.state['phase'] == 'break':
            key = 'remainingMs' if self.state['paused'] else 'deadlineMs'
            self.state[key] += 60000
            self.save()
            self.render()

    def play(self, phase):
        if self.options['sound'] and not self.testing:
            sound = self.sounds[phase]
            if sound.status() == QSoundEffect.Status.Error:
                QApplication.beep()
            else:
                sound.play()

    def tick(self):
        now = int(time.time()*1000)
        old_phase = self.state['phase']
        if advance_state(self.state, self.options['focus']*60000, self.options['break']*60000,
                         now, self.options['long']*60000, self.options['cycles']):
            self.save()
            if old_phase != self.state['phase']:
                self.play(self.state['phase'])
        if self.state['phase'] == 'focus' and not self.state['paused']:
            remaining = self.state['deadlineMs']-now
            if 0 < remaining <= 30000 and self.warned != self.state['deadlineMs']:
                self.warned = self.state['deadlineMs']
                if not self.testing:
                    self.tray.showMessage(self.tr_text('Tanaffusga 30 soniya qoldi'), self.tr_text('Ishingizni saqlang yoki taymerni pauzaga qo‘ying.'))
        self.render()

    def render(self):
        state = self.state
        phase = state['phase']
        remaining = state['remainingMs'] if state['paused'] else state['deadlineMs']-int(time.time()*1000)
        seconds = self.options['focus']*60 if phase == 'idle' else max(0, math.ceil(remaining/1000))
        text = f'{seconds//60:02d}:{seconds%60:02d}'
        title = {'idle':'Boshlashga tayyor', 'focus':'O‘qish vaqti', 'break':'Tanaffus'}[phase]
        if phase == 'break' and state.get('breakKind') == 'long':
            title = 'Uzun tanaffus'
        if state['paused']:
            title = self.tr_text(title) + self.tr_text(' — pauza')
        else:
            title = self.tr_text(title)
        self.clock.setText(text)
        self.phase.setText(title)
        self.setWindowTitle(f'{text} · Pomodoro' if phase != 'idle' else 'Pomodoro')
        action = 'Boshlash' if phase == 'idle' else ('Davom ettirish' if state['paused'] else 'Pauza')
        action = self.tr_text(action)
        self.main_button.setText(action)
        self.skip_button.setVisible(phase == 'break')
        self.stop_button.setVisible(phase != 'idle')
        total = self.options['focus' if phase != 'break' else ('long' if state.get('breakKind') == 'long' else 'break')]*60
        self.progress.setValue(min(1000, round(seconds/max(1,total)*1000)))
        self.cycle.setText(self.tr_text("Bajarilgan darslar: {count}", count=state["completedFocus"]) +
                           (self.tr_text(" · Uzun tanaffus har {cycles} darsda", cycles=self.options["cycles"]) if self.options["cycles"] else ""))
        if hasattr(self, 'tray'):
            self.tray.setToolTip(f'{title} · {text}')
            self.tray_status.setText(f'{title} · {text}')
            self.tray_primary.setText(action)
            self.tray_skip.setVisible(phase == 'break')
        if not self.testing:
            if phase == 'break' and not self.breaks:
                self.breaks = [BreakWindow(self, screen) for screen in QApplication.screens()]
            elif phase != 'break':
                self.close_breaks()
            for window in self.breaks:
                window.clock.setText(text)
                window.detail.setText(self.tr_text('Taymer pauzada' if state['paused'] else 'Ko‘zingizni dam oldiring'))
                window.pause.setText(self.tr_text('Davom ettirish' if state['paused'] else 'Pauza'))

    def close_breaks(self):
        self.closing_breaks = True
        for window in self.breaks:
            window.close()
            window.deleteLater()
        self.breaks = []
        self.closing_breaks = False

    def rebuild_breaks(self, *_args):
        self.close_breaks()
        self.render()

    def tray_activated(self, reason):
        if reason in (QSystemTrayIcon.ActivationReason.Trigger, QSystemTrayIcon.ActivationReason.DoubleClick):
            self.present()

    def present(self):
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def closeEvent(self, event):
        if not self.quitting and not self.testing and QSystemTrayIcon.isSystemTrayAvailable():
            self.hide()
            event.ignore()
        else:
            self.save()
            event.accept()
            if not self.testing:
                self.quit()

    def quit(self):
        self.quitting = True
        self.save()
        self.close_breaks()
        self.tray.hide()
        QApplication.quit()


def main():
    app = QApplication(sys.argv)
    app.setApplicationName('Pomodoro')
    app.setOrganizationName('PomodoroDesktop')
    app.setStyle('Fusion')
    app.setStyleSheet(STYLE)
    app.setQuitOnLastWindowClosed(False)
    data = Path(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppLocalDataLocation))
    data.mkdir(parents=True, exist_ok=True)
    lock = QLockFile(str(data / 'desktop.lock'))
    lock.setStaleLockTime(0)
    # Per-user server name; subsequent launches bring the first window forward.
    import hashlib
    server_name = 'pomodoro-' + hashlib.sha256(str(data).encode()).hexdigest()[:16]
    if not lock.tryLock(100):
        socket = QLocalSocket()
        socket.connectToServer(server_name)
        if socket.waitForConnected(1500):
            socket.write(b'show')
            socket.waitForBytesWritten(1000)
            socket.disconnectFromServer()
        else:
            language = QSettings('PomodoroDesktop', 'Pomodoro').value('language', 'en')
            QMessageBox.information(None, 'Pomodoro', translate(language, 'Dastur allaqachon ishlayapti. Tizim panelidagi belgisini bosing.'))
        return 0
    QLocalServer.removeServer(server_name)
    server = QLocalServer()
    server.listen(server_name)
    window = Desktop()
    def show_existing():
        connection = server.nextPendingConnection()
        window.present()
        if connection:
            connection.disconnectFromServer()
            connection.deleteLater()
    server.newConnection.connect(show_existing)
    window.show()
    app.aboutToQuit.connect(window.save)
    return app.exec()


if __name__ == '__main__':
    sys.exit(main())
