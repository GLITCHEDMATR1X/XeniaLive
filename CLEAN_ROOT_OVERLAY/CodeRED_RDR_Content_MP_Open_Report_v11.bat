@echo off
setlocal
cd /d "%~dp0"
if exist logs\codered_rdr_content_mp_index_v11.txt (
  notepad logs\codered_rdr_content_mp_index_v11.txt
) else (
  echo No v11 report found yet. Run CodeRED_RDR_Content_MP_Indexer_v11.bat first.
  pause
)
