<#
.SYNOPSIS
    Windows setup script for sfdump - installs, updates, or uninstalls.
.DESCRIPTION
    Menu-driven installer for non-technical users:
    - Checks disk space requirements (40GB recommended)
    - Installs Python if missing (no admin required)
    - Installs/updates sfdump and dependencies into a virtual environment
    - Configures .env file
    - Clean uninstall option
.PARAMETER Install
    Non-interactive install mode. Installs sfdump without prompts.
    Requires Python to already be installed.
.PARAMETER SkipEnv
    Skip .env file configuration (useful for CI).
.NOTES
    Run from PowerShell: .\setup.ps1
    Or double-click install.bat

    For CI/automated installs: .\setup.ps1 -Install -SkipEnv
#>

param(
    [switch]$Install,
    [switch]$SkipEnv
)

$ErrorActionPreference = "Stop"
$MinPythonVersion = [Version]"3.12.0"
$PythonInstallerUrl = "https://www.python.org/ftp/python/3.12.4/python-3.12.4-amd64.exe"
$PythonInstallerPath = "$env:TEMP\python-installer.exe"
$RequiredDiskSpaceGB = 40
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$GitHubRepo = "ksteptoe/sfdump"

# ============================================================================
# Helper Functions
# ============================================================================

function Write-Step {
    param([string]$Message)
    Write-Host "`n>>> $Message" -ForegroundColor Cyan
}

function Write-Success {
    param([string]$Message)
    Write-Host $Message -ForegroundColor Green
}

function Write-Warn {
    param([string]$Message)
    Write-Host $Message -ForegroundColor Yellow
}

function Write-Err {
    param([string]$Message)
    Write-Host $Message -ForegroundColor Red
}

function Get-CurrentVersion {
    $venvPython = Join-Path $ScriptDir ".venv\Scripts\python.exe"
    if (-not (Test-Path $venvPython)) { return $null }

    try {
        $ver = & $venvPython -c "import sfdump; print(sfdump.__version__)" 2>&1
        if ($LASTEXITCODE -eq 0 -and $ver -match "^\d+\.\d+") {
            return $ver.Trim()
        }
    } catch {}
    return $null
}

function Get-LatestRelease {
    try {
        [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
        $pypiUrl = "https://pypi.org/pypi/sfdump/json"
        $response = Invoke-RestMethod -Uri $pypiUrl -ErrorAction Stop

        $version = $response.info.version

        return @{ Version = $version }
    } catch {
        return $null
    }
}

function Update-Sfdump {
    Show-Banner

    Write-Step "Checking for updates..."

    $currentVersion = Get-CurrentVersion
    $latest = Get-LatestRelease

    if ($currentVersion) {
        Write-Host "  Installed: $currentVersion"
    } else {
        Write-Host "  Installed: (unknown version)"
    }

    if (-not $latest) {
        Write-Err "  Could not check for updates (no internet?)"
        Write-Host ""
        $reinstall = Read-Host "Reinstall from local source files instead? (Y/n)"
        if ($reinstall -eq "" -or $reinstall -match "^[Yy]") {
            Install-Sfdump | Out-Null
        }
        return
    }

    Write-Host "  Latest:    $($latest.Version)"
    Write-Host ""

    # Compare versions — strip any dev/post suffix for a clean comparison
    $cleanCurrent = ($currentVersion -split '[\.\+]dev|\.post')[0]

    if ($currentVersion -and $cleanCurrent -eq $latest.Version) {
        Write-Success "  Already up to date!"
        Write-Host ""
        $reinstall = Read-Host "Reinstall anyway? (y/N)"
        if ($reinstall -notmatch "^[Yy]") {
            return
        }
    }

    Write-Step "Upgrading sfdump via pip..."

    $venvPython = Join-Path $ScriptDir ".venv\Scripts\python.exe"
    if (-not (Test-Path $venvPython)) {
        Write-Err "  Virtual environment not found. Use option 1 for a fresh install."
        return
    }

    try {
        & $venvPython -m pip install --upgrade sfdump
        if ($LASTEXITCODE -ne 0) { throw "pip install failed" }
        $newVersion = Get-CurrentVersion
        if ($newVersion) {
            Write-Host ""
            Write-Success "  Upgrade complete! Now running sfdump v$newVersion"
        }
    } catch {
        Write-Err "  Upgrade failed: $($_.Exception.Message)"
        Write-Host ""
        $reinstall = Read-Host "Reinstall from local source files instead? (Y/n)"
        if ($reinstall -eq "" -or $reinstall -match "^[Yy]") {
            Install-Sfdump | Out-Null
        }
    }
}

function Show-Banner {
    # Skip Clear-Host in non-interactive mode (CI) to avoid console errors
    if (-not $Install) {
        try {
            Clear-Host
        } catch {
            # Ignore errors if no console available
        }
    }
    Write-Host @"
============================================================
             sfdump - Salesforce Data Export Tool
                     Windows Installer
============================================================
"@ -ForegroundColor Cyan
}

function Get-FreeDiskSpaceGB {
    param([string]$Path = $ScriptDir)

    $drive = (Get-Item $Path).PSDrive.Name
    $disk = Get-PSDrive $drive
    return [math]::Round($disk.Free / 1GB, 1)
}

function Test-DiskSpace {
    $freeSpace = Get-FreeDiskSpaceGB
    $installDrive = (Get-Item $ScriptDir).PSDrive.Name

    Write-Host "`nDisk Space Check:" -ForegroundColor White
    Write-Host "  Drive ${installDrive}: has $freeSpace GB free"
    Write-Host "  Required: $RequiredDiskSpaceGB GB (for Salesforce file exports)"

    if ($freeSpace -lt $RequiredDiskSpaceGB) {
        Write-Host ""
        Write-Err "  WARNING: Insufficient disk space!"
        Write-Host @"

  Salesforce exports can be very large. You need at least
  $RequiredDiskSpaceGB GB of free space to safely export files.

  Options:
  1. Free up disk space and try again
  2. Move sfdump to a drive with more space
  3. Continue anyway (not recommended)

"@ -ForegroundColor Yellow

        $continue = Read-Host "Continue with installation anyway? (y/N)"
        if ($continue -notmatch "^[Yy]") {
            return $false
        }
        Write-Warn "Proceeding with limited disk space..."
    } else {
        Write-Success "  Disk space OK"
    }
    return $true
}

function Test-PythonInstalled {
    # First check PATH (important for CI where Python is set up via actions/setup-python)
    # This also handles cases where user has Python in PATH already
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

    # Try py launcher - but verify it actually has a Python installation
    try {
        $pyPath = (Get-Command py -ErrorAction SilentlyContinue).Source
        if ($pyPath -and -not ($pyPath -like "*WindowsApps*")) {
            # Verify py launcher can actually find Python
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

function Test-SfdumpInstalled {
    $pythonPath = Test-PythonInstalled
    if (-not $pythonPath) { return $false }

    try {
        if ($pythonPath -eq "py") {
            $result = & py -m pip show sfdump 2>&1
        } else {
            $result = & $pythonPath -m pip show sfdump 2>&1
        }
        return $result -match "Name: sfdump"
    } catch {
        return $false
    }
}

function Install-Python {
    Write-Step "Downloading Python installer..."

    try {
        [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

        # Download with progress
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

    # Start installation
    $process = Start-Process -FilePath $PythonInstallerPath -ArgumentList $installArgs -PassThru

    # Show progress dots while waiting
    while (-not $process.HasExited) {
        Write-Host "." -NoNewline
        Start-Sleep -Seconds 2
    }

    Write-Host " Done!" -ForegroundColor Green

    # Clean up installer
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

function Install-Sfdump {
    $pythonPath = Test-PythonInstalled

    if (-not $pythonPath) {
        Write-Err "Python not found. Cannot install sfdump."
        return $false
    }

    # Determine python command
    if ($pythonPath -eq "py") {
        $pythonCmd = "py"
    } else {
        $pythonCmd = $pythonPath
    }

    $venvDir = Join-Path $ScriptDir ".venv"
    $venvPython = Join-Path $venvDir "Scripts\python.exe"
    $venvActivate = Join-Path $venvDir "Scripts\Activate.ps1"

    # Create virtual environment if it doesn't exist
    if (-not (Test-Path $venvPython)) {
        Write-Step "Creating virtual environment..."
        & $pythonCmd -m venv $venvDir

        if ($LASTEXITCODE -ne 0) {
            Write-Err "Failed to create virtual environment."
            return $false
        }
        Write-Success "Virtual environment created at: $venvDir"
    } else {
        Write-Host "`nUsing existing virtual environment: $venvDir" -ForegroundColor Green
    }

    Write-Step "Upgrading pip in virtual environment..."
    & $venvPython -m pip install --upgrade pip setuptools wheel 2>&1 | Out-Null

    Write-Step "Installing sfdump and dependencies..."
    Write-Host "This may take a few minutes..." -ForegroundColor Gray

    Push-Location $ScriptDir
    try {
        & $venvPython -m pip install -e ".[dev]"

        if ($LASTEXITCODE -eq 0) {
            Write-Success "sfdump installed successfully!"

            # Store venv path for later use
            $script:VenvActivate = $venvActivate
            $script:VenvPython = $venvPython

            return $true
        } else {
            Write-Err "Installation failed."
            return $false
        }
    } finally {
        Pop-Location
    }
}

function Setup-EnvFile {
    $envFile = Join-Path $ScriptDir ".env"

    if (Test-Path $envFile) {
        Write-Host "`n.env file already exists." -ForegroundColor Green
        $edit = Read-Host "Would you like to edit it? (y/N)"
        if ($edit -match "^[Yy]") {
            Start-Process notepad.exe $envFile
        }
        return
    }

    Write-Host @"

------------------------------------------------------------
NEXT STEP: Configure Salesforce Connection
------------------------------------------------------------

You need a .env file with your Salesforce credentials.

To get these credentials, ask your Salesforce administrator for:

  1. Consumer Key      -> SF_CLIENT_ID
     (From a Connected App in Salesforce Setup)

  2. Consumer Secret   -> SF_CLIENT_SECRET
     (From the same Connected App)

  3. Your Salesforce instance URL -> SF_LOGIN_URL
     (e.g., https://yourcompany.my.salesforce.com)

The Connected App must be configured for OAuth Client Credentials flow.

"@ -ForegroundColor Yellow

    $createEnv = Read-Host "Create a template .env file now? (Y/n)"
    if ($createEnv -eq "" -or $createEnv -match "^[Yy]") {
        $envTemplate = @"
# ============================================================
# Salesforce Connection Settings for sfdump
# ============================================================
# Replace the placeholder values below with your actual credentials
#
# IMPORTANT: Keep this file private! Do not share or commit to git.
# ============================================================

# Authentication flow (client_credentials is recommended for automation)
SF_AUTH_FLOW=client_credentials

# Connected App credentials (get these from your Salesforce admin)
SF_CLIENT_ID=paste_your_consumer_key_here
SF_CLIENT_SECRET=paste_your_consumer_secret_here

# Your Salesforce instance URL (use test.salesforce.com for sandboxes)
SF_LOGIN_URL=https://yourcompany.my.salesforce.com

# Optional: API version (default is v60.0)
# SF_API_VERSION=v60.0
"@
        $envTemplate | Out-File -FilePath $envFile -Encoding UTF8
        Write-Success "Created template .env file"

        $openNow = Read-Host "Open .env in Notepad to fill in your credentials? (Y/n)"
        if ($openNow -eq "" -or $openNow -match "^[Yy]") {
            Start-Process notepad.exe $envFile
        }
    }
}

function Uninstall-Sfdump {
    Show-Banner
    Write-Host @"

UNINSTALL OPTIONS
-----------------

"@ -ForegroundColor Yellow

    Write-Host "What would you like to remove?`n"
    Write-Host "  [1] sfdump only (keep Python installed)"
    Write-Host "  [2] sfdump + Python (complete removal)"
    Write-Host "  [3] Cancel - go back"
    Write-Host ""

    $choice = Read-Host "Enter choice (1-3)"

    switch ($choice) {
        "1" {
            Uninstall-SfdumpOnly
        }
        "2" {
            Uninstall-SfdumpOnly
            Uninstall-Python
        }
        "3" {
            return
        }
        default {
            Write-Warn "Invalid choice"
            return
        }
    }

    Write-Host ""
    Write-Success "Uninstall complete!"
    Write-Host ""

    # Ask about data files
    Write-Host @"
NOTE: Your data files were NOT deleted:
  - .env (credentials)
  - Any exported Salesforce data
  - SQLite databases

To completely remove everything, manually delete the sfdump folder.
"@ -ForegroundColor Yellow
}

function Uninstall-SfdumpOnly {
    Write-Step "Uninstalling sfdump..."

    $pythonPath = Test-PythonInstalled
    if ($pythonPath) {
        if ($pythonPath -eq "py") {
            & py -m pip uninstall sfdump -y 2>&1 | Out-Null
        } else {
            & $pythonPath -m pip uninstall sfdump -y 2>&1 | Out-Null
        }
        Write-Success "sfdump uninstalled"
    } else {
        Write-Host "sfdump was not installed (Python not found)"
    }
}

function Uninstall-Python {
    Write-Step "Uninstalling Python..."

    $pythonPath = "$env:LOCALAPPDATA\Programs\Python\Python312"
    $uninstaller = "$pythonPath\unins000.exe"

    # Try the standard uninstaller location
    if (Test-Path $uninstaller) {
        Start-Process $uninstaller -ArgumentList "/SILENT" -Wait
        Write-Success "Python uninstalled"
    } else {
        # Try via Windows installer
        $pythonPaths = @(
            "$env:LOCALAPPDATA\Programs\Python\Python312",
            "$env:LOCALAPPDATA\Programs\Python\Python313"
        )

        $removed = $false
        foreach ($path in $pythonPaths) {
            if (Test-Path $path) {
                Write-Host "Removing Python from: $path"
                # Find and run the uninstaller from the installer cache
                $uninstallKey = Get-ChildItem "HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall" -ErrorAction SilentlyContinue |
                    Where-Object { $_.GetValue("DisplayName") -like "Python 3.1*" }

                if ($uninstallKey) {
                    $uninstallString = $uninstallKey.GetValue("UninstallString")
                    if ($uninstallString) {
                        Start-Process cmd -ArgumentList "/c `"$uninstallString`" /quiet" -Wait
                        $removed = $true
                    }
                }

                # If registry method didn't work, try direct removal
                if (-not $removed -and (Test-Path $path)) {
                    Remove-Item $path -Recurse -Force -ErrorAction SilentlyContinue
                    $removed = $true
                }
            }
        }

        if ($removed) {
            Write-Success "Python removed"
        } else {
            Write-Warn "Could not automatically remove Python."
            Write-Host "To remove manually: Settings > Apps > Installed Apps > Python 3.12"
        }
    }

    # Clean up PATH entries
    Write-Host "Cleaning up environment variables..."
    $userPath = [Environment]::GetEnvironmentVariable("Path", "User")
    $newPath = ($userPath -split ";" | Where-Object { $_ -notmatch "Python31[23]" }) -join ";"
    [Environment]::SetEnvironmentVariable("Path", $newPath, "User")
}

function Show-Menu {
    $pythonInstalled = Test-PythonInstalled
    $sfdumpInstalled = Test-SfdumpInstalled
    $envExists = Test-Path (Join-Path $ScriptDir ".env")

    Show-Banner

    # Status display
    Write-Host "`nCurrent Status:" -ForegroundColor White

    if ($pythonInstalled) {
        $pyVersion = Get-PythonVersion $pythonInstalled
        Write-Host "  [OK] Python $pyVersion installed" -ForegroundColor Green
    } else {
        Write-Host "  [--] Python not installed" -ForegroundColor Gray
    }

    if ($sfdumpInstalled) {
        $sfdumpVersion = Get-CurrentVersion
        if ($sfdumpVersion) {
            Write-Host "  [OK] sfdump v$sfdumpVersion installed" -ForegroundColor Green
        } else {
            Write-Host "  [OK] sfdump installed" -ForegroundColor Green
        }
    } else {
        Write-Host "  [--] sfdump not installed" -ForegroundColor Gray
    }

    if ($envExists) {
        Write-Host "  [OK] .env file configured" -ForegroundColor Green
    } else {
        Write-Host "  [--] .env file not found" -ForegroundColor Gray
    }

    $freeSpace = Get-FreeDiskSpaceGB
    if ($freeSpace -ge $RequiredDiskSpaceGB) {
        Write-Host "  [OK] Disk space: $freeSpace GB free" -ForegroundColor Green
    } else {
        Write-Host "  [!!] Disk space: $freeSpace GB free (need $RequiredDiskSpaceGB GB)" -ForegroundColor Yellow
    }

    # Menu options
    Write-Host "`n------------------------------------------------------------"
    Write-Host "MENU" -ForegroundColor Cyan
    Write-Host "------------------------------------------------------------`n"

    if (-not $sfdumpInstalled) {
        Write-Host "  [1] Install sfdump (fresh installation)"
    } else {
        Write-Host "  [1] Upgrade to latest version"
    }

    Write-Host "  [2] Configure .env file (Salesforce credentials)"
    Write-Host "  [3] Test connection (run sfdump login)"
    Write-Host "  [4] Uninstall"
    Write-Host "  [5] Exit"
    Write-Host ""

    return Read-Host "Enter choice (1-5)"
}

function Test-Connection {
    $pythonPath = Test-PythonInstalled
    if (-not $pythonPath) {
        Write-Err "Python not installed. Please install first."
        return
    }

    if (-not (Test-SfdumpInstalled)) {
        Write-Err "sfdump not installed. Please install first."
        return
    }

    $envFile = Join-Path $ScriptDir ".env"
    if (-not (Test-Path $envFile)) {
        Write-Err ".env file not found. Please configure credentials first."
        return
    }

    Write-Step "Testing Salesforce connection..."
    Push-Location $ScriptDir
    try {
        & sfdump login
    } finally {
        Pop-Location
    }
}

function Show-PostInstallHelp {
    $venvActivate = Join-Path $ScriptDir ".venv\Scripts\Activate.ps1"

    Write-Host @"

============================================================
            Installation Complete!
============================================================

ACTIVATE THE VIRTUAL ENVIRONMENT
--------------------------------

Before using sfdump, activate the virtual environment:

    . "$venvActivate"

Or for Command Prompt (cmd.exe):

    .venv\Scripts\activate.bat

AVAILABLE COMMANDS (after activation)
-------------------------------------

    sfdump --help         Show all available commands
    sfdump login          Test Salesforce connection
    sfdump files          Export Attachments/ContentVersions
    sfdump build-db       Build searchable SQLite database
    sfdump db-viewer      Launch the web viewer

GETTING STARTED
---------------

1. Activate the virtual environment (see above)
2. Make sure your .env file is configured with Salesforce credentials
3. Run: sfdump login
   (to verify your connection works)
4. Run: sfdump files --help
   (to see export options)

"@ -ForegroundColor Cyan
}

# ============================================================================
# Main Script
# ============================================================================

# Non-interactive install mode (for CI and automation)
if ($Install) {
    Show-Banner
    Write-Host "Running in non-interactive install mode..." -ForegroundColor Cyan

    $pythonPath = Test-PythonInstalled
    if (-not $pythonPath) {
        Write-Err "Python not found. Please install Python 3.12+ first."
        Write-Host "Download from: https://www.python.org/downloads/"
        exit 1
    }

    $version = Get-PythonVersion $pythonPath
    Write-Host "Using Python $version" -ForegroundColor Green

    if (Install-Sfdump) {
        if (-not $SkipEnv) {
            Setup-EnvFile
        }
        Show-PostInstallHelp
        Write-Success "`nInstallation complete!"
        exit 0
    } else {
        Write-Err "Installation failed."
        exit 1
    }
}

# Interactive menu mode
$running = $true

while ($running) {
    $choice = Show-Menu

    switch ($choice) {
        "1" {
            if (Test-SfdumpInstalled) {
                # Upgrade existing installation
                Update-Sfdump
            } else {
                # Fresh install
                Show-Banner

                if (-not (Test-DiskSpace)) {
                    Read-Host "`nPress Enter to continue"
                    continue
                }

                $pythonPath = Test-PythonInstalled

                if (-not $pythonPath) {
                    Write-Step "Python not found - installing..."

                    # Show info about MS Store alias
                    Write-Host @"

NOTE: If you see 'Python was not found' errors, Windows may have
a Microsoft Store redirect enabled. The installer will work around this.

"@ -ForegroundColor Gray

                    $installPython = Read-Host "Install Python now? (Y/n)"
                    if ($installPython -eq "" -or $installPython -match "^[Yy]") {
                        if (-not (Install-Python)) {
                            Read-Host "`nPress Enter to continue"
                            continue
                        }
                    } else {
                        Write-Host "Please install Python 3.12+ manually from: https://www.python.org/downloads/"
                        Read-Host "`nPress Enter to continue"
                        continue
                    }
                } else {
                    $version = Get-PythonVersion $pythonPath
                    Write-Host "`nUsing existing Python $version" -ForegroundColor Green
                }

                if (Install-Sfdump) {
                    Setup-EnvFile
                    Show-PostInstallHelp
                }
            }

            Read-Host "Press Enter to continue"
        }
        "2" {
            # Configure .env
            Show-Banner
            Setup-EnvFile
            Read-Host "`nPress Enter to continue"
        }
        "3" {
            # Test connection
            Show-Banner
            Test-Connection
            Read-Host "`nPress Enter to continue"
        }
        "4" {
            # Uninstall
            Uninstall-Sfdump
            Read-Host "`nPress Enter to continue"
        }
        "5" {
            $running = $false
            Write-Host "`nGoodbye!" -ForegroundColor Cyan
        }
        default {
            Write-Warn "Invalid choice. Please enter 1-5."
            Start-Sleep -Seconds 1
        }
    }
}
