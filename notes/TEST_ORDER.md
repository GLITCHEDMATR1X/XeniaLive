# Test order

1. Back up your current Xenia release folder.
2. Put `01_INSTALL_CONFIG_FIXES_TO_RELEASE.bat` in the folder with `xenia_canary.exe` and run it.
3. Fully close Xenia.
4. Test the current Free Roam ISO/mod once.
5. If it still hangs, collect `xenia.log` with `04_COLLECT_NEW_XENIA_LOG_SUMMARY.bat`.
6. Fix/build source:
   - run `git submodule update --init --recursive`
   - run `02_APPLY_XAM_SOURCE_PATCH.bat` from the source root
   - run `03_FIX_THIRD_PARTY_AND_BUILD.bat`
7. Test the rebuilt EXE with the same config and same modded ISO.

Do not change multiple RDR layer_0 XML patches at the same time while testing this XAM profile pass. Keep the RDR-side patch constant so the result is attributable.
