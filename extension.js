import Clutter from 'gi://Clutter';
import GLib from 'gi://GLib';
import Gio from 'gi://Gio';
import Shell from 'gi://Shell';
import St from 'gi://St';

import {Extension} from 'resource:///org/gnome/shell/extensions/extension.js';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';
import * as PanelMenu from 'resource:///org/gnome/shell/ui/panelMenu.js';
import * as PopupMenu from 'resource:///org/gnome/shell/ui/popupMenu.js';

import {PomodoroTimer} from './timer.mjs';

function formatTime(totalSeconds) {
    const minutes = Math.floor(totalSeconds / 60);
    const seconds = totalSeconds % 60;
    return `${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`;
}

export default class PomodoroExtension extends Extension {
    enable() {
        this._settings = this.getSettings();
        this._timer = new PomodoroTimer(
            this._settings.get_int('focus-minutes'),
            this._settings.get_int('break-minutes'),
            this._settings.get_int('long-break-minutes'),
            this._settings.get_int('cycles-before-long')
        );
        this._timer.restore(this._settings.get_string('session-state'));
        this._warnedDeadline = 0;
        this._pausedByLock = false;
        this._screenBus = Gio.bus_get_sync(Gio.BusType.SESSION, null);
        this._screenSignalId = this._screenBus.signal_subscribe(
            'org.gnome.ScreenSaver', 'org.gnome.ScreenSaver', 'ActiveChanged',
            '/org/gnome/ScreenSaver', null, Gio.DBusSignalFlags.NONE,
            (_connection, _sender, _path, _interface, _signal, parameters) =>
                this._onScreenLock(parameters.deep_unpack()[0])
        );
        if (this._timer.advance())
            this._saveSession();

        this._indicator = new PanelMenu.Button(0.0, 'Pomodoro Ubuntu', false);
        const panelBox = new St.BoxLayout({style_class: 'pomodoro-panel-box'});
        panelBox.add_child(new St.Icon({
            icon_name: 'alarm-symbolic',
            style_class: 'system-status-icon',
        }));
        this._panelLabel = new St.Label({
            text: '25:00',
            y_align: Clutter.ActorAlign.CENTER,
            style_class: 'pomodoro-panel-label',
        });
        panelBox.add_child(this._panelLabel);
        this._indicator.add_child(panelBox);
        this._buildMenu();
        Main.panel.addToStatusArea(this.uuid, this._indicator, 0, 'center');

        this._sessionChangedId = this._settings.connect('changed::session-state', () => {
            const serialized = this._settings.get_string('session-state');
            if (serialized === this._timer.serialize())
                return;
            if (!this._timer.restore(serialized))
                this._timer.stop();
            if (this._timer.advance())
                this._saveSession();
            this._refresh();
        });
        this._focusChangedId = this._settings.connect('changed::focus-minutes',
            () => this._applyDurations());
        this._breakChangedId = this._settings.connect('changed::break-minutes',
            () => this._applyDurations());
        this._longBreakChangedId = this._settings.connect('changed::long-break-minutes',
            () => this._applyDurations());
        this._cyclesChangedId = this._settings.connect('changed::cycles-before-long',
            () => this._applyDurations());
        this._soundChangedId = this._settings.connect('changed::sound-enabled',
            () => this._soundItem.setToggleState(this._settings.get_boolean('sound-enabled')));
        this._lockChangedId = this._settings.connect('changed::pause-on-lock', () => {
            this._lockItem.setToggleState(this._settings.get_boolean('pause-on-lock'));
            if (this._pausedByLock && !this._settings.get_boolean('pause-on-lock'))
                this._onScreenLock(false);
        });

        this._refresh();
        this._tickId = GLib.timeout_add_seconds(GLib.PRIORITY_DEFAULT, 1, () => {
            this._warnBeforeBreak();
            const previousPhase = this._timer.phase;
            if (previousPhase === 'focus' && !this._timer.paused &&
                this._timer.deadlineMs <= Date.now() &&
                global.display.focus_window?.is_fullscreen()) {
                this._timer.deadlineMs = Date.now() + 60_000;
                this._saveSession();
                Main.notify('Pomodoro', 'To‘liq ekran ishi tugaguncha tanaffus kechiktirildi.');
                this._refresh();
                return GLib.SOURCE_CONTINUE;
            }
            if (this._timer.advance()) {
                this._saveSession();
                if (this._timer.phase !== previousPhase)
                    this._playTransitionSound(this._timer.phase);
            }
            this._refresh();
            return GLib.SOURCE_CONTINUE;
        });
    }

    disable() {
        for (const id of [this._sessionChangedId, this._focusChangedId,
            this._breakChangedId, this._longBreakChangedId,
            this._cyclesChangedId, this._soundChangedId, this._lockChangedId]) {
            if (id)
                this._settings.disconnect(id);
        }
        this._sessionChangedId = null;
        this._focusChangedId = null;
        this._breakChangedId = null;
        this._longBreakChangedId = null;
        this._cyclesChangedId = null;
        this._soundChangedId = null;
        this._lockChangedId = null;
        if (this._screenSignalId) {
            this._screenBus.signal_unsubscribe(this._screenSignalId);
            this._screenSignalId = null;
        }
        this._screenBus = null;
        if (this._tickId) {
            GLib.Source.remove(this._tickId);
            this._tickId = null;
        }
        this._hideBreakScreen();
        this._indicator?.destroy();
        this._indicator = null;
        this._panelLabel = null;
        this._settings = null;
        this._timer = null;
    }

    _buildMenu() {
        this._statusItem = new PopupMenu.PopupMenuItem('', {reactive: false});
        this._indicator.menu.addMenuItem(this._statusItem);
        this._indicator.menu.addMenuItem(new PopupMenu.PopupSeparatorMenuItem());

        this._focusValue = this._addDurationRow('O‘qish', 'focus-minutes', 1, 180);
        this._breakValue = this._addDurationRow('Tanaffus', 'break-minutes', 1, 60);
        this._longBreakValue = this._addDurationRow('Uzun tanaffus', 'long-break-minutes', 5, 60);
        this._cyclesValue = this._addDurationRow('Har nechta darsdan (0=o‘chiq)',
            'cycles-before-long', 0, 12);
        this._soundItem = new PopupMenu.PopupSwitchMenuItem(
            'Tanaffus ovozi', this._settings.get_boolean('sound-enabled')
        );
        this._soundItem.connect('toggled', (_item, state) =>
            this._settings.set_boolean('sound-enabled', state));
        this._indicator.menu.addMenuItem(this._soundItem);
        this._lockItem = new PopupMenu.PopupSwitchMenuItem(
            'Ekran qulflanganda pauza', this._settings.get_boolean('pause-on-lock')
        );
        this._lockItem.connect('toggled', (_item, state) =>
            this._settings.set_boolean('pause-on-lock', state));
        this._indicator.menu.addMenuItem(this._lockItem);
        this._indicator.menu.addMenuItem(new PopupMenu.PopupSeparatorMenuItem());

        this._startItem = new PopupMenu.PopupMenuItem('Boshlash');
        this._startItem.connect('activate', () => {
            this._timer.start();
            this._saveSession();
            this._refresh();
        });
        this._indicator.menu.addMenuItem(this._startItem);

        this._pauseItem = new PopupMenu.PopupMenuItem('Pauza');
        this._pauseItem.connect('activate', () => this._togglePause());
        this._indicator.menu.addMenuItem(this._pauseItem);

        this._skipItem = new PopupMenu.PopupMenuItem('Tanaffusni o‘tkazish');
        this._skipItem.connect('activate', () => this._skipBreak());
        this._indicator.menu.addMenuItem(this._skipItem);

        this._stopItem = new PopupMenu.PopupMenuItem('To‘xtatish');
        this._stopItem.connect('activate', () => this._stop());
        this._indicator.menu.addMenuItem(this._stopItem);
    }

    _addDurationRow(title, key, min, max) {
        const row = new PopupMenu.PopupBaseMenuItem({activate: false, can_focus: false});
        const titleLabel = new St.Label({
            text: title,
            x_expand: true,
            y_align: Clutter.ActorAlign.CENTER,
        });
        const valueLabel = new St.Label({
            text: '',
            y_align: Clutter.ActorAlign.CENTER,
            style_class: 'pomodoro-duration-value',
        });
        row.add_child(titleLabel);
        row.add_child(this._durationButton('−', () => this._changeDuration(key, -1, min, max)));
        row.add_child(valueLabel);
        row.add_child(this._durationButton('+', () => this._changeDuration(key, 1, min, max)));
        this._indicator.menu.addMenuItem(row);
        return valueLabel;
    }

    _durationButton(text, action) {
        const button = new St.Button({
            label: text,
            style_class: 'pomodoro-step-button',
            can_focus: true,
        });
        button.connect('clicked', action);
        return button;
    }

    _changeDuration(key, delta, min, max) {
        const oldValue = this._settings.get_int(key);
        const nextValue = Math.max(min, Math.min(max, oldValue + delta));
        if (nextValue === oldValue)
            return;
        this._settings.set_int(key, nextValue);
        this._applyDurations();
    }

    _applyDurations() {
        this._timer.configure(
            this._settings.get_int('focus-minutes'),
            this._settings.get_int('break-minutes'),
            this._settings.get_int('long-break-minutes'),
            this._settings.get_int('cycles-before-long')
        );
        this._refresh();
    }

    _togglePause() {
        if (this._timer.paused)
            this._timer.resume();
        else
            this._timer.pause();
        this._saveSession();
        this._refresh();
    }

    _skipBreak() {
        this._timer.skipBreak();
        this._saveSession();
        this._refresh();
    }

    _stop() {
        this._timer.stop();
        this._saveSession();
        this._refresh();
    }

    _saveSession() {
        this._settings.set_string('session-state', this._timer.serialize());
    }

    _onScreenLock(locked) {
        if (locked) {
            if (!this._settings.get_boolean('pause-on-lock') ||
                this._timer.phase === 'idle' || this._timer.paused)
                return;
            this._pausedByLock = true;
            this._timer.pause();
        } else {
            if (!this._pausedByLock)
                return;
            this._pausedByLock = false;
            if (!this._timer.paused || this._timer.phase === 'idle')
                return;
            this._timer.resume();
        }
        this._saveSession();
        this._refresh();
    }

    _warnBeforeBreak() {
        if (this._timer.phase !== 'focus' || this._timer.paused)
            return;
        const left = this._timer.deadlineMs - Date.now();
        if (left > 0 && left <= 30_000 && this._warnedDeadline !== this._timer.deadlineMs) {
            this._warnedDeadline = this._timer.deadlineMs;
            Main.notify('Pomodoro', 'Tanaffusga 30 soniya qoldi. Ishingizni saqlang.');
        }
    }

    _extendBreak() {
        this._timer.extendBreak();
        this._saveSession();
        this._refresh();
    }

    _playTransitionSound(phase) {
        if (!this._settings.get_boolean('sound-enabled'))
            return;
        const event = phase === 'break' ? 'message-new-instant' : 'complete';
        const file = phase === 'break' ? 'break-start.oga' : 'break-end.oga';
        const fallback = () => {
            try {
                Gio.Subprocess.new(
                    ['pw-play', GLib.build_filenamev([this.path, file])],
                    Gio.SubprocessFlags.NONE
                );
            } catch (error) {
                console.warn(`Pomodoro ovozi ijro etilmadi: ${error}`);
            }
        };
        try {
            const process = Gio.Subprocess.new(
                ['canberra-gtk-play', '-i', event], Gio.SubprocessFlags.NONE
            );
            process.wait_async(null, (proc, result) => {
                try {
                    proc.wait_finish(result);
                    if (!proc.get_if_exited() || proc.get_exit_status() !== 0)
                        fallback();
                } catch {
                    fallback();
                }
            });
        } catch (error) {
            fallback();
        }
    }

    _refresh() {
        const phase = this._timer.phase;
        const left = phase === 'idle'
            ? this._settings.get_int('focus-minutes') * 60
            : this._timer.secondsLeft();
        const time = formatTime(left);

        this._panelLabel.text = phase === 'idle' ? time
            : phase === 'break' ? `${this._timer.breakKind === 'long' ? 'Uzun dam' : 'Dam'} ${time}`
                : `Dars ${time}`;
        if (phase === 'break')
            this._panelLabel.add_style_class_name('pomodoro-panel-break');
        else
            this._panelLabel.remove_style_class_name('pomodoro-panel-break');
        const cycles = this._settings.get_int('cycles-before-long');
        const cycleText = cycles > 0
            ? ` — davr ${this._timer.completedFocus % cycles}/${cycles}`
            : ` — ${this._timer.completedFocus} dars`;
        this._statusItem.label.text = phase === 'idle'
            ? 'Boshlashga tayyor'
            : `${phase === 'break' ? this._timer.breakKind === 'long' ? 'Uzun tanaffus' : 'Tanaffus' : 'O‘qish'}: ${time}${this._timer.paused ? ' (pauza)' : ''}${cycleText}`;
        this._focusValue.text = `${this._settings.get_int('focus-minutes')} daq.`;
        this._breakValue.text = `${this._settings.get_int('break-minutes')} daq.`;
        this._longBreakValue.text = `${this._settings.get_int('long-break-minutes')} daq.`;
        this._cyclesValue.text = `${cycles}`;
        this._startItem.visible = phase === 'idle';
        this._pauseItem.visible = phase !== 'idle';
        this._pauseItem.label.text = this._timer.paused ? 'Davom ettirish' : 'Pauza';
        this._skipItem.visible = phase === 'break';
        this._stopItem.visible = phase !== 'idle';

        if (phase === 'break') {
            this._showBreakScreen();
            this._breakHeading.text = this._timer.breakKind === 'long'
                ? 'UZUN TANAFFUS' : 'TANAFFUS';
            this._breakTime.text = time;
            this._breakPauseButton.label = this._timer.paused ? 'Davom ettirish' : 'Pauza';
            this._breakCaption.text = this._timer.paused
                ? 'Taymer pauzada'
                : 'Ko‘zingizni dam oldiring, biroz harakat qiling';
        } else {
            this._hideBreakScreen();
        }
    }

    _showBreakScreen() {
        if (this._breakScreen)
            return;

        const screen = new St.Widget({
            reactive: true,
            can_focus: true,
        });
        this._breakScreen = screen;
        screen.connect('key-press-event', (_actor, event) => {
            if (event.get_key_symbol() === Clutter.KEY_Escape) {
                this._skipBreak();
                return Clutter.EVENT_STOP;
            }
            return Clutter.EVENT_PROPAGATE;
        });
        this._resizeBreakScreen();

        const monitors = Main.layoutManager.monitors.length
            ? Main.layoutManager.monitors
            : [{x: 0, y: 0, width: global.stage.width, height: global.stage.height}];
        const primaryIndex = Main.layoutManager.primaryIndex ?? 0;
        let primaryBackground = null;
        monitors.forEach((monitor, index) => {
            const background = new St.Widget({
                style_class: 'pomodoro-break-screen',
                layout_manager: new Clutter.BinLayout(),
            });
            background.set_position(monitor.x, monitor.y);
            background.set_size(monitor.width, monitor.height);
            const dim = new St.Widget({style_class: 'pomodoro-break-dim'});
            dim.set_size(monitor.width, monitor.height);
            background.add_child(dim);
            screen.add_child(background);
            if (index === primaryIndex)
                primaryBackground = background;
        });

        const content = new St.BoxLayout({
            vertical: true,
            style_class: 'pomodoro-break-content',
            x_align: Clutter.ActorAlign.CENTER,
            y_align: Clutter.ActorAlign.CENTER,
        });
        this._breakHeading = new St.Label({
            text: 'TANAFFUS',
            style_class: 'pomodoro-break-heading',
            x_align: Clutter.ActorAlign.CENTER,
        });
        content.add_child(this._breakHeading);
        this._breakTime = new St.Label({
            text: '',
            style_class: 'pomodoro-break-time',
            x_align: Clutter.ActorAlign.CENTER,
        });
        content.add_child(this._breakTime);
        this._breakCaption = new St.Label({
            text: '',
            style_class: 'pomodoro-break-caption',
            x_align: Clutter.ActorAlign.CENTER,
        });
        content.add_child(this._breakCaption);

        const buttons = new St.BoxLayout({
            style_class: 'pomodoro-break-buttons',
            x_align: Clutter.ActorAlign.CENTER,
        });
        this._breakPauseButton = new St.Button({
            label: 'Pauza',
            can_focus: true,
            style_class: 'pomodoro-break-button',
        });
        this._breakPauseButton.connect('clicked', () => this._togglePause());
        buttons.add_child(this._breakPauseButton);

        const extendButton = new St.Button({
            label: '+1 daqiqa',
            can_focus: true,
            style_class: 'pomodoro-break-button',
        });
        extendButton.connect('clicked', () => this._extendBreak());
        buttons.add_child(extendButton);

        const skipButton = new St.Button({
            label: 'Darsga qaytish',
            can_focus: true,
            style_class: 'pomodoro-break-button pomodoro-primary-button',
        });
        skipButton.connect('clicked', () => this._skipBreak());
        buttons.add_child(skipButton);
        content.add_child(buttons);
        (primaryBackground ?? screen.get_children()[0]).add_child(content);

        Main.layoutManager.addTopChrome(screen, {
            affectsStruts: false,
            trackFullscreen: false,
        });
        this._monitorsChangedId = Main.layoutManager.connect('monitors-changed', () => {
            this._hideBreakScreen();
            this._showBreakScreen();
            this._refresh();
        });
        this._modalGrab = Main.pushModal(screen, {actionMode: Shell.ActionMode.SYSTEM_MODAL});
        if (this._modalGrab)
            global.stage.set_key_focus(skipButton);
    }

    _resizeBreakScreen() {
        if (this._breakScreen)
            this._breakScreen.set_size(global.stage.width, global.stage.height);
    }

    _hideBreakScreen() {
        if (!this._breakScreen)
            return;
        if (this._modalGrab) {
            Main.popModal(this._modalGrab);
            this._modalGrab = null;
        }
        if (this._monitorsChangedId) {
            Main.layoutManager.disconnect(this._monitorsChangedId);
            this._monitorsChangedId = null;
        }
        this._breakScreen.destroy();
        this._breakScreen = null;
        this._breakTime = null;
        this._breakHeading = null;
        this._breakPauseButton = null;
        this._breakCaption = null;
    }
}
