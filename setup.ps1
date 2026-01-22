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

    Write-Step "Installing Python for current user (no admin required)..."
    Write-Host "This may take 2-5 minutes. Please wait..." -ForegroundColor Yellow
    Write-Host ""
    Write-Host "    [" -NoNewline

    # Show a simple progress animation in background
    $job = Start-Job -ScriptBlock {
        while ($true) {
            Write-Host "." -NoNewline
            Start-Sleep -Seconds 3
        }
    }

    # Per-user install - NO admin required
    # InstallAllUsers=0 means current user only
    # DefaultJustForMeTargetDir sets the install location
    $userPythonPath = "$env:LOCALAPPDATA\Programs\Python\Python312"
    $installArgs = @(
        "/quiet",
        "InstallAllUsers=0",
        "PrependPath=1",
        "Include_launcher=1",
        "Include_pip=1",
        "DefaultJustForMeTargetDir=`"$userPythonPath`""
    )

    # Run WITHOUT elevation (no -Verb RunAs)
    $process = Start-Process -FilePath $PythonInstallerPath -ArgumentList $installArgs -Wait -PassThru

    # Stop progress animation
    Stop-Job $job -ErrorAction SilentlyContinue
    Remove-Job $job -Force -ErrorAction SilentlyContinue
    Write-Host "] Done!" -ForegroundColor Green

    if ($process.ExitCode -ne 0) {
        Write-Host "ERROR: Python installation failed with exit code $($process.ExitCode)" -ForegroundColor Red
        Write-Host "Please install Python manually from: https://www.python.org/downloads/" -ForegroundColor Yellow
        exit 1
    }

    # Clean up installer
    Remove-Item $PythonInstallerPath -Force -ErrorAction SilentlyContinue

    # Refresh PATH for current session
    $env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path", "User")

    # Also add Python directly to current session PATH
    $env:Path = "$userPythonPath;$userPythonPath\Scripts;$env:Path"

    Write-Success "Python installed successfully to: $userPythonPath"
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
        # Per-user install - no admin required
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
        # Check if .env exists
        $envFile = Join-Path $scriptDir ".env"
        $envExists = Test-Path $envFile

        Write-Success @"

============================================================
            Setup Complete!
============================================================
"@

        if (-not $envExists) {
            Write-Host @"

------------------------------------------------------------
NEXT STEP: Configure Salesforce Connection
------------------------------------------------------------

You need to create a .env file with your Salesforce credentials.

1. In the sfdump folder, create a new file called:  .env
   (Note: The filename starts with a dot)

2. Open it with Notepad and paste these lines:

   SF_CLIENT_ID=your_consumer_key_here
   SF_CLIENT_SECRET=your_consumer_secret_here
   SF_HOST=login.salesforce.com
   SF_USERNAME=your.email@company.com
   SF_PASSWORD=your_password_here

3. Replace the placeholder values with your actual Salesforce
   Connected App credentials.

Need help getting these values? Ask your Salesforce admin for:
  - Consumer Key (SF_CLIENT_ID)
  - Consumer Secret (SF_CLIENT_SECRET)
  - Your Salesforce username and password

"@ -ForegroundColor Yellow

            # Offer to create template
            $createEnv = Read-Host "Would you like me to create a template .env file for you? (Y/n)"
            if ($createEnv -eq "" -or $createEnv -match "^[Yy]") {
                $envTemplate = @"
# Salesforce Connection Settings
# Replace the values below with your actual credentials

SF_CLIENT_ID=paste_your_consumer_key_here
SF_CLIENT_SECRET=paste_your_consumer_secret_here
SF_HOST=login.salesforce.com
SF_USERNAME=your.email@company.com
SF_PASSWORD=your_password_and_security_token

# Optional: API version (default is v62.0)
# SF_API_VERSION=v62.0
"@
                $envTemplate | Out-File -FilePath $envFile -Encoding UTF8
                Write-Success "Created template .env file at: $envFile"
                Write-Host "Open this file in Notepad and fill in your credentials." -ForegroundColor Cyan

                # Try to open in notepad
                $openNow = Read-Host "Open .env in Notepad now? (Y/n)"
                if ($openNow -eq "" -or $openNow -match "^[Yy]") {
                    Start-Process notepad.exe $envFile
                }
            }
        } else {
            Write-Host ".env file found - you're ready to go!" -ForegroundColor Green
        }

        Write-Host @"

------------------------------------------------------------
Available Commands
------------------------------------------------------------

    sfdump --help         Show all available commands
    sfdump login          Test Salesforce connection
    sfdump files          Export Attachments/ContentVersions
    sfdump build-db       Build searchable SQLite database
    sfdump db-viewer      Launch the web viewer

"@ -ForegroundColor Cyan

    } else {
        throw "pip install failed"
    }
} catch {
    Write-Host "ERROR: Installation failed. Error: $_" -ForegroundColor Red
    exit 1
} finally {
    Pop-Location
}
