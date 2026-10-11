@echo off
rem Download WIT binaries into bin\ and an offline copy of wit.wiimm.de into site\
cd /d "%~dp0"
python wit_setup.py all
pause
