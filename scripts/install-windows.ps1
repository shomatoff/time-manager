# EN: Install for the current user and create shortcuts.
# UZ: Joriy foydalanuvchiga o‘rnatadi va yorliqlar yaratadi.
$ErrorActionPreference = 'Stop'
$Source = $PSScriptRoot
if (-not (Test-Path (Join-Path $Source 'Pomodoro.exe'))) {
    throw 'Run this script from the extracted Pomodoro Windows bundle.'
}
$Destination = Join-Path $env:LOCALAPPDATA 'Programs\Pomodoro'
New-Item -ItemType Directory -Force -Path $Destination | Out-Null
Copy-Item -Path (Join-Path $Source '*') -Destination $Destination -Recurse -Force
$Shell = New-Object -ComObject WScript.Shell
foreach ($Folder in @([Environment]::GetFolderPath('Desktop'), [Environment]::GetFolderPath('Programs'))) {
    $Shortcut = $Shell.CreateShortcut((Join-Path $Folder 'Pomodoro.lnk'))
    $Shortcut.TargetPath = Join-Path $Destination 'Pomodoro.exe'
    $Shortcut.WorkingDirectory = $Destination
    $Shortcut.Description = 'Focus and break timer'
    $Shortcut.Save()
}
Write-Host 'Pomodoro installed. Open the Desktop shortcut.'
