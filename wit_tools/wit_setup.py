#!/usr/bin/env python3
"""Download Wiimms ISO Tools binaries and mirror https://wit.wiimm.de for offline use.

Usage:
    python wit_setup.py tools        # download + extract binaries for this OS into ./bin
    python wit_setup.py site         # mirror the website into ./site
    python wit_setup.py all
    python wit_setup.py archive FILE # install from an already downloaded .zip/.tar.gz
"""
import html
import os
import posixpath
import re
import shutil
import sys
import tarfile
import time
import urllib.parse
import urllib.request
import zipfile
from html.parser import HTMLParser

HERE = os.path.dirname(os.path.abspath(__file__))
BIN_DIR = os.path.join(HERE, "bin")
SITE_DIR = os.path.join(HERE, "site")
SITE_ROOT = "https://wit.wiimm.de/"
DOWNLOAD_PAGES = [SITE_ROOT + "download.html", SITE_ROOT + "download", SITE_ROOT]
TOOL_NAMES = ("wit", "wwt", "wdf", "wfuse")
UA = {"User-Agent": "Mozilla/5.0 (wit-gui offline mirror)"}


def log(msg, out=None):
    (out or print)(msg)


def fetch(url, timeout=60):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read(), r.headers.get_content_type(), r.geturl()


class LinkParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []

    def handle_starttag(self, tag, attrs):
        for k, v in attrs:
            if k in ("href", "src") and v:
                self.links.append(v)
            elif k == "srcset" and v:
                self.links += [p.strip().split(" ")[0] for p in v.split(",") if p.strip()]


def extract_links(data, base):
    p = LinkParser()
    try:
        p.feed(data.decode("utf-8", "replace"))
    except Exception:
        pass
    text = data.decode("utf-8", "replace")
    css_urls = re.findall(r"url\(\s*['\"]?([^'\")]+)['\"]?\s*\)", text)
    return [urllib.parse.urljoin(base, html.unescape(l)) for l in p.links + css_urls]


# ---------------------------------------------------------------- binaries

def platform_key():
    if sys.platform.startswith("win") or sys.platform == "cygwin":
        return "windows"
    if sys.platform == "darwin":
        return "mac"
    return "linux"


def score_archive(url, plat):
    name = url.rsplit("/", 1)[-1].lower()
    if not name.startswith("wit-") or not re.search(r"\.(zip|tar\.gz|tgz)$", name):
        return -1
    if plat == "windows":
        return 3 if "cygwin64" in name else 2 if "cygwin" in name else -1
    if plat == "mac":
        return 3 if "mac" in name else -1
    if "cygwin" in name or "mac" in name or "src" in name:
        return -1
    return 3 if "x86_64" in name or "x86-64" in name else 1 if "i386" in name else -1


def find_archive_url(out=None):
    plat = platform_key()
    best = (-1, None)
    for page in DOWNLOAD_PAGES:
        try:
            data, _, real = fetch(page)
        except Exception as e:
            log(f"  {page}: {e}", out)
            continue
        for link in extract_links(data, real):
            s = score_archive(link, plat)
            if s > best[0]:
                best = (s, link)
        if best[1]:
            break
    return best[1]


def install_archive(path, out=None):
    dest = os.path.join(BIN_DIR, "_extract")
    shutil.rmtree(dest, ignore_errors=True)
    os.makedirs(dest)
    if path.lower().endswith(".zip"):
        with zipfile.ZipFile(path) as z:
            z.extractall(dest)
    else:
        with tarfile.open(path) as t:
            if hasattr(tarfile, "data_filter"):
                t.extractall(dest, filter="data")
            else:
                t.extractall(dest)
    # Find the folder holding wit / wit.exe and copy its contents flat into bin/
    found = None
    for root, _, files in os.walk(dest):
        if "wit.exe" in files or "wit" in files:
            found = root
            break
    if not found:
        raise RuntimeError("wit executable not found in archive")
    for f in os.listdir(found):
        src = os.path.join(found, f)
        if os.path.isfile(src):
            shutil.copy2(src, os.path.join(BIN_DIR, f))
            if not f.lower().endswith((".dll", ".txt")):
                os.chmod(os.path.join(BIN_DIR, f), 0o755)
    # Keep docs/extra files shipped with the archive
    docs = os.path.join(BIN_DIR, "package")
    shutil.rmtree(docs, ignore_errors=True)
    shutil.move(dest, docs)
    log(f"Installed tools into {BIN_DIR}", out)
    return BIN_DIR


def download_tools(out=None):
    os.makedirs(BIN_DIR, exist_ok=True)
    log("Looking for WIT download link...", out)
    url = find_archive_url(out)
    if not url:
        raise RuntimeError("No archive for this OS found on wit.wiimm.de. "
                           "Download manually and use 'Install from archive'.")
    log(f"Downloading {url}", out)
    data, _, _ = fetch(url, timeout=300)
    archive = os.path.join(BIN_DIR, url.rsplit("/", 1)[-1])
    with open(archive, "wb") as f:
        f.write(data)
    install_archive(archive, out)
    os.remove(archive)
    return BIN_DIR


# ---------------------------------------------------------------- site mirror

def local_path_for(url):
    p = urllib.parse.urlsplit(url)
    path = urllib.parse.unquote(p.path) or "/"
    if path.endswith("/"):
        path += "index.html"
    if p.query:
        root, ext = posixpath.splitext(path)
        path = f"{root}_{re.sub(r'[^A-Za-z0-9]+', '_', p.query)}{ext}"
    return path.lstrip("/")


def mirror_site(out=None, max_files=5000, delay=0.15, stop=None):
    host = urllib.parse.urlsplit(SITE_ROOT).netloc
    queue, seen, saved = [SITE_ROOT], {SITE_ROOT}, {}
    while queue and len(saved) < max_files:
        if stop and stop():
            log("Mirror stopped.", out)
            break
        url = queue.pop(0)
        try:
            data, ctype, real = fetch(url)
        except Exception as e:
            log(f"  skip {url}: {e}", out)
            continue
        rel = local_path_for(real)
        if ctype == "text/html" and not rel.lower().endswith((".html", ".htm")):
            rel += ".html"
        saved[url] = saved[real] = (rel, ctype, data)
        log(f"[{len(saved)}] {rel}", out)
        if ctype in ("text/html", "text/css"):
            for link in extract_links(data, real):
                link = urllib.parse.urldefrag(link)[0]
                sp = urllib.parse.urlsplit(link)
                if sp.scheme in ("http", "https") and sp.netloc == host and link not in seen:
                    if re.search(r"\.(zip|gz|tgz|bz2|xz|7z|exe|dmg|iso|wbfs)$", sp.path, re.I):
                        continue  # don't mirror binaries into the docs
                    seen.add(link)
                    queue.append(link)
        time.sleep(delay)

    url_to_rel = {u: v[0] for u, v in saved.items()}

    def rewrite(text, page_rel, base):
        def sub(m):
            raw = html.unescape(m.group(2))
            full, frag = urllib.parse.urldefrag(urllib.parse.urljoin(base, raw))
            target = url_to_rel.get(full)
            if not target:
                return m.group(0)
            r = posixpath.relpath(target, posixpath.dirname(page_rel) or ".")
            return m.group(1) + html.escape(r + ("#" + frag if frag else ""), quote=True) + m.group(3)
        text = re.sub(r"""((?:href|src)\s*=\s*["'])([^"']+)(["'])""", sub, text, flags=re.I)
        return re.sub(r"""(url\(\s*['"]?)([^'")]+)(['"]?\s*\))""", sub, text)

    written = set()
    for url, (rel, ctype, data) in saved.items():
        if rel in written:
            continue
        written.add(rel)
        dst = os.path.join(SITE_DIR, *rel.split("/"))
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        if ctype in ("text/html", "text/css"):
            data = rewrite(data.decode("utf-8", "replace"), rel, url).encode("utf-8")
        with open(dst, "wb") as f:
            f.write(data)
    log(f"Mirrored {len(written)} files into {SITE_DIR}", out)
    return os.path.join(SITE_DIR, "index.html")


def main(argv):
    cmd = argv[1] if len(argv) > 1 else "all"
    if cmd in ("tools", "all"):
        download_tools()
    if cmd in ("site", "all"):
        mirror_site()
    if cmd == "archive":
        install_archive(argv[2])


if __name__ == "__main__":
    main(sys.argv)
