CodeRED XEX / Package Viewer v10
=================================

Purpose
-------
This pass adds a read-only XEX/PIRS/manifest viewer and launch-target guard for the
CodeRED Xenia RDR test setup.

It does not decrypt, edit, patch, or bypass XEX security. It only identifies and reports.

Why this pass exists
--------------------
The RDR system-update/dashboard reference zips include files named default.xex. If those are
extracted into the active Red Dead Redemption folder, a blind launcher search can accidentally
pick a dashboard/system-update executable instead of the intended RDR game ISO/XEX.

That would make multiplayer/profile testing misleading.

Added files
-----------
- tools/codered_xex_viewer.py
- CodeRED_XEX_View_And_Audit_v10.bat
- CodeRED_XEX_View_Zip_v10.bat
- CodeRED_RDR_Launch_Target_Guard_v10.bat
- docs/codered/rdr_xex_viewer_v10.md

Usage
-----
Extract this package over:

  D:\Games\Red Dead Redemption\xenia-canary-6de80df\

Then run:

  CodeRED_XEX_View_And_Audit_v10.bat

By default, it scans:

  D:\Games\Red Dead Redemption

To scan a zip, drag the zip onto:

  CodeRED_XEX_View_Zip_v10.bat

or run:

  CodeRED_XEX_View_Zip_v10.bat "D:\path\file.zip"

To run the stricter launch-target guard:

  CodeRED_RDR_Launch_Target_Guard_v10.bat

Reports
-------
Reports are written to:

  logs\codered_xex_audit_v10.txt
  logs\codered_xex_audit_v10.json
  logs\codered_xex_zip_audit_v10.txt
  logs\codered_xex_zip_audit_v10.json
  logs\codered_launch_target_guard_v10.txt
  logs\codered_launch_target_guard_v10.json

Recommended rule
----------------
Keep dashboard/system update files as reference material only. Do not extract them into the
active RDR test folder unless they are in a clearly ignored subfolder such as:

  D:\Games\Red Dead Redemption\_reference_system_update\

The RDR multiplayer bootstrap still needs UDP/session discovery work. These dashboard/update
XEX files are not a multiplayer world-server fix, but they help prevent wrong-launch regressions.
