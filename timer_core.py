"""EN: Shared timer transitions, independent of the operating system.
UZ: Operatsion tizimga bog‘liq bo‘lmagan umumiy taymer bosqichlari.
"""

def empty_state():
    return {
        "phase": "idle",
        "deadlineMs": 0,
        "remainingMs": 0,
        "paused": False,
        "completedFocus": 0,
        "breakKind": "short",
    }


def advance_state(state, focus_ms, break_ms, now_ms,
                  long_break_ms=15 * 60_000, cycles_before_long=0):
    """Advance a saved session after a phase ends, including long sleep gaps."""
    if state["phase"] == "idle" or state["paused"] or now_ms < state["deadlineMs"]:
        return False
    for _ in range(100_000):
        if now_ms < state["deadlineMs"]:
            break
        if state["phase"] == "focus":
            state["completedFocus"] += 1
            state["phase"] = "break"
            state["breakKind"] = "long" if cycles_before_long > 0 and \
                state["completedFocus"] % cycles_before_long == 0 else "short"
            state["deadlineMs"] += long_break_ms if state["breakKind"] == "long" else break_ms
        else:
            state["phase"] = "focus"
            state["breakKind"] = "short"
            state["deadlineMs"] += focus_ms
    return True


