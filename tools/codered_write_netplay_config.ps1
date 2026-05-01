param(
  [Parameter(Mandatory=$true)][string]$Root,
  [string]$RdrPath = "D:\Games\Red Dead Redemption",
  [string]$ApiAddress = "http://127.0.0.1:36000/",
  [string]$InterfaceAddress = "127.0.0.1"
)

$ErrorActionPreference = "Stop"

function Normalize-InputPath([string]$Value) {
  $v = $Value.Trim().Trim('"')
  while ($v.EndsWith('"')) { $v = $v.Substring(0, $v.Length - 1) }
  while ($v.EndsWith('\') -or $v.EndsWith('/')) { $v = $v.Substring(0, $v.Length - 1) }
  return [System.IO.Path]::GetFullPath($v)
}

function Escape-Toml([string]$Value) {
  return $Value.Replace('\', '\\').Replace('"', '\"')
}

$Root = Normalize-InputPath $Root
$RdrPath = Normalize-InputPath $RdrPath

$configNames = @(
  "xenia-canary.config.toml",
  "xenia-canary-config.toml",
  "xenia.config.toml"
)

$exeCandidates = @(
  (Join-Path $Root "xenia_canary.exe"),
  (Join-Path $Root "build\bin\Windows\Release\xenia_canary.exe"),
  (Join-Path $Root "build\bin\Windows\Debug\xenia_canary.exe"),
  (Join-Path $Root "build\bin\Release\xenia_canary.exe"),
  (Join-Path $Root "build\bin\Debug\xenia_canary.exe"),
  (Join-Path $Root "bin\xenia_canary.exe")
)

$targetDirs = New-Object System.Collections.Generic.List[string]
$targetDirs.Add($Root)
foreach ($exe in $exeCandidates) {
  if (Test-Path -LiteralPath $exe) {
    $dir = Split-Path -Parent $exe
    if (-not $targetDirs.Contains($dir)) { $targetDirs.Add($dir) }
  }
}

function Remove-TomlSection {
  param([string[]]$Lines, [string]$SectionName)
  $out = New-Object System.Collections.Generic.List[string]
  $skip = $false
  foreach ($line in $Lines) {
    if ($line -match '^\s*\[(.+?)\]\s*$') {
      $name = $Matches[1]
      if ($name -eq $SectionName) {
        $skip = $true
        continue
      }
      if ($skip) { $skip = $false }
    }
    if (-not $skip) { $out.Add($line) }
  }
  return $out.ToArray()
}

function Update-ConfigFile {
  param([string]$Path)
  $lines = @()
  if (Test-Path -LiteralPath $Path) {
    $lines = Get-Content -LiteralPath $Path
  }
  $lines = Remove-TomlSection -Lines $lines -SectionName "Netplay"
  $lines = Remove-TomlSection -Lines $lines -SectionName "CodeRED"

  $append = @(
    "",
    "[Netplay]",
    "network_mode = 2",
    "netplay_api_address = `"$(Escape-Toml $ApiAddress)`"",
    "selected_network_interface = `"$(Escape-Toml $InterfaceAddress)`"",
    "upnp = true",
    "xhttp = true",
    "net_logging = true",
    "netplay_http_timeout_ms = 1500",
    "",
    "[CodeRED]",
    "rdr_path = `"$(Escape-Toml $RdrPath)`""
  )

  $merged = @($lines) + $append
  $parent = Split-Path -Parent $Path
  if (-not (Test-Path -LiteralPath $parent)) { New-Item -ItemType Directory -Force -Path $parent | Out-Null }
  Set-Content -LiteralPath $Path -Value $merged -Encoding UTF8
  Write-Host "Updated $Path"
}

foreach ($dir in $targetDirs) {
  foreach ($name in $configNames) {
    Update-ConfigFile -Path (Join-Path $dir $name)
  }
}

Write-Host "CodeRED netplay config updated. RDR path: $RdrPath"
