<#
.SYNOPSIS
    Bootstrap installer for sfdump - installs Python if needed and installs sfdump from PyPI.
.DESCRIPTION
    This script can be run directly from the internet to install sfdump:

    One-liner installation (paste into PowerShell):
        irm https://raw.githubusercontent.com/ksteptoe/sfdump/main/bootstrap.ps1 | iex

    Or download and run:
        1. Save this file as bootstrap.ps1
        2. Right-click > Run with PowerShell

.NOTES
    - Installs Python if missing (no admin required)
    - Installs sfdump from PyPI via pip
    - No admin required
    - After install, run `sf setup` to configure Salesforce credentials
#>

$ErrorActionPreference = "Stop"

$MinPythonVersion = [Version]"3.12.0"
$PythonInstallerUrl = "https://www.python.org/ftp/python/3.12.4/python-3.12.4-amd64.exe"
$PythonInstallerPath = "$env:TEMP\python-installer.exe"

function Write-Step {
    param([string]$Message)
    Write-Host "`n>>> $Message" -ForegroundColor Cyan
}

function Write-Success {
    param([string]$Message)
    Write-Host $Message -ForegroundColor Green
}

function Write-Err {
    param([string]$Message)
    Write-Host $Message -ForegroundColor Red
}

# ============================================================================
# Python Detection & Installation
# ============================================================================

function Test-PythonInstalled {
    # Check PATH first (important for CI where Python is set up via actions/setup-python)
    try {
        $pythonPath = (Get-Command python -ErrorAction SilentlyContinue).Source
        if ($pythonPath -and -not ($pythonPath -like "*WindowsApps*")) {
            $version = & python --version 2>&1
            if ($version -match "Python (\d+\.\d+\.\d+)") {
                return $pythonPath
            }
        }
    } catch {}

    # Check common Python locations (skip WindowsApps stub)
    $pythonPaths = @(
        "$env:LOCALAPPDATA\Programs\Python\Python313\python.exe",
        "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe",
        "C:\Python313\python.exe",
        "C:\Python312\python.exe",
        "$env:ProgramFiles\Python313\python.exe",
        "$env:ProgramFiles\Python312\python.exe"
    )

    foreach ($path in $pythonPaths) {
        if (Test-Path $path) {
            return $path
        }
    }

    # Try py launcher
    try {
        $pyPath = (Get-Command py -ErrorAction SilentlyContinue).Source
        if ($pyPath -and -not ($pyPath -like "*WindowsApps*")) {
            $pyVersion = & py --version 2>&1
            if ($LASTEXITCODE -eq 0 -and $pyVersion -match "Python \d+\.\d+") {
                return "py"
            }
        }
    } catch {}

    return $null
}

function Get-PythonVersion {
    param([string]$PythonPath)
    try {
        if ($PythonPath -eq "py") {
            $version = & py --version 2>&1
        } else {
            $version = & $PythonPath --version 2>&1
        }
        if ($version -match "Python (\d+\.\d+\.\d+)") {
            return [Version]$Matches[1]
        }
    } catch {}
    return $null
}

function Install-Python {
    Write-Step "Downloading Python installer..."

    try {
        [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
        $webClient = New-Object System.Net.WebClient
        $webClient.DownloadFile($PythonInstallerUrl, $PythonInstallerPath)
    } catch {
        Write-Err "ERROR: Failed to download Python installer."
        Write-Host "Please download Python manually from: https://www.python.org/downloads/" -ForegroundColor Yellow
        Write-Host "IMPORTANT: Check 'Add Python to PATH' during installation!" -ForegroundColor Yellow
        return $false
    }

    Write-Step "Installing Python for current user (no admin required)..."
    Write-Host "This takes 2-5 minutes. Please wait..." -ForegroundColor Yellow
    Write-Host ""
    Write-Host "    Installing" -NoNewline

    $userPythonPath = "$env:LOCALAPPDATA\Programs\Python\Python312"
    $installArgs = @(
        "/quiet",
        "InstallAllUsers=0",
        "PrependPath=1",
        "Include_launcher=1",
        "Include_pip=1",
        "DefaultJustForMeTargetDir=`"$userPythonPath`""
    )

    $process = Start-Process -FilePath $PythonInstallerPath -ArgumentList $installArgs -PassThru

    while (-not $process.HasExited) {
        Write-Host "." -NoNewline
        Start-Sleep -Seconds 2
    }

    Write-Host " Done!" -ForegroundColor Green

    Remove-Item $PythonInstallerPath -Force -ErrorAction SilentlyContinue

    if ($process.ExitCode -ne 0) {
        Write-Err "ERROR: Python installation failed with exit code $($process.ExitCode)"
        Write-Host "Please install Python manually from: https://www.python.org/downloads/" -ForegroundColor Yellow
        return $false
    }

    # Refresh PATH
    $env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path", "User")
    $env:Path = "$userPythonPath;$userPythonPath\Scripts;$env:Path"

    Write-Success "Python installed successfully!"
    return $true
}

# ============================================================================
# Main
# ============================================================================

Clear-Host
Write-Host @"
============================================================
           sfdump - Salesforce Data Export Tool
                  Bootstrap Installer
============================================================
"@ -ForegroundColor Cyan

Write-Host @"

This will install sfdump from PyPI (https://pypi.org/project/sfdump/).

"@

$continue = Read-Host "Continue with installation? (Y/n)"
if ($continue -notmatch "^[Yy]?$") {
    Write-Host "Installation cancelled."
    exit 0
}

# --- Check for Python ---
Write-Step "Checking for Python..."

$pythonPath = Test-PythonInstalled

if (-not $pythonPath) {
    Write-Host "Python not found." -ForegroundColor Yellow
    Write-Host ""

    Write-Host @"
NOTE: If you see 'Python was not found' errors, Windows may have
a Microsoft Store redirect enabled. The installer will work around this.

"@ -ForegroundColor Gray

    $installPython = Read-Host "Install Python now? (Y/n)"
    if ($installPython -eq "" -or $installPython -match "^[Yy]") {
        if (-not (Install-Python)) {
            exit 1
        }
        $pythonPath = Test-PythonInstalled
        if (-not $pythonPath) {
            Write-Err "Python still not found after installation."
            exit 1
        }
    } else {
        Write-Host "Please install Python 3.12+ manually from: https://www.python.org/downloads/"
        exit 1
    }
}

$pyVersion = Get-PythonVersion $pythonPath
if ($pyVersion -lt $MinPythonVersion) {
    Write-Err "Python $pyVersion is too old. sfdump requires Python $MinPythonVersion or newer."
    Write-Host "Please upgrade Python from: https://www.python.org/downloads/"
    exit 1
}

Write-Success "  Python $pyVersion found"

# --- Install sfdump from PyPI ---
Write-Step "Installing sfdump from PyPI..."

if ($pythonPath -eq "py") {
    $pythonCmd = "py"
} else {
    $pythonCmd = $pythonPath
}

try {
    & $pythonCmd -m pip install --upgrade pip 2>&1 | Out-Null
    & $pythonCmd -m pip install sfdump

    if ($LASTEXITCODE -ne 0) { throw "pip install failed" }
} catch {
    Write-Err "`nERROR: Failed to install sfdump."
    Write-Host "Please check your internet connection and try again."
    Write-Host ""
    Write-Host "You can also try installing manually:" -ForegroundColor Yellow
    Write-Host "  pip install sfdump" -ForegroundColor Cyan
    exit 1
}

# --- Verify installation ---
Write-Step "Verifying installation..."

try {
    $version = & $pythonCmd -m sfdump --version 2>&1
    if ($version) {
        Write-Success "  sfdump $version installed successfully!"
    } else {
        # Try the sfdump command directly (may be in PATH)
        $version = & sfdump --version 2>&1
        Write-Success "  sfdump $version installed successfully!"
    }
} catch {
    Write-Success "  sfdump installed (could not determine version)"
}

# --- Done ---
Write-Host @"

============================================================
            Installation Complete!
============================================================

NEXT STEPS
----------

1. Configure your Salesforce credentials:

    sf setup

2. Test your connection:

    sf test

3. Export your Salesforce data:

    sf dump

4. Browse your data:

    sf view

UPGRADING
---------

To upgrade sfdump later, run:

    pip install --upgrade sfdump

"@ -ForegroundColor Cyan
