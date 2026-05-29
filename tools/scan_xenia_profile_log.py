
from __future__ import annotations
import re, sys
from pathlib import Path

log = Path(sys.argv[1]) if len(sys.argv) > 1 else Path('xenia.log')
text = log.read_text(errors='ignore')
patterns = [
    'logged_profile_slot_0_xuid',
    'FindProfiles: Adding profile',
    'XamUserGetXUID',
    'XamUserGetSigninInfo',
    'XamUserCheckPrivilege',
    'XamUserReadProfileSettings',
    'RDR2MPSAVE.SAV',
    'netplay_disable_saves',
    'disable_saves',
    'net.worldLoaded',
    'net.sessionJoined',
    'net.lostConnection',
    'net.signedOffline',
    'StartMultiplayer',
]
print(f'Log: {log}')
for p in patterns:
    print(f'{p}: {text.count(p)}')
print('\nSuspicious XUID returns:')
for line in text.splitlines():
    if 'XamUserGetXUID' in line and ('0000000000000000' in line or '00000000)' in line):
        print(line[:300])
