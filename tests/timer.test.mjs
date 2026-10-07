import assert from 'node:assert/strict';
import test from 'node:test';

import {PomodoroTimer} from '../timer.mjs';

const minute = 60_000;

test('25 daqiqa o‘qishdan so‘ng 5 daqiqa tanaffus, keyin yangi o‘qish boshlanadi', () => {
    const timer = new PomodoroTimer();
    timer.start(0);
    assert.equal(timer.secondsLeft(24 * minute), 60);
    assert.equal(timer.advance(25 * minute), true);
    assert.equal(timer.phase, 'break');
    assert.equal(timer.secondsLeft(25 * minute), 300);
    assert.equal(timer.completedFocus, 1);
    assert.equal(timer.advance(30 * minute), true);
    assert.equal(timer.phase, 'focus');
    assert.equal(timer.secondsLeft(30 * minute), 1500);
});

test('pauza qolgan vaqtni saqlaydi va davom ettirish uni tiklaydi', () => {
    const timer = new PomodoroTimer(2, 1);
    timer.start(0);
    timer.pause(30_000);
    assert.equal(timer.secondsLeft(4 * minute), 90);
    assert.equal(timer.advance(4 * minute), false);
    timer.resume(4 * minute);
    assert.equal(timer.secondsLeft(4 * minute), 90);
    assert.equal(timer.advance(5 * minute + 30_000), true);
    assert.equal(timer.phase, 'break');
});

test('uzoq uyqudan keyin vaqt va bosqich to‘g‘ri hisoblanadi', () => {
    const timer = new PomodoroTimer();
    timer.start(0);
    assert.equal(timer.advance(24 * 60 * minute + 27 * minute), true);
    assert.equal(timer.phase, 'break');
    assert.equal(timer.secondsLeft(24 * 60 * minute + 27 * minute), 180);
    assert.equal(timer.completedFocus, 49);
});

test('sessiya qayta tiklanadi va tanaffusni o‘tkazish yangi ishni boshlaydi', () => {
    const timer = new PomodoroTimer();
    timer.start(0);
    timer.advance(25 * minute);
    const restored = new PomodoroTimer();
    assert.equal(restored.restore(timer.serialize()), true);
    assert.equal(restored.phase, 'break');
    restored.skipBreak(26 * minute);
    assert.equal(restored.phase, 'focus');
    assert.equal(restored.secondsLeft(26 * minute), 1500);
    assert.equal(restored.restore('{bad json'), false);
});

test('to‘rtinchi darsdan keyin ixtiyoriy uzun tanaffus ishlaydi', () => {
    const timer = new PomodoroTimer(1, 1, 15, 4);
    timer.start(0);
    timer.advance(7 * minute);
    assert.equal(timer.phase, 'break');
    assert.equal(timer.breakKind, 'long');
    assert.equal(timer.completedFocus, 4);
    assert.equal(timer.secondsLeft(7 * minute), 15 * 60);
    timer.extendBreak();
    assert.equal(timer.secondsLeft(7 * minute), 16 * 60);
    timer.pause(7 * minute);
    timer.extendBreak();
    assert.equal(timer.secondsLeft(7 * minute), 17 * 60);
    timer.resume(8 * minute);
    assert.equal(timer.breakKind, 'long');
});
