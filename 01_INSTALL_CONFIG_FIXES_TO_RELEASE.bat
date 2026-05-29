@echo off
setlocal EnableExtensions
cd /d "%~dp0"

set XUID=E03000004156EF97

echo [Code RED] Applying RDR/Xenia profile config fixes to current folder...

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$files=@('xenia-canary.config.toml','xenia-canary-config.toml','xenia.config.toml'); foreach($f in $files){ if(Test-Path $f){ $t=Get-Content $f -Raw; if($t -match 'license_mask\s*='){ $t=$t -replace 'license_mask\s*=\s*[^\r\n#]*','license_mask = -1                                  '; } else { $t += \"`r`nlicense_mask = -1`r`n\" }; if($t -match 'netplay_disable_saves\s*='){ $t=$t -replace 'netplay_disable_saves\s*=\s*[^\r\n#]*','netplay_disable_saves = false'; } else { $t += \"`r`nnetplay_disable_saves = false`r`n\" }; if($t -match 'disable_saves\s*='){ $t=$t -replace 'disable_saves\s*=\s*[^\r\n#]*','disable_saves = false'; } else { $t += \"`r`ndisable_saves = false`r`n\" }; if($t -match 'net_logging\s*='){ $t=$t -replace 'net_logging\s*=\s*[^\r\n#]*','net_logging = true'; } else { $t += \"`r`nnet_logging = true`r`n\" }; if($t -match 'flush_log\s*='){ $t=$t -replace 'flush_log\s*=\s*[^\r\n#]*','flush_log = true'; } else { $t += \"`r`nflush_log = true`r`n\" }; if($t -match 'logged_profile_slot_0_xuid\s*='){ $t=$t -replace 'logged_profile_slot_0_xuid\s*=\s*\"[^\"]*\"','logged_profile_slot_0_xuid = \"%XUID%\"'; } else { $t += \"`r`n[Profiles]`r`nlogged_profile_slot_0_xuid = \\\"%XUID%\\\"`r`n\" }; Copy-Item $f ($f+'.codered_pass6_bak') -Force; Set-Content $f $t -Encoding UTF8; Write-Host 'patched' $f } else { Write-Host 'missing' $f } }"

echo.
echo Done. Fully close Xenia before testing.
pause
