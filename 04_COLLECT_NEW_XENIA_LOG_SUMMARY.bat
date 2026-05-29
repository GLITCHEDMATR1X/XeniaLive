@echo off
setlocal EnableExtensions
cd /d "%~dp0"

set LOG=xenia.log
if not exist "%LOG%" (
  echo xenia.log not found beside this script. Put this script in the Xenia release folder or copy xenia.log here.
  pause
  exit /b 1
)

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$log='xenia.log'; $out='codered_pass6_log_summary.txt'; $patterns=@('XamUserGetXUID','XamUserGetSigninInfo','XamUserGetSigninState','XamUserCheckPrivilege','XamContentCreateEnumerator','RDR2MPSAVE','RDR2OPTIONS','RDR2SAVE','RDR2ZOMBIESAVE','CodeRED Netplay','ResolvePath(\content','net.worldLoaded','net.sessionJoined','net.lostConnection','signedOffline','WSAGetLastError: 10035'); 'Code RED pass6 log summary' | Set-Content $out; foreach($p in $patterns){ Add-Content $out \"`r`n--- $p ---\"; Select-String -Path $log -Pattern $p -SimpleMatch | Select-Object -Last 30 | ForEach-Object { Add-Content $out $_.Line } }; Write-Host 'Wrote' $out"

pause
