# Installs the latest Azure DevOps MCP extension into Claude Desktop (Windows).
# Usage (PowerShell):
#   irm https://raw.githubusercontent.com/ms31376/ado-mcp-server/main/install.ps1 | iex

$ErrorActionPreference = 'Stop'
$Repo = 'ms31376/ado-mcp-server'
$Url  = "https://github.com/$Repo/releases/latest/download/ado-mcp-server.mcpb"
$Dir  = Join-Path $env:USERPROFILE 'Downloads'
if (-not (Test-Path $Dir)) { $Dir = $env:TEMP }
$File = Join-Path $Dir 'ado-mcp-server.mcpb'

Write-Host ''
Write-Host 'Azure DevOps MCP - installer for Claude Desktop' -ForegroundColor Cyan
Write-Host ''

# 1. Download the latest release
try {
    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
    Write-Host "Downloading latest version..."
    Invoke-WebRequest -Uri $Url -OutFile $File -UseBasicParsing
    Write-Host "Saved to: $File" -ForegroundColor Green
} catch {
    Write-Host "Download failed: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host "Download it manually from: https://github.com/$Repo/releases/latest"
    return
}

# 2. Open it with Claude Desktop
$opened = $false
try {
    Start-Process -FilePath $File -ErrorAction Stop
    $opened = $true
    Write-Host 'Opening the installer in Claude Desktop...'
} catch { }

if (-not $opened) {
    $claude = (Test-Path "$env:LOCALAPPDATA\AnthropicClaude") -or
              (Get-AppxPackage -Name '*Claude*' -ErrorAction SilentlyContinue)
    if (-not $claude) {
        Write-Host 'Claude Desktop does not seem to be installed.' -ForegroundColor Yellow
        Write-Host 'Install it from https://claude.ai/download and run this command again.'
        return
    }
    Write-Host 'Windows could not open the file automatically. Install it from Claude Desktop:' -ForegroundColor Yellow
    Write-Host '  Settings > Customize > Connectors > Add > install extension (choose the file below)'
    Write-Host '  or, with Developer Mode on: menu > Developer > Extensions > install from file'
    Write-Host "  File: $File"
    Start-Process explorer.exe "/select,`"$File`""
}

Write-Host ''
Write-Host 'Next, in the install form:' -ForegroundColor Cyan
Write-Host '  - Server URL: https://server/Collection  or  https://dev.azure.com/YourOrg'
Write-Host '  - Personal Access Token: create one in Azure DevOps > User settings > Personal access tokens'
Write-Host '  - Access level: read (recommended to start)'
Write-Host '  - Internal server and timeouts? turn on "Ignore system proxy"'
Write-Host ''