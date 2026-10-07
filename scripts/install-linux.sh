#!/usr/bin/env bash
set -euo pipefail
bundle_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
test -f "$bundle_dir/Pomodoro"
app_dir="$HOME/.local/share/pomodoro-desktop"
mkdir -p "$app_dir" "$HOME/.local/share/applications"
cp -a "$bundle_dir/." "$app_dir/"
chmod +x "$app_dir/Pomodoro"
entry="$HOME/.local/share/applications/pomodoro-desktop.desktop"
cat > "$entry" <<EOF
[Desktop Entry]
Type=Application
Name=Pomodoro
Exec="$app_dir/Pomodoro"
Icon=$app_dir/_internal/pomodoro.svg
Terminal=false
Categories=Utility;
EOF
desktop_dir="$(xdg-user-dir DESKTOP 2>/dev/null || true)"
if [[ -n "$desktop_dir" && -d "$desktop_dir" ]]; then
    install -m 755 "$entry" "$desktop_dir/Pomodoro.desktop"
    gio set "$desktop_dir/Pomodoro.desktop" metadata::trusted true 2>/dev/null || true
fi
printf 'Pomodoro installed. Open the application menu or Desktop shortcut.\n'
