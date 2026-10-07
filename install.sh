#!/usr/bin/env bash
set -euo pipefail

project_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
uuid='pomodoro-ubuntu@chainjas.local'

if ! command -v gnome-extensions >/dev/null || ! command -v gnome-shell >/dev/null; then
    printf 'GNOME Shell va gnome-extensions kerak.\n' >&2
    exit 1
fi

if [[ "$(gnome-shell --version)" != 'GNOME Shell 46.'* ]]; then
    printf 'Bu versiya GNOME Shell 46 uchun tayyorlangan.\n' >&2
    exit 1
fi

mkdir -p "$project_dir/dist"
gnome-extensions pack --force \
    --out-dir="$project_dir/dist" \
    --extra-source=timer.mjs \
    --extra-source=black-hole.jpg \
    --extra-source=break-start.oga \
    --extra-source=break-end.oga \
    --schema=schemas/org.gnome.shell.extensions.pomodoro-ubuntu.gschema.xml \
    "$project_dir"

bundle="$project_dir/dist/$uuid.shell-extension.zip"
gnome-extensions install --force "$bundle"
glib-compile-schemas "$HOME/.local/share/gnome-shell/extensions/$uuid/schemas"

app_dir="$HOME/.local/share/pomodoro-ubuntu"
applications_dir="$HOME/.local/share/applications"
desktop_dir="$(xdg-user-dir DESKTOP 2>/dev/null || true)"
desktop_dir="${desktop_dir:-$HOME/Desktop}"
mkdir -p "$app_dir" "$applications_dir" "$desktop_dir"
install -m 755 "$project_dir/control.py" "$app_dir/control.py"
install -m 644 "$project_dir/indicator.py" "$app_dir/indicator.py"
install -m 644 "$project_dir/timer_core.py" "$app_dir/timer_core.py"
install -m 644 "$project_dir/pomodoro.svg" "$app_dir/pomodoro.svg"

application_entry="$applications_dir/pomodoro-ubuntu.desktop"
cat > "$application_entry" <<EOF
[Desktop Entry]
Type=Application
Name=Pomodoro Ubuntu
Comment=O‘qish va tanaffus taymeri
Exec=/usr/bin/python3 "$app_dir/control.py"
Icon=$app_dir/pomodoro.svg
Terminal=false
StartupNotify=true
Categories=Utility;
EOF
desktop_entry="$desktop_dir/Pomodoro Ubuntu.desktop"
install -m 755 "$application_entry" "$desktop_entry"
gio set "$desktop_entry" metadata::trusted true

if [[ -f "$project_dir/HISOBOT.md" ]]; then
    install -m 644 "$project_dir/HISOBOT.md" "$desktop_dir/Pomodoro Ubuntu - Hisobot.md"
fi
if [[ -f "$project_dir/HISOBOT.html" ]]; then
    install -m 644 "$project_dir/HISOBOT.html" "$desktop_dir/Pomodoro Ubuntu - Hisobot.html"
fi
if [[ -f "$project_dir/GEMINI_MASLAHAT.md" ]]; then
    install -m 644 "$project_dir/GEMINI_MASLAHAT.md" "$desktop_dir/Pomodoro Ubuntu - Gemini maslahat.md"
fi

if gnome-extensions enable "$uuid" 2>/dev/null; then
    printf 'Pomodoro o‘rnatildi va yoqildi. Desktopdagi yorliqni ikki marta bosing.\n'
else
    python3 - "$uuid" <<'PY'
import ast
import subprocess
import sys

uuid = sys.argv[1]
value = subprocess.check_output(
    ['gsettings', 'get', 'org.gnome.shell', 'enabled-extensions'],
    text=True,
)
enabled = ast.literal_eval(value.strip())
if uuid not in enabled:
    enabled.append(uuid)
    subprocess.run(
        ['gsettings', 'set', 'org.gnome.shell', 'enabled-extensions', str(enabled)],
        check=True,
    )
PY
    printf 'Desktop yorlig‘i tayyor. Hozir panelda AppIndicators taymeri ishlaydi. '
    printf 'Qayta kirganda GNOME kengaytmasi avtomatik yoqiladi.\n'
fi
