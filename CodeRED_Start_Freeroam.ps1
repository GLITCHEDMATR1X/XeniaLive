param(
  [string]$IsoPath = ""
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root

function Get-FirstIPv4 {
  $ip = Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue |
    Where-Object {
      $_.IPAddress -notlike "127.*" -and
      $_.IPAddress -notlike "169.254.*" -and
      $_.PrefixOrigin -ne "WellKnown"
    } |
    Sort-Object InterfaceMetric, InterfaceIndex |
    Select-Object -First 1 -ExpandProperty IPAddress
  if (-not $ip) { $ip = "127.0.0.1" }
  return $ip
}

function Patch-ConfigFile([string]$Path, [string]$Ip) {
  if (-not (Test-Path $Path)) { return }
  $text = Get-Content -LiteralPath $Path -Raw

  $pairs = [ordered]@{
    'network_mode' = '3'
    'netplay_api_address' = '"http://127.0.0.1:36000/"'
    'selected_network_interface' = '"' + $Ip + '"'
    'net_logging' = 'true'
    'netplay_singleplayer_host' = 'true'
    'netplay_disable_saves' = 'false'
    'netplay_udp_bootstrap' = 'true'
    'netplay_udp_bootstrap_interval' = '120'
    'xhttp' = 'true'
    'upnp' = 'true'
    'license_mask' = '-1'
    'logged_profile_slot_0_xuid' = '"E03000004156EF97"'
    'logged_profile_slot_1_xuid' = '""'
    'logged_profile_slot_2_xuid' = '""'
    'logged_profile_slot_3_xuid' = '""'
    'apply_title_update' = 'false'
    'allow_incompatible_title_update' = 'true'
    'disable_saves' = 'false'
    'flush_log' = 'true'
    'log_file' = '"logs/xenia_codered_freeroam_ready.log"'
  }

  foreach ($k in $pairs.Keys) {
    $v = $pairs[$k]
    $pattern = "(?m)^$([regex]::Escape($k))\s*=.*$"
    if ($text -match $pattern) {
      $text = [regex]::Replace($text, $pattern, "$k = $v", 1)
    }
  }

  Set-Content -LiteralPath $Path -Value $text -Encoding UTF8
}

$ip = Get-FirstIPv4
Write-Host "[Code RED] Local IPv4 selected for XNet:" $ip

New-Item -ItemType Directory -Force -Path (Join-Path $Root "logs") | Out-Null

foreach ($cfg in @("xenia-canary.config.toml", "xenia.config.toml", "xenia-canary-config.toml")) {
  Patch-ConfigFile (Join-Path $Root $cfg) $ip
}

$python = Get-Command python -ErrorAction SilentlyContinue
if (-not $python) { $python = Get-Command py -ErrorAction SilentlyContinue }

if ($python) {
  $hostScript = Join-Path $Root "codered_tools\codered_rdr_bootstrap_host.py"
  Write-Host "[Code RED] Starting local bootstrap host..."
  Start-Process -FilePath $python.Source -ArgumentList "`"$hostScript`"" -WorkingDirectory $Root -WindowStyle Normal
  Start-Sleep -Seconds 1
} else {
  Write-Host "[Code RED] Python not found; bootstrap host was not started. Install Python or start your old CodeRED bootstrap host manually."
}

if (-not $IsoPath) {
  $recent = Join-Path $Root "recent.toml"
  if (Test-Path $recent) {
    $raw = Get-Content -LiteralPath $recent -Raw
    $m = [regex]::Match($raw, "path\s*=\s*'([^']+)'")
    if ($m.Success) { $IsoPath = $m.Groups[1].Value }
  }
}

if (-not $IsoPath) {
  Write-Host "[Code RED] No ISO path provided and recent.toml had no path."
  Write-Host "Usage: START_CODERED_FREEROAM.bat `"D:\Path\To\Disc 2.iso`""
  pause
  exit 1
}

if (-not (Test-Path $IsoPath)) {
  Write-Host "[Code RED] ISO path does not exist:" $IsoPath
  Write-Host "Launch manually or run: START_CODERED_FREEROAM.bat `"D:\Path\To\Disc 2.iso`""
  pause
  exit 1
}

$exe = Join-Path $Root "xenia_canary.exe"
if (-not (Test-Path $exe)) {
  Write-Host "[Code RED] Missing xenia_canary.exe in:" $Root
  pause
  exit 1
}

Write-Host "[Code RED] Launching Xenia:"
Write-Host "  $exe"
Write-Host "  $IsoPath"
Start-Process -FilePath $exe -ArgumentList "`"$IsoPath`"" -WorkingDirectory $Root
