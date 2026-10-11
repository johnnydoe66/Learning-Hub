@echo off
cd /d "%~dp0"
python -c "import imgui_bundle" 2>nul || python -m pip install -r requirements.txt
start "" pythonw wit_gui.py
