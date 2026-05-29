# Code RED Xenia Free Roam READY package

This package has the config fixes applied directly. No drop-in folders.

## What is already applied

- Local profile slot 0: `E03000004156EF97`
- Content license mask: `-1`
- MP save blocking disabled
- Netplay logging enabled
- Code RED single-player host bridge enabled
- UDP bootstrap enabled
- Title update application disabled for this private modded Disc 2/layer test
- Local bootstrap host included at `codered_tools/codered_rdr_bootstrap_host.py`

## Run it

Double-click:

```text
START_CODERED_FREEROAM.bat
```

The launcher will:
1. Patch the configs one more time in-place.
2. Detect your current local IPv4.
3. Start the local Code RED bootstrap host on `127.0.0.1:36000`.
4. Launch `xenia_canary.exe` using the ISO path from `recent.toml`.

If it cannot find the ISO, run:

```bat
START_CODERED_FREEROAM.bat "D:\Path\To\Your\Disc 2.iso"
```

## Log

After a failed test, check:

```text
logs\xenia_codered_freeroam_ready.log
```

or any new `xenia*.log` beside the EXE.

## Notes

This is private/offline testing only. It does not connect to Xbox Live or any public service.
