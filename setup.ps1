<#
.SYNOPSIS
    Windows setup script for sfdump - installs Python and project dependencies.
.DESCRIPTION
    This script handles the complete setup for non-technical users:
    1. Checks if Python 3.12+ is installed
    2. Downloads and installs Python if missing
    3. Installs sfdump and all dependencies
.NOTES
    Run from PowerShell: .\setup.ps1
    Or right-click and "Run with PowerShell"
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

function Write-Warning {
    param([string]$Message)
    Write-Host $Message -ForegroundColor Yellow
}

function Test-PythonInstalled {
    # Check common Python locations (skip WindowsApps stub)
    $pythonPaths = @(
        "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe",
        "$env:LOCALAPPDATA\Programs\Python\Python313\python.exe",
        "C:\Python312\python.exe",
        "C:\Python313\python.exe",
        "$env:ProgramFiles\Python312\python.exe",
        "$env:ProgramFiles\Python313\python.exe"
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
            return "py"
        }
    } catch {}

    # Try python but exclude WindowsApps
    try {
        $pythonPath = (Get-Command python -ErrorAction SilentlyContinue).Source
        if ($pythonPath -and -not ($pythonPath -like "*WindowsApps*")) {
            # Verify it actually works
            $version = & python --version 2>&1
            if ($version -match "Python (\d+\.\d+\.\d+)") {
                return $pythonPath
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
        Invoke-WebRequest -Uri $PythonInstallerUrl -OutFile $PythonInstallerPath -UseBasicParsing
    } catch {
        Write-Host "ERROR: Failed to download Python installer." -ForegroundColor Red
        Write-Host "Please download Python manually from: https://www.python.org/downloads/" -ForegroundColor Yellow
        Write-Host "IMPORTANT: Check 'Add Python to PATH' during installation!" -ForegroundColor Yellow
        exit 1
    }

    Write-Step "Installing Python (this may take a few minutes)..."
    Write-Host "A security prompt may appear - please click 'Yes' to allow installation." -ForegroundColor Yellow

    # Install Python with PATH enabled
    $installArgs = @(
        "/quiet",
        "InstallAllUsers=0",
        "PrependPath=1",
        "Include_launcher=1",
        "Include_pip=1"
    )

    Start-Process -FilePath $PythonInstallerPath -ArgumentList $installArgs -Wait -Verb RunAs

    # Clean up installer
    Remove-Item $PythonInstallerPath -Force -ErrorAction SilentlyContinue

    # Refresh PATH
    $env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path", "User")

    Write-Success "Python installed successfully!"
}

function Disable-WindowsStoreAlias {
    Write-Step "Disabling Microsoft Store Python alias..."
    Write-Host "This prevents the 'Python not found' error from Windows Store redirect." -ForegroundColor Gray

    # The aliases are in WindowsApps, we'll just inform the user
    Write-Warning @"

To disable the Microsoft Store Python alias manually:
1. Open Windows Settings (Win + I)
2. Go to: Apps > Advanced app settings > App execution aliases
3. Turn OFF 'python.exe' and 'python3.exe' aliases

"@
}

# ============================================================================
# Main Script
# ============================================================================

Write-Host @"
============================================================
             sfdump Windows Setup Script
============================================================
"@ -ForegroundColor Cyan

# Check for admin rights for Python installation
$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)

Write-Step "Checking Python installation..."

$pythonPath = Test-PythonInstalled

if ($pythonPath) {
    $version = Get-PythonVersion $pythonPath
    Write-Host "Found Python $version at: $pythonPath"

    if ($version -lt $MinPythonVersion) {
        Write-Warning "Python $MinPythonVersion or higher is required. Found: $version"
        Write-Host "Installing newer Python version..."
        Install-Python
        $pythonPath = Test-PythonInstalled
    } else {
        Write-Success "Python version OK!"
    }
} else {
    Write-Warning "Python not found on this system."
    Disable-WindowsStoreAlias

    $response = Read-Host "Would you like to install Python automatically? (Y/n)"
    if ($response -eq "" -or $response -match "^[Yy]") {
        if (-not $isAdmin) {
            Write-Warning "Installing Python requires administrator privileges."
            Write-Host "Please run this script as Administrator, or install Python manually." -ForegroundColor Yellow
            Write-Host "Download from: https://www.python.org/downloads/" -ForegroundColor Cyan
            Write-Host "IMPORTANT: Check 'Add Python to PATH' during installation!" -ForegroundColor Yellow
            exit 1
        }
        Install-Python
        $pythonPath = Test-PythonInstalled
    } else {
        Write-Host "Please install Python 3.12+ from: https://www.python.org/downloads/" -ForegroundColor Cyan
        Write-Host "IMPORTANT: Check 'Add Python to PATH' during installation!" -ForegroundColor Yellow
        exit 1
    }
}

# Determine the python command to use
if ($pythonPath -eq "py") {
    $pythonCmd = "py"
} elseif (Test-Path $pythonPath) {
    $pythonCmd = $pythonPath
} else {
    $pythonCmd = "python"
}

Write-Step "Upgrading pip..."
& $pythonCmd -m pip install --upgrade pip setuptools wheel 2>&1 | Out-Null

Write-Step "Installing sfdump and dependencies..."
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Push-Location $scriptDir

try {
    & $pythonCmd -m pip install -e ".[dev]"

    if ($LASTEXITCODE -eq 0) {
        Write-Success @"

============================================================
            Setup Complete!
============================================================

You can now use sfdump from the command line:

    sfdump --help

Or run specific commands:

    sfdump login          # Authenticate with Salesforce
    sfdump files          # Export files
    sfdump build-db       # Build SQLite database
    sfdump db-viewer      # Launch web viewer

"@
    } else {
        throw "pip install failed"
    }
} catch {
    Write-Host "ERROR: Installation failed. Error: $_" -ForegroundColor Red
    exit 1
} finally {
    Pop-Location
}
