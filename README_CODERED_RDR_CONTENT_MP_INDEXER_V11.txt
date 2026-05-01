CodeRED RDR Content Multiplayer Indexer v11
==========================================

Purpose
-------
This pass indexes RDR content.zip / extracted content trees without editing them.
It focuses on multiplayer scripts, freemode, action areas, regions, gringo scripts,
vehicle/wagon/horse/train references, update threads, and population/ambient leads.

Why this matters
----------------
The current Xenia/RDR tests show RDR receives a network identity, then loops on
recvfrom / WSAGetLastError 10035. That means the local MP world/scripts are likely
present, but the session/UDP bootstrap is not feeding the game useful packets yet.
This indexer proves what local content exists so future Xenia passes can focus on
network/session bootstrap instead of chasing missing world files.

Install
-------
Extract this package over:

  D:\Games\Red Dead Redemption\xenia-canary-6de80df\

No Xenia rebuild is required. This is tooling only.

Run
---
Place content.zip in the xenia-canary-6de80df folder, then run:

  CodeRED_RDR_Content_MP_Indexer_v11.bat

Or drag any content.zip onto:

  CodeRED_RDR_Content_MP_Index_Zip_v11.bat

Reports
-------
Reports are written to:

  logs\codered_rdr_content_mp_index_v11.txt
  logs\codered_rdr_content_mp_index_v11.json

Safety
------
This pass does not modify .csc, .sco, .xex, .rpf, PIRS, LIVE, CON, or package files.
Do not bulk patch content scripts. Use copied archives and one controlled experiment
at a time.
