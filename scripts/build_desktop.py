"""Build on the target OS: python scripts/build_desktop.py."""
import shutil
import subprocess
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[1]
platform = 'windows' if sys.platform == 'win32' else 'linux'
title = 'Windows' if platform == 'windows' else 'Linux'
command = [sys.executable, '-m', 'PyInstaller', '--noconfirm', '--clean',
           '--windowed', '--onedir', '--name', 'Pomodoro',
           '--distpath', str(root / 'dist' / platform), '--workpath', str(root / 'build'),
           '--specpath', str(root / 'build')]
for filename in ['pomodoro.svg', 'black-hole.jpg', 'break-start.wav', 'break-end.wav']:
    command += ['--add-data', f'{root / filename}:.']
command.append(str(root / 'desktop.py'))
subprocess.run(command, cwd=root, check=True)
bundle = root / 'dist' / platform / 'Pomodoro'
shutil.copy2(root / 'README.md', bundle / 'README.md')
shutil.copytree(root / 'docs', bundle / 'docs', dirs_exist_ok=True)
shutil.copytree(root / 'platforms', bundle / 'platforms', dirs_exist_ok=True)
installer = 'install-windows.ps1' if sys.platform == 'win32' else 'install-linux.sh'
shutil.copy2(root / 'scripts' / installer, bundle / installer)
archive = shutil.make_archive(str(root / 'dist' / f'Pomodoro-{title}-x64'),
                             'zip' if platform == 'windows' else 'gztar', root_dir=bundle)
print(f'Ready: {bundle}')
print(f'Archive: {archive}')
