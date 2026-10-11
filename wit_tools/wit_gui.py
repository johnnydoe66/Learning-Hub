#!/usr/bin/env python3
"""Dear ImGui front-end for Wiimms ISO Tools (wit, wwt, wdf, wfuse).

Run:  python wit_gui.py      (needs:  pip install imgui-bundle)
"""
import json
import os
import shlex
import shutil
import subprocess
import sys
import threading
import webbrowser

from imgui_bundle import hello_imgui, imgui, immapp
from imgui_bundle import portable_file_dialogs as pfd

import wit_setup

HERE = os.path.dirname(os.path.abspath(__file__))
CONFIG = os.path.join(HERE, "wit_gui.json")
IS_WIN = sys.platform.startswith("win")
IMAGE_FILTER = ["Wii/GC images", "*.iso *.wbfs *.wdf *.wia *.ciso *.wbi *.gcz *.rvz *.gcm *.dol",
                "All files", "*"]

# ------------------------------------------------------------------ options
# key: (flag, kind, label, suggestions, tooltip)
#   kind: bool | text | flags (choice whose value is the flag itself)
FORMATS = ["", "--iso", "--wbfs", "--wdf", "--wdf1", "--wdf2", "--wia", "--ciso", "--wbi", "--gcz", "--fst"]
OPTS = {
    "format":   ("", "flags", "Output format", FORMATS, "Image format of the destination (empty = tool default)"),
    "compr":    ("--compression", "text", "Compression", ["", "none", "purge", "bzip2", "lzma", "lzma2", "lzma.9", "bzip2.9", "best", "fast", "default"], "WIA/GCZ compression method[.level][@chunk]"),
    "psel":     ("--psel", "text", "Partitions", ["", "data", "update", "channel", "ptab", "whole", "raw", "-update", "data,channel"], "Partition selector (--psel)"),
    "pmode":    ("--pmode", "text", "Prefix mode", ["", "auto", "none", "point", "name", "index"], "Partition prefix mode for file paths"),
    "files":    ("--files", "text", "File filter", ["", "+/sys/", "-/files/movie/", "=/files/"], "File selection rules (--files RULES)"),
    "overwrite":("--overwrite", "bool", "Overwrite (-o)", None, "Overwrite existing files"),
    "update":   ("--update", "bool", "Update only (-u)", None, "Copy only files that do not exist at destination"),
    "remove":   ("--remove", "bool", "Remove source (-R)", None, "Remove source files after successful copy"),
    "preserve": ("--preserve", "bool", "Preserve times (-p)", None, "Preserve file times"),
    "split":    ("--split", "bool", "Split output (-z)", None, "Split output into multiple files"),
    "splitsize":("--split-size", "text", "Split size", ["", "4G", "2G", "4300M"], "Split size, implies --split"),
    "trunc":    ("--trunc", "bool", "Truncate (--trunc)", None, "Truncate image after copy"),
    "enc":      ("--enc", "text", "Encoding", ["", "auto", "none", "decrypt", "encrypt", "sign"], "Encryption/sign mode (--enc)"),
    "modify":   ("--modify", "text", "Modify", ["", "auto", "none", "all", "disc", "boot", "ticket", "tmd", "wbfs", "tik,tmd"], "Where to patch ID/name (--modify)"),
    "region":   ("--region", "text", "Region", ["", "jap", "usa", "pal", "korea", "file", "disc", "auto"], "Patch region"),
    "ios":      ("--ios", "text", "System IOS", ["", "36", "38", "53", "55", "56", "57", "58", "249"], "Patch system version / IOS"),
    "id":       ("--id", "text", "New ID", None, "Patch the ID (e.g. RMCP01)"),
    "name":     ("--name", "text", "New name", None, "Patch the disc name"),
    "dest":     ("--dest", "path", "Destination (-d)", None, "Destination file or directory"),
    "DEST":     ("--DEST", "path", "Destination + create dirs (-D)", None, "Like --dest but creates missing directories"),
    "recurse":  ("--recurse", "path", "Recurse folder (-r)", None, "Search this folder recursively for images"),
    "rdepth":   ("--rdepth", "text", "Recurse depth", ["", "1", "2", "5", "10"], "Max recursion depth"),
    "include":  ("--include", "text", "Include IDs (-n)", None, "Only images with these IDs (ID4/ID6, wildcards)"),
    "exclude":  ("--exclude", "text", "Exclude IDs (-x)", None, "Skip images with these IDs"),
    "ignore":   ("--ignore", "bool", "Ignore missing (-i)", None, "Ignore non-existing files/discs"),
    "sort":     ("--sort", "text", "Sort", ["", "id", "name", "title", "path", "size", "date", "region", "wbfs", "npart", "none"], "Sort listing"),
    "sections": ("--sections", "bool", "Sections output", None, "Machine-readable section output"),
    "long":     ("--long", "bool", "Long (-l)", None, "More details"),
    "unique":   ("--unique", "bool", "Unique (-U)", None, "Eliminate duplicates"),
    "titles":   ("--titles", "path", "Titles file (-T)", None, "Path to a titles.txt"),
    "verbose":  ("--verbose", "bool", "Verbose (-v)", None, "Verbose output"),
    "quiet":    ("--quiet", "bool", "Quiet (-q)", None, "Quiet output"),
    "progress": ("--progress", "bool", "Progress (-P)", None, "Print progress counter"),
    "test":     ("--test", "bool", "Test / dry run (-t)", None, "Show what would happen, change nothing"),
    "sneek":    ("--sneek", "bool", "SNEEK layout", None, "Extract for SNEEK"),
    "neek":     ("--neek", "bool", "NEEK layout", None, "Extract for NEEK"),
    "limit":    ("--limit", "text", "Error limit", None, "Max number of errors to report"),
    # wwt
    "part":     ("--part", "path", "WBFS partition (-p)", None, "WBFS partition or file, e.g. /dev/sdb1 or X:\\ (Windows: \\\\.\\X:)"),
    "auto":     ("--auto", "bool", "Auto-find WBFS (-a)", None, "Search all WBFS partitions automatically"),
    "all":      ("--all", "bool", "All partitions (-A)", None, "Use all found WBFS partitions"),
    "force":    ("--force", "bool", "Force (-f)", None, "Force the operation"),
    "newer":    ("--newer", "bool", "Newer only", None, "Add/update only newer images"),
    "sync":     ("--sync", "bool", "Sync", None, "Synchronize: remove discs not in source"),
    "repair":   ("--repair", "text", "Repair mode", ["", "fbt", "inodes", "standard", "rm-invalid", "rm-overlap", "rm-free", "rm-all", "all"], "Repair mode for CHECK/REPAIR"),
    "hss":      ("--hss", "text", "HD sector size", ["", "512", "2048", "4096"], "Hard disk sector size"),
    "wss":      ("--wss", "text", "WBFS sector size", ["", "1M", "2M", "4M", "8M"], "WBFS sector size"),
    "recover":  ("--recover", "bool", "Recover", None, "Format in recover mode"),
    "inode":    ("--inode", "bool", "Inodes", None, "Force inode creation"),
    # wdf
    "keep":     ("--keep", "bool", "Keep source (-k)", None, "Keep the source file"),
    "stdout":   ("--stdout", "bool", "To stdout (-c)", None, "Write result to stdout"),
    "chunk":    ("--chunk", "bool", "Chunk table", None, "Print chunk table (DUMP)"),
    # wfuse
    "umount":   ("--umount", "bool", "Unmount (-u)", None, "Unmount instead of mount"),
    "lazy":     ("--lazy", "bool", "Lazy unmount (-l)", None, "Lazy unmount"),
    "create":   ("--create", "bool", "Create mount dir (-c)", None, "Create the mount point if missing"),
    "remount":  ("--remount", "bool", "Remount (-r)", None, "Unmount first if already mounted"),
    "fuseopt":  ("--option", "text", "FUSE option (-o)", ["", "allow_other", "ro"], "Pass option to FUSE"),
}

COMMON = ["verbose", "quiet", "test", "titles"]
SEL = ["recurse", "rdepth", "include", "exclude", "ignore"]
PATCH = ["modify", "region", "ios", "id", "name", "enc"]
COPYO = ["format", "compr", "psel", "split", "splitsize", "overwrite", "update", "remove", "preserve", "trunc", "progress"]

# Command spec: name -> (description, src, dest, args_hint, options)
#   src: files/dirs list   dest: show --dest   args_hint: extra positional args (None = none)
WIT = {
    "VERSION":   ("Print program name and version", 0, 0, None, ["long"]),
    "INFO":      ("Print information about internal keywords/formats", 0, 0, "KEYWORD ...", ["long"]),
    "TITLES":    ("Dump the internal titles database", 0, 0, "ID ...", ["titles"]),
    "GETTITLES": ("Download titles.txt (GameTDB) into the share dir", 0, 0, None, []),
    "COMPR":     ("List supported compression modes", 0, 0, "MODE ...", ["long"]),
    "FILELIST":  ("List all source files", 1, 0, None, SEL + ["long"]),
    "FILETYPE":  ("Print the file type of each source", 1, 0, None, SEL + ["long"]),
    "ISOSIZE":   ("Print the ISO and WBFS sizes", 1, 0, None, SEL + ["long"]),
    "DUMP":      ("Dump the data structure of images", 1, 0, None, SEL + ["psel", "files", "long"]),
    "ID6":       ("Print the ID6 of each image", 1, 0, None, SEL + ["unique", "sort"]),
    "ID8":       ("Print the ID8 (ID6 + disc + version)", 1, 0, None, SEL + ["unique", "sort"]),
    "FRAGMENTS": ("Print the fragmentation of images", 1, 0, None, SEL + ["long"]),
    "LIST":      ("List images (short)", 1, 0, None, SEL + ["sort", "unique", "sections"]),
    "LIST-L":    ("List images (long)", 1, 0, None, SEL + ["sort", "unique", "sections"]),
    "LIST-LL":   ("List images (more details)", 1, 0, None, SEL + ["sort", "unique", "sections"]),
    "LIST-LLL":  ("List images (all details)", 1, 0, None, SEL + ["sort", "unique", "sections"]),
    "ILIST":     ("List all files inside images", 1, 0, None, SEL + ["psel", "pmode", "files", "sort"]),
    "ILIST-L":   ("List files inside images (with sizes)", 1, 0, None, SEL + ["psel", "pmode", "files", "sort"]),
    "ILIST-LL":  ("List files inside images (with offsets)", 1, 0, None, SEL + ["psel", "pmode", "files", "sort"]),
    "DIFF":      ("Compare images raw (first = source, dest = compare)", 1, 1, None, SEL + ["psel", "files", "long", "limit"]),
    "FDIFF":     ("Compare images file by file", 1, 1, None, SEL + ["psel", "files", "long", "limit"]),
    "EXTRACT":   ("Extract all files of images into a folder", 1, 1, None, SEL + ["psel", "pmode", "files", "overwrite", "preserve", "sneek", "neek", "progress"] + PATCH),
    "COPY":      ("Copy/convert images to the destination", 1, 1, None, SEL + COPYO + PATCH),
    "CONVERT":   ("Convert images in place (keep name)", 1, 0, None, SEL + ["format", "compr", "psel", "split", "splitsize", "preserve", "trunc", "progress"] + PATCH),
    "EDIT":      ("Patch ID/name/region/IOS of images in place", 1, 0, None, SEL + PATCH),
    "MOVE":      ("Move/rename image files", 1, 1, None, SEL + ["overwrite"]),
    "RENAME":    ("Rename ID and title of images", 1, 0, "ID6=[new title] ...", SEL + ["modify", "ignore"]),
    "SETTITLE":  ("Set the title of images", 1, 0, "ID6=new title ...", SEL + ["modify"]),
    "VERIFY":    ("Verify hash values of images", 1, 0, None, SEL + ["psel", "long", "limit", "progress"]),
    "SKELETON":  ("Create small skeleton images (for analysis)", 1, 1, None, SEL + ["psel"]),
    "MIX":       ("Mix partitions from different sources", 0, 1, "SOURCE [select] [as PTYPE] ...", ["format", "overwrite", "id", "name", "region", "ios"]),
}
WWT = {
    "VERSION":   ("Print program name and version", 0, 0, None, ["long"]),
    "INFO":      ("Print information about internal keywords", 0, 0, "KEYWORD ...", ["long"]),
    "TITLES":    ("Dump the internal titles database", 0, 0, "ID ...", ["titles"]),
    "GETTITLES": ("Download titles.txt (GameTDB)", 0, 0, None, []),
    "COMPR":     ("List supported compression modes", 0, 0, None, ["long"]),
    "FIND":      ("Find WBFS partitions", 0, 0, None, ["part", "auto", "all", "long"]),
    "SPACE":     ("Print disk space of WBFS partitions", 0, 0, None, ["part", "auto", "all", "long"]),
    "ANALYZE":   ("Analyze files/partitions for WBFS structures", 1, 0, None, ["long"]),
    "DUMP":      ("Dump WBFS partition structure", 0, 0, None, ["part", "auto", "all", "long"]),
    "ID6":       ("Print ID6 of all discs in WBFS", 0, 0, None, ["part", "auto", "all", "unique", "sort"]),
    "LIST":      ("List discs in WBFS (short)", 0, 0, None, ["part", "auto", "all", "sort", "unique", "sections"]),
    "LIST-L":    ("List discs in WBFS (long)", 0, 0, None, ["part", "auto", "all", "sort", "unique", "sections"]),
    "LIST-LL":   ("List discs in WBFS (details)", 0, 0, None, ["part", "auto", "all", "sort", "unique", "sections"]),
    "LIST-A":    ("List discs of all partitions", 0, 0, None, ["sort", "unique", "sections"]),
    "LIST-M":    ("List discs, mixed view", 0, 0, None, ["part", "auto", "all", "sort"]),
    "LIST-U":    ("List discs, unique view", 0, 0, None, ["part", "auto", "all", "sort"]),
    "FORMAT":    ("Format a file or partition as WBFS (DESTRUCTIVE)", 1, 0, None, ["force", "hss", "wss", "recover", "inode", "test"]),
    "RECOVER":   ("Recover deleted discs of WBFS", 0, 0, None, ["part", "auto", "all", "test"]),
    "CHECK":     ("Check WBFS for errors", 0, 0, None, ["part", "auto", "all", "repair", "long"]),
    "REPAIR":    ("Check and repair WBFS", 0, 0, None, ["part", "auto", "all", "repair", "test"]),
    "EDIT":      ("Low-level edit of WBFS blocks (expert)", 0, 0, "act=block,... ", ["part", "force", "test"]),
    "PHANTOM":   ("Add phantom discs (testing)", 0, 0, "ID6=size ...", ["part", "test"]),
    "TRUNCATE":  ("Truncate WBFS file/partition", 0, 0, None, ["part", "auto", "test"]),
    "ADD":       ("Add images to WBFS", 1, 0, None, ["part", "auto", "all"] + SEL + ["psel", "update", "newer", "sync", "remove", "progress"] + PATCH),
    "UPDATE":    ("Add only missing images to WBFS", 1, 0, None, ["part", "auto", "all"] + SEL + ["psel", "newer", "progress"]),
    "NEW":       ("Add only newer images to WBFS", 1, 0, None, ["part", "auto", "all"] + SEL + ["psel", "progress"]),
    "SYNC":      ("Sync WBFS with sources (removes others!)", 1, 0, None, ["part", "auto", "all"] + SEL + ["psel", "newer", "progress"]),
    "DUP":       ("Duplicate WBFS partition", 0, 1, None, ["part", "auto", "progress"]),
    "EXTRACT":   ("Extract discs from WBFS to images", 0, 1, "ID6[=dest] ...", ["part", "auto", "all", "format", "compr", "psel", "split", "splitsize", "overwrite", "unique", "progress"] + PATCH),
    "REMOVE":    ("Remove discs from WBFS", 0, 0, "ID6 ...", ["part", "auto", "all", "force", "unique", "test"]),
    "RENAME":    ("Rename ID6 and title of discs in WBFS", 0, 0, "ID6=[new ID][,title] ...", ["part", "auto", "all", "modify", "test"]),
    "SETTITLE":  ("Set title of discs in WBFS", 0, 0, "ID6=new title ...", ["part", "auto", "all", "modify", "test"]),
    "TOUCH":     ("Set time stamps of discs", 0, 0, "ID6 ...", ["part", "auto", "all", "test"]),
    "VERIFY":    ("Verify discs in WBFS", 0, 0, "ID6 ...", ["part", "auto", "all", "psel", "long", "limit", "progress"]),
    "SKELETON":  ("Create skeletons of WBFS discs", 0, 1, "ID6 ...", ["part", "auto", "all"]),
    "FILETYPE":  ("Print file types", 1, 0, None, ["long"]),
    "ISOSIZE":   ("Print ISO/WBFS sizes", 1, 0, None, ["long"]),
}
WDF = {
    "+PACK":     ("Pack images (WDF/WIA/CISO/WBI/GCZ)", 1, 1, None, ["format", "compr", "overwrite", "keep", "stdout", "preserve", "split", "splitsize"]),
    "+UNPACK":   ("Unpack to plain ISO", 1, 1, None, ["overwrite", "keep", "stdout", "preserve", "split", "splitsize"]),
    "+CAT":      ("Write unpacked data to stdout/dest", 1, 1, None, ["overwrite"]),
    "+CMP":      ("Compare two (packed) files", 1, 0, None, ["long", "limit"]),
    "+DUMP":     ("Dump container structure", 1, 0, None, ["chunk", "long"]),
    "+VERSION":  ("Print program version", 0, 0, None, ["long"]),
}
WFUSE = {
    "MOUNT":     ("Mount an image/WBFS as folder (Linux/macOS only)", 1, 0, "MOUNT_DIR", ["create", "remount", "fuseopt", "part"]),
    "UNMOUNT":   ("Unmount a mounted folder", 0, 0, "MOUNT_DIR", ["lazy"]),
}
TOOLS = [("wit", WIT), ("wwt", WWT), ("wdf", WDF), ("wfuse", WFUSE)]


# ------------------------------------------------------------------ state
class Runner:
    """Runs one process at a time and collects its output."""

    def __init__(self):
        self.lines = [""]
        self.lock = threading.Lock()
        self.proc = None
        self.busy = False
        self.scroll = False

    def write(self, text):
        with self.lock:
            parts = text.replace("\r\n", "\n").split("\n")
            for i, part in enumerate(parts):
                if i:
                    self.lines.append("")
                # carriage return = progress line rewrite
                if "\r" in part:
                    self.lines[-1] = part.rsplit("\r", 1)[1]
                else:
                    self.lines[-1] += part
            del self.lines[:-20000]
            self.scroll = True

    def log(self, msg):
        self.write(("\n" if self.lines[-1] else "") + msg + "\n")

    def run(self, argv, cwd):
        if self.busy:
            return
        self.busy = True
        self.log("$ " + quote(argv))

        def work():
            try:
                flags = subprocess.CREATE_NO_WINDOW if IS_WIN else 0
                self.proc = subprocess.Popen(argv, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                             stdin=subprocess.DEVNULL, creationflags=flags)
                while True:
                    chunk = self.proc.stdout.read1(4096)
                    if not chunk:
                        break
                    self.write(chunk.decode("utf-8", "replace"))
                code = self.proc.wait()
                self.log(f"[exit code {code}]\n")
            except Exception as e:
                self.log(f"[error] {e}\n")
            finally:
                self.proc = None
                self.busy = False

        threading.Thread(target=work, daemon=True).start()

    def task(self, name, fn):
        """Run a Python function in the background, logging into the console."""
        if self.busy:
            return
        self.busy = True
        self.log(f"== {name} ==")

        def work():
            try:
                fn()
                self.log("== done ==\n")
            except Exception as e:
                self.log(f"[error] {e}\n")
            finally:
                self.busy = False

        threading.Thread(target=work, daemon=True).start()

    def stop(self):
        if self.proc:
            self.proc.kill()
            self.log("[killed]")


def quote(argv):
    return subprocess.list2cmdline(argv) if IS_WIN else shlex.join(argv)


class CmdState:
    def __init__(self):
        self.sources = []
        self.args = ""
        self.extra = ""
        self.values = {}  # option key -> bool/str


class App:
    def __init__(self):
        self.cfg = {"tools_dir": wit_setup.BIN_DIR, "workdir": HERE, "font_scale": 1.0}
        try:
            with open(CONFIG) as f:
                self.cfg.update(json.load(f))
        except Exception:
            pass
        self.runner = Runner()
        self.selected = {t: next(iter(spec)) for t, spec in TOOLS}
        self.states = {}
        self.dialog = None  # (pfd dialog, callback)
        self.stop_mirror = False
        self.filter = ""

    def save(self):
        try:
            with open(CONFIG, "w") as f:
                json.dump(self.cfg, f, indent=2)
        except Exception:
            pass

    # ---------------------------------------------------------- tools
    def exe(self, tool):
        name = tool + (".exe" if IS_WIN else "")
        for d in (self.cfg["tools_dir"], wit_setup.BIN_DIR):
            p = os.path.join(d, name)
            if os.path.isfile(p):
                return p
        return shutil.which(tool)

    def state(self, tool, cmd):
        return self.states.setdefault((tool, cmd), CmdState())

    def build(self, tool, cmd):
        desc, src, dest, args_hint, opts = TOOLS_D[tool][cmd]
        st = self.state(tool, cmd)
        argv = [self.exe(tool) or tool]
        if tool == "wfuse":
            if cmd == "UNMOUNT":
                argv.append("--umount")
        else:
            argv.append(cmd)
        keys = list(opts) + (["dest", "DEST"] if dest else []) + [k for k in COMMON if k not in opts]
        for k in keys:
            flag, kind, *_ = OPTS[k]
            v = st.values.get(k)
            if not v:
                continue
            if kind == "bool":
                argv.append(flag)
            elif kind == "flags":
                argv.append(v)
            else:
                argv.append(f"{flag}={v}")
        argv += st.sources
        if st.args.strip():
            argv += shlex.split(st.args, posix=not IS_WIN)
        if st.extra.strip():
            argv += shlex.split(st.extra, posix=not IS_WIN)
        return argv

    # ---------------------------------------------------------- dialogs
    def open_dialog(self, dlg, callback):
        self.dialog = (dlg, callback)

    def poll_dialog(self):
        if self.dialog and self.dialog[0].ready():
            dlg, cb = self.dialog
            self.dialog = None
            res = dlg.result()
            if res:
                cb(res)

    # ---------------------------------------------------------- widgets
    def path_input(self, label, value, on_set=None, file_ok=True):
        imgui.push_id(label)
        imgui.align_text_to_frame_padding()
        imgui.text(label)
        imgui.same_line()
        imgui.set_next_item_width(-imgui.get_frame_height() * (7.5 if file_ok else 4.2))
        changed, value = imgui.input_text("##v", value or "")
        start = value or self.cfg["workdir"]
        if file_ok:
            imgui.same_line()
            if imgui.button("File..."):
                self.open_dialog(pfd.open_file("Select file", start, IMAGE_FILTER), lambda r: on_set(r[0]))
        imgui.same_line()
        if imgui.button("Folder..."):
            self.open_dialog(pfd.select_folder("Select folder", start), on_set)
        imgui.pop_id()
        return changed, value

    def option(self, st, key):
        flag, kind, label, sugg, tip = OPTS[key]
        v = st.values.get(key)
        imgui.push_id(key)
        if kind == "bool":
            _, st.values[key] = imgui.checkbox(label, bool(v))
        elif kind == "flags":
            imgui.set_next_item_width(220)
            if imgui.begin_combo(label, v or "(default)"):
                for s in sugg:
                    if imgui.selectable(s or "(default)", s == (v or ""))[0]:
                        st.values[key] = s
                imgui.end_combo()
        elif kind == "path":
            def setter(r, k=key):
                st.values[k] = r
            _, st.values[key] = self.path_input(label, v, on_set=setter)
        else:
            imgui.set_next_item_width(220)
            _, st.values[key] = imgui.input_text(label, v or "")
            if sugg:
                imgui.same_line()
                if imgui.begin_combo("##s", "", imgui.ComboFlags_.no_preview):
                    for s in sugg:
                        if imgui.selectable(s or "(clear)", s == v)[0]:
                            st.values[key] = s
                    imgui.end_combo()
        imgui.set_item_tooltip(f"{flag}  {tip}" if flag else tip)
        imgui.pop_id()

    # ---------------------------------------------------------- panels
    def tool_tab(self, tool, spec):
        exe = self.exe(tool)
        imgui.begin_child("cmds", imgui.ImVec2(250, 0), imgui.ChildFlags_.borders | imgui.ChildFlags_.resize_x)
        if not exe:
            imgui.text_colored(imgui.ImVec4(1, 0.4, 0.3, 1), f"{tool} not found!")
            imgui.text_wrapped("Go to 'Setup & Docs' tab.")
            imgui.separator()
        imgui.set_next_item_width(-1)
        _, self.filter = imgui.input_text_with_hint("##filter", "filter commands", self.filter)
        for cmd, (desc, *_r) in spec.items():
            if self.filter and self.filter.lower() not in (cmd + desc).lower():
                continue
            if imgui.selectable(cmd, self.selected[tool] == cmd)[0]:
                self.selected[tool] = cmd
            imgui.set_item_tooltip(desc)
        imgui.end_child()
        imgui.same_line()

        imgui.begin_child("form", imgui.ImVec2(0, 0), imgui.ChildFlags_.borders)
        cmd = self.selected[tool]
        desc, src, dest, args_hint, opts = spec[cmd]
        st = self.state(tool, cmd)
        imgui.text(f"{tool} {cmd}")
        imgui.same_line()
        imgui.text_disabled(desc)
        imgui.text_disabled(exe or "(executable not found, using PATH)")
        argv = self.build(tool, cmd)
        line = quote(argv)
        imgui.text_wrapped(line)
        busy = self.runner.busy
        imgui.begin_disabled(busy)
        if imgui.button(" Run ", imgui.ImVec2(110, 0)):
            self.runner.run(argv, self.cfg["workdir"])
        imgui.end_disabled()
        imgui.same_line()
        imgui.begin_disabled(not busy)
        if imgui.button("Stop"):
            self.runner.stop()
        imgui.end_disabled()
        imgui.same_line()
        if imgui.button("Copy command"):
            imgui.set_clipboard_text(line)
        imgui.same_line()
        imgui.begin_disabled(busy)
        if imgui.button("Help for command"):
            if tool == "wfuse":
                self.runner.run([exe or tool, "--help"], self.cfg["workdir"])
            else:
                self.runner.run([exe or tool, "HELP" if not cmd.startswith("+") else "+HELP", cmd.lstrip("+")],
                                self.cfg["workdir"])
        imgui.end_disabled()
        imgui.same_line()
        if imgui.button("Reset"):
            self.states.pop((tool, cmd), None)
        imgui.same_line()
        if imgui.button("Online docs"):
            webbrowser.open(wit_setup.SITE_ROOT)
        imgui.separator()
        imgui.begin_child("params")

        if src:
            imgui.text("Sources")
            for i, s in enumerate(list(st.sources)):
                imgui.push_id(i)
                if imgui.small_button("x"):
                    st.sources.pop(i)
                imgui.same_line()
                imgui.text(s)
                imgui.pop_id()
            if imgui.button("Add files..."):
                self.open_dialog(pfd.open_file("Add images", self.cfg["workdir"], IMAGE_FILTER, pfd.opt.multiselect),
                                 lambda r: st.sources.extend(r))
            imgui.same_line()
            if imgui.button("Add folder..."):
                self.open_dialog(pfd.select_folder("Add folder", self.cfg["workdir"]), lambda r: st.sources.append(r))
            imgui.same_line()
            if imgui.button("Clear"):
                st.sources.clear()
            imgui.spacing()

        if dest:
            def set_dest(r):
                st.values["dest"] = r
            _, st.values["dest"] = self.path_input("Destination (-d)", st.values.get("dest"), on_set=set_dest)
            imgui.set_item_tooltip("--dest: output file or folder. Use --DEST in options to create missing folders.")

        if args_hint is not None:
            imgui.set_next_item_width(-1)
            _, st.args = imgui.input_text_with_hint("##args", args_hint, st.args)
            imgui.set_item_tooltip("Positional arguments: " + args_hint)

        if imgui.collapsing_header("Options", imgui.TreeNodeFlags_.default_open):
            for k in opts:
                self.option(st, k)
            if dest:
                self.option(st, "DEST")
        if imgui.collapsing_header("Common options"):
            for k in COMMON:
                if k not in opts:
                    self.option(st, k)
        imgui.set_next_item_width(-1)
        _, st.extra = imgui.input_text_with_hint("##extra", "extra raw arguments (anything the tool accepts)", st.extra)

        imgui.end_child()
        imgui.end_child()

    def setup_tab(self):
        r = self.runner
        imgui.separator_text("Tools")
        for tool, _ in TOOLS:
            p = self.exe(tool)
            col = imgui.ImVec4(0.4, 1, 0.4, 1) if p else imgui.ImVec4(1, 0.4, 0.3, 1)
            imgui.text_colored(col, f"{tool:6} {p or 'not found'}")

        def set_dir(v):
            self.cfg["tools_dir"] = v
            self.save()
        ch, v = self.path_input("Tools folder", self.cfg["tools_dir"], on_set=set_dir, file_ok=False)
        if ch:
            set_dir(v)

        def set_wd(v):
            self.cfg["workdir"] = v
            self.save()
        ch, v = self.path_input("Working folder", self.cfg["workdir"], on_set=set_wd, file_ok=False)
        if ch:
            set_wd(v)

        imgui.begin_disabled(r.busy)
        if imgui.button("Download / update WIT from wit.wiimm.de"):
            r.task("Download WIT", lambda: wit_setup.download_tools(r.log))
        imgui.same_line()
        if imgui.button("Install from archive..."):
            def inst(res):
                r.task("Install archive", lambda: wit_setup.install_archive(res[0], r.log))
            self.open_dialog(pfd.open_file("WIT archive", HERE, ["Archives", "*.zip *.tar.gz *.tgz"]), inst)
        imgui.same_line()
        if imgui.button("Download titles.txt"):
            exe = self.exe("wit")
            if exe:
                r.run([exe, "GETTITLES"], self.cfg["tools_dir"])
        imgui.end_disabled()
        if imgui.button("Open tools folder"):
            open_path(self.cfg["tools_dir"])

        imgui.separator_text("Offline documentation (HTML copy of wit.wiimm.de)")
        index = os.path.join(wit_setup.SITE_DIR, "index.html")
        has = os.path.isfile(index)
        imgui.text_colored(imgui.ImVec4(0.4, 1, 0.4, 1) if has else imgui.ImVec4(1, 0.7, 0.3, 1),
                           index if has else "not downloaded yet")
        imgui.begin_disabled(r.busy)
        if imgui.button("Mirror website now"):
            self.stop_mirror = False
            r.task("Mirror wit.wiimm.de", lambda: wit_setup.mirror_site(r.log, stop=lambda: self.stop_mirror))
        imgui.end_disabled()
        imgui.same_line()
        if imgui.button("Stop mirror"):
            self.stop_mirror = True
        imgui.same_line()
        imgui.begin_disabled(not has)
        if imgui.button("Open offline docs"):
            webbrowser.open("file:///" + index.replace("\\", "/").lstrip("/"))
        imgui.end_disabled()
        imgui.same_line()
        if imgui.button("Open online docs"):
            webbrowser.open(wit_setup.SITE_ROOT)

        imgui.separator_text("Appearance")
        imgui.set_next_item_width(200)
        ch, self.cfg["font_scale"] = imgui.slider_float("UI scale", self.cfg.get("font_scale", 1.0), 0.75, 2.0)
        if imgui.is_item_deactivated_after_edit():
            self.save()

    def console(self):
        r = self.runner
        imgui.text("Output")
        imgui.same_line()
        if imgui.small_button("Clear"):
            with r.lock:
                r.lines = [""]
        imgui.same_line()
        if imgui.small_button("Copy all"):
            with r.lock:
                imgui.set_clipboard_text("\n".join(r.lines))
        if r.busy:
            imgui.same_line()
            imgui.text_colored(imgui.ImVec4(1, 0.8, 0.2, 1), "running...")
        imgui.begin_child("console", imgui.ImVec2(0, 0), imgui.ChildFlags_.borders,
                          imgui.WindowFlags_.horizontal_scrollbar)
        with r.lock:
            lines = list(r.lines)
            scroll, r.scroll = r.scroll, False
        clipper = imgui.ListClipper()
        clipper.begin(len(lines))
        while clipper.step():
            for i in range(clipper.display_start, clipper.display_end):
                imgui.text_unformatted(lines[i])
        if scroll and imgui.get_scroll_y() >= imgui.get_scroll_max_y() - 40:
            imgui.set_scroll_here_y(1.0)
        imgui.end_child()

    def gui(self):
        self.poll_dialog()
        imgui.get_style().font_scale_main = self.cfg.get("font_scale", 1.0)
        h = imgui.get_content_region_avail().y
        imgui.begin_child("top", imgui.ImVec2(0, h * 0.62), imgui.ChildFlags_.resize_y)
        if imgui.begin_tab_bar("tabs"):
            for tool, spec in TOOLS:
                if imgui.begin_tab_item(tool)[0]:
                    self.tool_tab(tool, spec)
                    imgui.end_tab_item()
            if imgui.begin_tab_item("Setup & Docs")[0]:
                self.setup_tab()
                imgui.end_tab_item()
            imgui.end_tab_bar()
        imgui.end_child()
        self.console()


TOOLS_D = dict(TOOLS)


def open_path(p):
    if IS_WIN:
        os.startfile(p)
    elif sys.platform == "darwin":
        subprocess.Popen(["open", p])
    else:
        subprocess.Popen(["xdg-open", p])


def main():
    app = App()
    if not any(app.exe(t) for t, _ in TOOLS):
        app.runner.log("WIT tools not found. Open 'Setup & Docs' and click 'Download / update WIT'.")
    rp = hello_imgui.RunnerParams()
    rp.app_window_params.window_title = "WIT GUI - Wiimms ISO Tools"
    rp.app_window_params.window_geometry.size = (1280, 860)
    rp.imgui_window_params.default_imgui_window_type = hello_imgui.DefaultImGuiWindowType.provide_full_screen_window
    rp.fps_idling.fps_idle = 10
    rp.ini_folder_type = hello_imgui.IniFolderType.app_user_config_folder
    rp.callbacks.show_gui = app.gui
    hello_imgui.run(rp)


if __name__ == "__main__":
    main()
