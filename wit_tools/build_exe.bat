@echo off
rem Builds a standalone WIT_GUI.exe (no Python needed afterwards) into this folder
cd /d "%~dp0"
python -m pip install -r requirements.txt pyinstaller
python -m PyInstaller --noconfirm --onefile --windowed --name WIT_GUI --collect-all imgui_bundle wit_gui.py
copy /y dist\WIT_GUI.exe .
