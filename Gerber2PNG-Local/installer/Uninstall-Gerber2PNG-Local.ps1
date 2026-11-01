[CmdletBinding()]
param(
    [string]$InstallRoot = "$env:ProgramFiles\Gerber2PNG Local Server",
    [string]$PluginDirectory
)

$ErrorActionPreference = 'Stop'
$ServiceName = 'Gerber2PNGLocalServer'
$PluginFolderName = 'com_github_fablabkerala_gerber2png-plugin-for-kicad'
$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$admin = ([Security.Principal.WindowsPrincipal]$identity).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $admin) {
    $args = @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', "`"$PSCommandPath`"", '-InstallRoot', "`"$InstallRoot`"")
    if ($PluginDirectory) { $args += @('-PluginDirectory', "`"$PluginDirectory`"") }
    Start-Process -FilePath 'powershell.exe' -Verb RunAs -ArgumentList $args
    exit
}

$nssm = Join-Path $InstallRoot 'nssm.exe'
if (Test-Path -LiteralPath $nssm) {
    & $nssm stop $ServiceName | Out-Null
    & $nssm remove $ServiceName confirm | Out-Null
} elseif (Get-Service -Name $ServiceName -ErrorAction SilentlyContinue) {
    throw "Cannot safely remove $ServiceName because its NSSM executable is missing from $InstallRoot."
}

if (-not $PluginDirectory) {
    Add-Type -AssemblyName System.Windows.Forms
    $dialog = New-Object System.Windows.Forms.FolderBrowserDialog
    $dialog.Description = 'Select the KiCad 10.0\3rdparty\plugins folder containing the Gerber2PNG plugin'
    $candidates = @(
        (Join-Path $env:APPDATA 'kicad\10.0\3rdparty\plugins'),
        (Join-Path $env:USERPROFILE 'Documents\KiCad\10.0\3rdparty\plugins'),
        (Join-Path $env:USERPROFILE 'OneDrive\Documents\KiCad\10.0\3rdparty\plugins'),
        'D:\OneDrive\Documents\KiCad\10.0\3rdparty\plugins'
    )
    $found = $candidates | Where-Object { Test-Path -LiteralPath (Join-Path $_ $PluginFolderName) } | Select-Object -First 1
    if ($found) { $dialog.SelectedPath = $found }
    if ($dialog.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK) { $PluginDirectory = $dialog.SelectedPath }
}

if ($PluginDirectory) {
    $pluginPath = Join-Path $PluginDirectory $PluginFolderName
    if ((Test-Path -LiteralPath $pluginPath) -and (Read-Host "Remove plugin folder $pluginPath? Type YES to confirm") -ceq 'YES') {
        Remove-Item -LiteralPath $pluginPath -Recurse -Force
    }
}

if (Test-Path -LiteralPath (Join-Path $InstallRoot 'environment-backup.json')) {
    $previousEnvironment = Get-Content -LiteralPath (Join-Path $InstallRoot 'environment-backup.json') -Raw | ConvertFrom-Json
    if ([Environment]::GetEnvironmentVariable('GERBER2PNG_SERVER_ROOT', 'Machine') -eq $InstallRoot) {
        [Environment]::SetEnvironmentVariable('GERBER2PNG_SERVER_ROOT', $previousEnvironment.GERBER2PNG_SERVER_ROOT, 'Machine')
        [Environment]::SetEnvironmentVariable('GERBER2PNG_PYTHON', $previousEnvironment.GERBER2PNG_PYTHON, 'Machine')
    }
}
if ((Test-Path -LiteralPath $InstallRoot) -and (Read-Host "Remove local service files from $InstallRoot? Type YES to confirm") -ceq 'YES') {
    Remove-Item -LiteralPath $InstallRoot -Recurse -Force
}
Write-Host 'Gerber2PNG local service removal finished.' -ForegroundColor Green
