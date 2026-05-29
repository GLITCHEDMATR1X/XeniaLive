param(
  [string]$Root = (Get-Location).Path,
  [string]$Xuid = "E03000004156EF97"
)

$ErrorActionPreference = "Stop"
$Root = [System.IO.Path]::GetFullPath($Root)
Write-Host "[Code RED] Target Xenia release folder: $Root"
if (!(Test-Path $Root)) {
  throw "Target folder does not exist: $Root"
}
Set-Location $Root

$configNames = @(
  "xenia-canary.config.toml",
  "xenia-canary-config.toml",
  "xenia.config.toml"
)

function Set-TomlScalarLine {
  param(
    [string]$Text,
    [string]$Key,
    [string]$Value
  )
  $escapedKey = [regex]::Escape($Key)
  $pattern = "(?m)^\s*$escapedKey\s*=.*$"
  $line = "$Key = $Value"
  if ($Text -match $pattern) {
    return [regex]::Replace($Text, $pattern, $line)
  }
  if ($Text.Length -gt 0 -and !$Text.EndsWith("`n")) {
    $Text += "`r`n"
  }
  return $Text + $line + "`r`n"
}

function Ensure-ProfileSlot0 {
  param(
    [string]$Text,
    [string]$Xuid
  )
  $line = "logged_profile_slot_0_xuid = `"$Xuid`""
  $pattern = '(?m)^\s*logged_profile_slot_0_xuid\s*=.*$'
  if ($Text -match $pattern) {
    return [regex]::Replace($Text, $pattern, $line)
  }
  if ($Text -notmatch '(?m)^\s*\[Profiles\]\s*$') {
    if ($Text.Length -gt 0 -and !$Text.EndsWith("`n")) { $Text += "`r`n" }
    $Text += "`r`n[Profiles]`r`n"
  } elseif ($Text.Length -gt 0 -and !$Text.EndsWith("`n")) {
    $Text += "`r`n"
  }
  return $Text + $line + "`r`n"
}

$patched = 0
foreach ($name in $configNames) {
  $path = Join-Path $Root $name
  if (!(Test-Path $path)) {
    Write-Host "missing $name"
    continue
  }

  $text = Get-Content $path -Raw
  $stamp = Get-Date -Format "yyyyMMdd_HHmmss"
  Copy-Item $path "$path.codered_pass6b_bak_$stamp" -Force

  $text = Set-TomlScalarLine $text "license_mask" "-1"
  $text = Set-TomlScalarLine $text "netplay_disable_saves" "false"
  $text = Set-TomlScalarLine $text "disable_saves" "false"
  $text = Set-TomlScalarLine $text "net_logging" "true"
  $text = Set-TomlScalarLine $text "flush_log" "true"
  $text = Ensure-ProfileSlot0 $text $Xuid

  Set-Content -Path $path -Value $text -Encoding UTF8
  Write-Host "patched $name"
  $patched += 1
}

if ($patched -eq 0) {
  throw "No Xenia config files found in $Root. Run this from the folder containing xenia_canary.exe, or pass that folder path to the BAT."
}

Write-Host "[Code RED] Config patch complete. Fully close Xenia before testing."
