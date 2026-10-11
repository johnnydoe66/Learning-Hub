# WIT GUI — Wiimms ISO Tools without the terminal

Dear ImGui front-end for **wit**, **wwt**, **wdf**, **wfuse** from https://wit.wiimm.de.

## Quick start (Windows)
1. Install Python 3.10+ (tick "Add to PATH").
2. Double-click `setup_all.bat` → downloads WIT binaries into `bin\` and an offline HTML copy of wit.wiimm.de into `site\`.
3. Double-click `run_gui.bat`.
4. Optional: `build_exe.bat` → standalone `WIT_GUI.exe`.

Linux/macOS: `python3 wit_setup.py all && ./run_gui.sh`.

Everything from step 2 can also be done inside the GUI (**Setup & Docs** tab).

## Folder layout
| Path | Content |
|---|---|
| `wit_gui.py` | the GUI |
| `wit_setup.py` | downloader for binaries + website mirror (`tools`, `site`, `all`, `archive FILE`) |
| `bin/` | wit/wwt/wdf/wfuse executables (+ cygwin DLLs on Windows) |
| `site/index.html` | offline copy of wit.wiimm.de |

## GUI
- Tabs per tool, command list on the left (filterable, tooltips).
- Sources (Add files/folder), destination, positional args, options (checkboxes / combos with suggestions), extra raw args.
- Live command preview, **Run / Stop**, **Copy command**, **Help for command** (runs `wit HELP <CMD>` — real docs from the binary).
- Output console with progress-line handling.
- If no Internet download works: get the archive manually from wit.wiimm.de → **Install from archive...**.

Notes: `wfuse` needs FUSE (Linux/macOS only). `wwt FORMAT`/`SYNC`/`REMOVE` modify drives — use **Test / dry run** first.
