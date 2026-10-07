# Windows

**EN:** Pomodoro helps you manage focus and rest: 25 minutes of work, 5 minutes of rest, with configurable durations, sounds and a full-screen break timer.

**UZ:** Pomodoro ish va dam olish vaqtini boshqaradi: 25 daqiqa ish, 5 daqiqa tanaffus. Vaqtlar, ovozlar va to‘liq ekran tanaffusini boshqarish mumkin.

**RU:** Pomodoro чередует работу и отдых: 25 минут работы и 5 минут перерыва. Длительность и звуки можно настроить.

1. Download and extract **Pomodoro-Windows-x64.zip**.
2. Keep `Pomodoro.exe` and `_internal` together. Double-click `Pomodoro.exe`; Python is not required.
3. Choose **English / Русский / O‘zbekcha** at the top.
4. Optional Desktop and Start Menu shortcuts: run `install-windows.ps1` in PowerShell from the extracted directory. It installs under your LocalAppData account without administrator access. If your PowerShell policy blocks scripts, run the exe directly.

**UZ:** ZIP’ni oching va `Pomodoro.exe` ni ikki marta bosing. `_internal` papkasini o‘chirmang. Tilni oynaning yuqorisidan tanlang. Yorliq yaratish uchun `install-windows.ps1` bor.

**RU:** Распакуйте ZIP и запустите `Pomodoro.exe`. Не удаляйте `_internal`. Язык выбирается вверху окна. `install-windows.ps1` создаёт ярлыки.

Closing the window keeps the timer in the system tray. Use **Quit application** from the tray menu to exit. Hover over the tray icon to see the remaining time. A second launch reopens the first window.

## Build on Windows

```powershell
python -m pip install -r requirements-desktop.txt "pyinstaller>=6.11,<7"
python scripts/build_desktop.py
```

Output: `dist/windows/Pomodoro/` and `dist/Pomodoro-Windows-x64.zip`.
