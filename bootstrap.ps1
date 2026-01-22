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
    - Downloads the latest RELEASE from GitHub (stable, tested version)
    - Falls back to main branch if no releases exist
    - Installs to user's home directory (no admin required)
    - Automatically runs the setup wizard
#>

$ErrorActionPreference = "Stop"

# Configuration
$GitHubRepo = "ksteptoe/sfdump"
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
Write-Step "Checking for latest release..."

$zipPath = "$env:TEMP\sfdump-download.zip"
$extractPath = "$env:TEMP\sfdump-extract"
$zipUrl = $null
$version = "main"

try {
    # Ensure TLS 1.2 for GitHub
    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

    # Try to get latest release from GitHub API
    $releaseApiUrl = "https://api.github.com/repos/$GitHubRepo/releases/latest"

    try {
        $headers = @{ "User-Agent" = "sfdump-bootstrap" }
        $release = Invoke-RestMethod -Uri $releaseApiUrl -Headers $headers -ErrorAction Stop

        # Look for the sfdump ZIP in release assets
        $asset = $release.assets | Where-Object { $_.name -match "^sfdump-.*\.zip$" } | Select-Object -First 1

        if ($asset) {
            $zipUrl = $asset.browser_download_url
            $version = $release.tag_name
            Write-Host "    Found release: $version" -ForegroundColor Green
        } else {
            Write-Host "    Release found but no ZIP asset, using source archive" -ForegroundColor Yellow
            $zipUrl = $release.zipball_url
            $version = $release.tag_name
        }
    } catch {
        Write-Host "    No releases found, using main branch" -ForegroundColor Yellow
        $zipUrl = "https://github.com/$GitHubRepo/archive/refs/heads/main.zip"
        $version = "main"
    }

    Write-Step "Downloading sfdump ($version)..."
    Write-Host "    Source: $zipUrl"
    Write-Host "    Downloading" -NoNewline

    $webClient = New-Object System.Net.WebClient
    $webClient.Headers.Add("User-Agent", "sfdump-bootstrap")

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
    Write-Host "  https://github.com/$GitHubRepo/releases" -ForegroundColor Cyan
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
} catch {
    if ($_.Exception.Message -match "cannot be loaded because running scripts is disabled") {
        Write-Err "`nERROR: PowerShell execution policy is blocking the setup script."
        Write-Host ""
        Write-Host "Run the setup script with bypass (recommended):" -ForegroundColor Yellow
        Write-Host ""
        Write-Host "  Open PowerShell and run:" -ForegroundColor White
        Write-Host "  powershell -ExecutionPolicy Bypass -File `"$InstallDir\setup.ps1`"" -ForegroundColor Cyan
        Write-Host ""
        Write-Host "Or use the batch file alternative:" -ForegroundColor Yellow
        Write-Host "  $InstallDir\install.bat" -ForegroundColor Cyan
        Write-Host ""
    } else {
        throw
    }
} finally {
    Pop-Location
}
