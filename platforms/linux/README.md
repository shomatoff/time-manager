# Linux

**EN:** A focus/rest timer with configurable Pomodoro sessions, full-screen breaks, sounds and tray controls.

**UZ:** Sozlanadigan dars/tanaffus vaqtlari, to‘liq ekran tanaffusi, ovozlar va panel boshqaruvi bor Pomodoro taymeri.

**RU:** Таймер работы и отдыха с настройкой длительности, полноэкранными перерывами, звуками и системным треем.

## Common desktop package — English / Русский / O‘zbekcha

Download **Pomodoro-Linux-x64.tar.gz**, extract it, and run:

```sh
./Pomodoro
# Optional: install in your user account and create shortcuts
bash install-linux.sh
```

**UZ:** Arxivni oching va `./Pomodoro` ni ishga tushiring. Tilni oynaning yuqorisidan tanlang. `bash install-linux.sh` foydalanuvchi hisobiga o‘rnatib, yorliq yaratadi.

**RU:** Распакуйте архив и запустите `./Pomodoro`. Язык выбирается вверху окна. `bash install-linux.sh` устанавливает приложение для текущего пользователя.

Keep the executable and `_internal` together. The package is built on Ubuntu 24.04 x64; older distributions may need a source installation. Tray support depends on your desktop. When the tray is unavailable, closing the main window exits the application and saves the session.

## Optional Ubuntu 24.04 / GNOME 46 integration

The native version displays timer text directly in the top panel. From the source directory:

```sh
./install.sh
```

It uses GTK/PyGObject and GNOME Shell, and currently has an Uzbek interface. The Qt package above has all three languages. Do not run both variants at once; they have separate settings.

## Build on Linux

```sh
python -m pip install -r requirements-desktop.txt "pyinstaller>=6.11,<7"
python scripts/build_desktop.py
```

Output: `dist/linux/Pomodoro/` and `dist/Pomodoro-Linux-x64.tar.gz`.
