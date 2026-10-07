export class PomodoroTimer {
    constructor(focusMinutes = 25, breakMinutes = 5, longBreakMinutes = 15,
        cyclesBeforeLong = 0) {
        this.configure(focusMinutes, breakMinutes, longBreakMinutes, cyclesBeforeLong);
        this.stop();
    }

    configure(focusMinutes, breakMinutes, longBreakMinutes = 15, cyclesBeforeLong = 0) {
        this.focusMs = Math.max(1, Math.min(180, focusMinutes)) * 60_000;
        this.breakMs = Math.max(1, Math.min(60, breakMinutes)) * 60_000;
        this.longBreakMs = Math.max(5, Math.min(60, longBreakMinutes)) * 60_000;
        this.cyclesBeforeLong = Math.max(0, Math.min(12, cyclesBeforeLong));
    }

    start(now = Date.now()) {
        this.phase = 'focus';
        this.deadlineMs = now + this.focusMs;
        this.remainingMs = 0;
        this.paused = false;
        this.completedFocus = 0;
        this.breakKind = 'short';
    }

    stop() {
        this.phase = 'idle';
        this.deadlineMs = 0;
        this.remainingMs = 0;
        this.paused = false;
        this.completedFocus = 0;
        this.breakKind = 'short';
    }

    advance(now = Date.now()) {
        if (this.phase === 'idle' || this.paused || now < this.deadlineMs)
            return false;

        // Durations are at least one minute, so this also catches up after suspend.
        for (let transitions = 0; now >= this.deadlineMs && transitions < 100_000; transitions++) {
            if (this.phase === 'focus') {
                this.completedFocus++;
                this.phase = 'break';
                this.breakKind = this.cyclesBeforeLong > 0 &&
                    this.completedFocus % this.cyclesBeforeLong === 0 ? 'long' : 'short';
                this.deadlineMs += this.breakKind === 'long' ? this.longBreakMs : this.breakMs;
            } else {
                this.phase = 'focus';
                this.breakKind = 'short';
                this.deadlineMs += this.focusMs;
            }
        }
        return true;
    }

    pause(now = Date.now()) {
        if (this.phase === 'idle' || this.paused)
            return;
        this.advance(now);
        this.remainingMs = Math.max(0, this.deadlineMs - now);
        this.paused = true;
    }

    resume(now = Date.now()) {
        if (!this.paused)
            return;
        this.deadlineMs = now + this.remainingMs;
        this.remainingMs = 0;
        this.paused = false;
    }

    skipBreak(now = Date.now()) {
        if (this.phase !== 'break')
            return;
        this.phase = 'focus';
        this.deadlineMs = now + this.focusMs;
        this.remainingMs = 0;
        this.paused = false;
        this.breakKind = 'short';
    }

    extendBreak(milliseconds = 60_000) {
        if (this.phase !== 'break')
            return;
        if (this.paused)
            this.remainingMs += milliseconds;
        else
            this.deadlineMs += milliseconds;
    }

    secondsLeft(now = Date.now()) {
        if (this.phase === 'idle')
            return 0;
        const milliseconds = this.paused ? this.remainingMs : this.deadlineMs - now;
        return Math.max(0, Math.ceil(milliseconds / 1000));
    }

    serialize() {
        return JSON.stringify({
            phase: this.phase,
            deadlineMs: this.deadlineMs,
            remainingMs: this.remainingMs,
            paused: this.paused,
            completedFocus: this.completedFocus,
            breakKind: this.breakKind,
        });
    }

    restore(serialized) {
        try {
            const state = JSON.parse(serialized);
            if (!['focus', 'break'].includes(state.phase) ||
                !Number.isFinite(state.deadlineMs) || state.deadlineMs <= 0 ||
                !Number.isFinite(state.remainingMs) || state.remainingMs < 0 ||
                typeof state.paused !== 'boolean' ||
                !Number.isSafeInteger(state.completedFocus) || state.completedFocus < 0)
                return false;
            this.phase = state.phase;
            this.deadlineMs = state.deadlineMs;
            this.remainingMs = state.remainingMs;
            this.paused = state.paused;
            this.completedFocus = state.completedFocus;
            this.breakKind = state.breakKind === 'long' ? 'long' : 'short';
            return true;
        } catch {
            return false;
        }
    }
}
