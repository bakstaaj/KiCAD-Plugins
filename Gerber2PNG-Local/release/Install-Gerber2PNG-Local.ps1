[CmdletBinding()]
param(
    [string]$InstallRoot = "$env:ProgramFiles\Gerber2PNG Local Server",
    [string]$PluginDirectory
)

$ErrorActionPreference = 'Stop'
$ServiceName = 'Gerber2PNGLocalServer'
$PluginFolderName = 'com_github_fablabkerala_gerber2png-plugin-for-kicad'
$PackageRoot = $PSScriptRoot

function Select-Folder([string]$Description, [string]$InitialPath) {
    Add-Type -AssemblyName System.Windows.Forms
    $dialog = New-Object System.Windows.Forms.FolderBrowserDialog
    $dialog.Description = $Description
    $dialog.ShowNewFolderButton = $true
    if ($InitialPath -and (Test-Path -LiteralPath $InitialPath)) { $dialog.SelectedPath = $InitialPath }
    if ($dialog.ShowDialog() -ne [System.Windows.Forms.DialogResult]::OK) { throw 'Installation cancelled.' }
    return $dialog.SelectedPath
}

function Test-Administrator {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    return ([Security.Principal.WindowsPrincipal]$identity).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

if (-not (Test-Administrator)) {
    $argumentLine = @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', "`"$PSCommandPath`"")
    if ($InstallRoot) { $argumentLine += @('-InstallRoot', "`"$InstallRoot`"") }
    if ($PluginDirectory) { $argumentLine += @('-PluginDirectory', "`"$PluginDirectory`"") }
    Start-Process -FilePath 'powershell.exe' -Verb RunAs -ArgumentList $argumentLine
    exit
}

$nssmSource = Join-Path $PackageRoot 'NSSM\win64\nssm.exe'
$serverSource = Join-Path $PackageRoot 'Service\server.py'
$distSource = Join-Path $PackageRoot 'Service\dist'
$pythonArchive = Join-Path $PackageRoot 'PythonRuntime\python-3.13.17-embed-amd64.zip'
$pluginSource = Join-Path (Join-Path $PackageRoot 'KiCadPlugin') $PluginFolderName
foreach ($required in @($nssmSource, $serverSource, $pythonArchive, (Join-Path $distSource 'index.html'), (Join-Path $pluginSource '__init__.py'))) {
    if (-not (Test-Path -LiteralPath $required)) { throw "Package file is missing: $required" }
}

if (-not $PluginDirectory) {
    $candidates = @(
        (Join-Path $env:APPDATA 'kicad\10.0\3rdparty\plugins'),
        (Join-Path $env:USERPROFILE 'Documents\KiCad\10.0\3rdparty\plugins'),
        (Join-Path $env:USERPROFILE 'OneDrive\Documents\KiCad\10.0\3rdparty\plugins'),
        'D:\OneDrive\Documents\KiCad\10.0\3rdparty\plugins'
    )
    $suggestion = $candidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
    $PluginDirectory = Select-Folder 'Select KiCad 10.0\3rdparty\plugins' $suggestion
}
if (-not (Test-Path -LiteralPath $PluginDirectory)) { New-Item -ItemType Directory -Path $PluginDirectory -Force | Out-Null }

$portOwner = Get-NetTCPConnection -State Listen -LocalPort 4172 -ErrorAction SilentlyContinue | Select-Object -First 1
if ($portOwner) {
    $existingService = Get-CimInstance Win32_Service -Filter "ProcessId=$($portOwner.OwningProcess)" -ErrorAction SilentlyContinue
    if (-not $existingService -or $existingService.Name -ne $ServiceName) {
        throw "Port 4172 is already in use by PID $($portOwner.OwningProcess). Stop that process before installing this service."
    }
}

$existingPlugin = Join-Path $PluginDirectory $PluginFolderName
if (Test-Path -LiteralPath $existingPlugin) {
    $stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
    Move-Item -LiteralPath $existingPlugin -Destination "$existingPlugin.backup-$stamp"
}

if (Get-Service -Name $ServiceName -ErrorAction SilentlyContinue) {
    $nssmInstalled = Join-Path $InstallRoot 'nssm.exe'
    if (Test-Path -LiteralPath $nssmInstalled) {
        & $nssmInstalled stop $ServiceName | Out-Null
        & $nssmInstalled remove $ServiceName confirm | Out-Null
    } else {
        throw "Service $ServiceName already exists but its NSSM installation was not found; remove it before continuing."
    }
}

New-Item -ItemType Directory -Path $InstallRoot -Force | Out-Null
New-Item -ItemType Directory -Path (Join-Path $InstallRoot 'dist') -Force | Out-Null
New-Item -ItemType Directory -Path (Join-Path $InstallRoot 'logs') -Force | Out-Null
$pythonDir = Join-Path $InstallRoot 'Python'
New-Item -ItemType Directory -Path $pythonDir -Force | Out-Null
Expand-Archive -LiteralPath $pythonArchive -DestinationPath $pythonDir -Force
$PythonExe = Join-Path $pythonDir 'python.exe'
if (-not (Test-Path -LiteralPath $PythonExe -PathType Leaf)) { throw 'The bundled Python runtime did not extract correctly.' }
$pythonVersion = & $PythonExe -c 'import sys; print(sys.version_info[0] * 100 + sys.version_info[1])'
if ($LASTEXITCODE -ne 0 -or [int]$pythonVersion -lt 310) { throw 'The bundled Python runtime failed its version check.' }
Copy-Item -LiteralPath $serverSource -Destination (Join-Path $InstallRoot 'server.py') -Force
Copy-Item -LiteralPath $nssmSource -Destination (Join-Path $InstallRoot 'nssm.exe') -Force
Copy-Item -Path (Join-Path $distSource '*') -Destination (Join-Path $InstallRoot 'dist') -Recurse -Force
Copy-Item -LiteralPath $pluginSource -Destination $PluginDirectory -Recurse

if (-not (Test-Path -LiteralPath (Join-Path $InstallRoot 'environment-backup.json'))) {
    $previousEnvironment = [ordered]@{
        GERBER2PNG_SERVER_ROOT = [Environment]::GetEnvironmentVariable('GERBER2PNG_SERVER_ROOT', 'Machine')
        GERBER2PNG_PYTHON = [Environment]::GetEnvironmentVariable('GERBER2PNG_PYTHON', 'Machine')
    }
    $previousEnvironment | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $InstallRoot 'environment-backup.json') -Encoding UTF8
}
[Environment]::SetEnvironmentVariable('GERBER2PNG_SERVER_ROOT', $InstallRoot, 'Machine')
[Environment]::SetEnvironmentVariable('GERBER2PNG_PYTHON', $PythonExe, 'Machine')

$nssm = Join-Path $InstallRoot 'nssm.exe'
& $nssm install $ServiceName $PythonExe (Join-Path $InstallRoot 'server.py')
if ($LASTEXITCODE -ne 0) { throw 'NSSM could not register the local service.' }
& $nssm set $ServiceName AppDirectory $InstallRoot
& $nssm set $ServiceName Start SERVICE_AUTO_START
& $nssm set $ServiceName AppEnvironmentExtra "GERBER2PNG_SERVER_ROOT=$InstallRoot" "GERBER2PNG_PYTHON=$PythonExe" "PATH=$pythonDir;$env:SystemRoot\System32;$env:SystemRoot"
& $nssm set $ServiceName AppStdout (Join-Path $InstallRoot 'logs\service-out.log')
& $nssm set $ServiceName AppStderr (Join-Path $InstallRoot 'logs\service-error.log')
& $nssm set $ServiceName AppRotateFiles 1
& $nssm set $ServiceName AppRotateOnline 1
& $nssm set $ServiceName AppRotateBytes 1048576
& $nssm set $ServiceName AppExit Default Restart
& $nssm start $ServiceName
if ($LASTEXITCODE -ne 0) { throw 'The Gerber2PNG service did not start. See service-error.log.' }

$deadline = (Get-Date).AddSeconds(20)
$ready = $false
while ((Get-Date) -lt $deadline) {
    try {
        $response = Invoke-WebRequest -Uri 'http://127.0.0.1:4172/' -TimeoutSec 2 -UseBasicParsing
        if ($response.StatusCode -eq 200) { $ready = $true; break }
    } catch { Start-Sleep -Milliseconds 500 }
}
if (-not $ready) { throw "Service installed but did not answer on port 4172. Check $InstallRoot\logs\service-error.log." }

Write-Host "Gerber2PNG local service installed and listening at http://127.0.0.1:4172/" -ForegroundColor Green
Write-Host "KiCad plugin installed to $PluginDirectory\$PluginFolderName"
Write-Host 'Restart KiCad before using the plugin.'
