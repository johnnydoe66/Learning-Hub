#!/bin/sh
cd "$(dirname "$0")"
python3 -c "import imgui_bundle" 2>/dev/null || python3 -m pip install -r requirements.txt
exec python3 wit_gui.py
