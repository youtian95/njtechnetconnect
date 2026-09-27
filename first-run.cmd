@echo off
chcp 65001 >nul
rem First-run setup entry for the packaged release. Python is not required.
rem Keep this file ASCII-only: Chinese text desyncs cmd.exe's parser and breaks the script.
cd /d "%~dp0"
njtechnetconnect.exe setup
if errorlevel 1 echo Setup did not finish. See the messages above or run njtechnetconnect.exe status.
pause