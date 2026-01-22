<#
.SYNOPSIS
    Bootstrap installer for sfdump - downloads and installs from GitHub.
.DESCRIPTION
    This script can be run directly from the internet to install sfdump:

    One-liner installation (paste into PowerShell):
        irm https://raw.githubusercontent.com/ksteptoe/sfdump/main/bootstrap.ps1 | iex

    Or download and run:
        1. Save this file as bootstrap.ps1
        2. Right-click > Run with PowerShell

.NOTES
    - Downloads the latest version from GitHub
    - Installs to user's home directory (no admin required)
    - Automatically runs the setup wizard
#>

$ErrorActionPreference = "Stop"

# Configuration
$GitHubRepo = "ksteptoe/sfdump"
$Branch = "main"
$InstallDir = "$env:USERPROFILE\sfdump"

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

This will download and install sfdump from GitHub.

  Source:  https://github.com/$GitHubRepo
  Install: $InstallDir

"@

# Check if already installed
if (Test-Path "$InstallDir\setup.ps1") {
    Write-Host "sfdump is already installed at: $InstallDir" -ForegroundColor Yellow
    Write-Host ""
    $choice = Read-Host "Reinstall/update? (Y/n)"
    if ($choice -notmatch "^[Yy]?$") {
        Write-Host "`nTo run the existing installer:"
        Write-Host "  cd `"$InstallDir`"" -ForegroundColor White
        Write-Host "  .\install.bat" -ForegroundColor White
        exit 0
    }
}

$continue = Read-Host "Continue with installation? (Y/n)"
if ($continue -notmatch "^[Yy]?$") {
    Write-Host "Installation cancelled."
    exit 0
}

# Download
Write-Step "Downloading sfdump from GitHub..."

$zipUrl = "https://github.com/$GitHubRepo/archive/refs/heads/$Branch.zip"
$zipPath = "$env:TEMP\sfdump-download.zip"
$extractPath = "$env:TEMP\sfdump-extract"

try {
    # Ensure TLS 1.2 for GitHub
    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

    # Download with progress
    Write-Host "    Downloading" -NoNewline

    $webClient = New-Object System.Net.WebClient
    $downloadComplete = $false

    # Simple progress indicator
    $timer = [System.Diagnostics.Stopwatch]::StartNew()

    Register-ObjectEvent -InputObject $webClient -EventName DownloadProgressChanged -Action {
        if ($timer.ElapsedMilliseconds -gt 500) {
            Write-Host "." -NoNewline
            $timer.Restart()
        }
    } | Out-Null

    $webClient.DownloadFile($zipUrl, $zipPath)

    Write-Host " Done!" -ForegroundColor Green

} catch {
    Write-Err "`nERROR: Failed to download from GitHub."
    Write-Host "Please check your internet connection and try again."
    Write-Host "`nAlternatively, download manually from:"
    Write-Host "  https://github.com/$GitHubRepo/archive/refs/heads/$Branch.zip" -ForegroundColor Cyan
    exit 1
}

# Extract
Write-Step "Extracting files..."

try {
    # Clean up any previous extract
    if (Test-Path $extractPath) {
        Remove-Item $extractPath -Recurse -Force
    }

    # Extract zip
    Expand-Archive -Path $zipPath -DestinationPath $extractPath -Force

    # Find the extracted folder (GitHub adds branch name suffix)
    $extractedFolder = Get-ChildItem $extractPath | Select-Object -First 1

    if (-not $extractedFolder) {
        throw "No files found in downloaded archive"
    }

    # Create install directory if needed
    if (-not (Test-Path $InstallDir)) {
        New-Item -ItemType Directory -Path $InstallDir -Force | Out-Null
    }

    # Copy files to install location
    Write-Host "    Installing to: $InstallDir"
    Copy-Item -Path "$($extractedFolder.FullName)\*" -Destination $InstallDir -Recurse -Force

    Write-Success "    Files extracted successfully!"

} catch {
    Write-Err "ERROR: Failed to extract files."
    Write-Host $_.Exception.Message
    exit 1
} finally {
    # Clean up temp files
    Remove-Item $zipPath -Force -ErrorAction SilentlyContinue
    Remove-Item $extractPath -Recurse -Force -ErrorAction SilentlyContinue
}

# Run the installer
Write-Step "Launching setup wizard..."
Write-Host ""

Push-Location $InstallDir
try {
    # Run the PowerShell setup script
    & "$InstallDir\setup.ps1"
} finally {
    Pop-Location
}
