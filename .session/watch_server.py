"""The coach's live, read-only view of the learner's tmux session and repo, served on port 1001.

Session plumbing, not part of the exercise. Started by setup.sh and left running. The page asks for
/screen a couple of times a second; each answer is the layout of the tmux window and the contents of
every pane (from `tmux capture-pane`, colours included). The page draws the panes and scales the whole
screen to fit the coach's browser, whatever size the learner's window is. Nothing is ever sent to
tmux, so the coach can only watch.

The page's Files view lists the repo (/files) and shows one file at a time (/file?path=...), read-only.
It hides the same session plumbing the learner's editor hides.
"""

import html
import json
import os
import re
import subprocess
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

SESSION = "city"
PORT = int(os.environ.get("CITY_WATCH_PORT", "1001"))
TMUX = str(Path.home() / ".local" / "bin" / "tmux")

# The 16 standard colours, close to the editor's dark terminal theme.
BASIC = ["#000000", "#cd3131", "#0dbc79", "#e5e510", "#2472c8", "#bc3fbc", "#11a8cd", "#e5e5e5",
         "#666666", "#f14c4c", "#23d18b", "#f5f543", "#3b8eea", "#d670d6", "#29b8db", "#ffffff"]


def colour256(n):
    if n < 16:
        return BASIC[n]
    if n < 232:
        n -= 16
        steps = [0, 95, 135, 175, 215, 255]
        return "#%02x%02x%02x" % (steps[n // 36], steps[(n // 6) % 6], steps[n % 6])
    level = 8 + (n - 232) * 10
    return "#%02x%02x%02x" % (level, level, level)


SGR = re.compile(r"\x1b\[([0-9;:]*)m")


def ansi_to_html(line):
    """One captured line, with SGR colour codes, as HTML spans."""
    out, style = [], {}
    pos = 0

    def emit(text):
        if not text:
            return
        fg, bg = style.get("fg"), style.get("bg")
        if style.get("reverse"):
            fg, bg = bg or "var(--bg)", fg or "var(--fg)"
        css = []
        if fg:
            css.append(f"color:{fg}")
        if bg:
            css.append(f"background:{bg}")
        if style.get("bold"):
            css.append("font-weight:700")
        if style.get("dim"):
            css.append("opacity:.6")
        if style.get("italic"):
            css.append("font-style:italic")
        if style.get("underline"):
            css.append("text-decoration:underline")
        text = html.escape(text)
        out.append(f'<span style="{";".join(css)}">{text}</span>' if css else text)

    for m in SGR.finditer(line):
        emit(line[pos:m.start()])
        pos = m.end()
        codes = [int(c) if c.isdigit() else 0 for c in re.split(r"[;:]", m.group(1) or "0")]
        i = 0
        while i < len(codes):
            c = codes[i]
            if c == 0:
                style = {}
            elif c == 1:
                style["bold"] = True
            elif c == 2:
                style["dim"] = True
            elif c == 3:
                style["italic"] = True
            elif c == 4:
                style["underline"] = True
            elif c == 7:
                style["reverse"] = True
            elif c == 22:
                style.pop("bold", None)
                style.pop("dim", None)
            elif c == 23:
                style.pop("italic", None)
            elif c == 24:
                style.pop("underline", None)
            elif c == 27:
                style.pop("reverse", None)
            elif 30 <= c <= 37 or 90 <= c <= 97:
                style["fg"] = BASIC[c - 30 if c < 90 else c - 82]
            elif 40 <= c <= 47 or 100 <= c <= 107:
                style["bg"] = BASIC[c - 40 if c < 100 else c - 92]
            elif c == 39:
                style.pop("fg", None)
            elif c == 49:
                style.pop("bg", None)
            elif c in (38, 48) and i + 1 < len(codes):
                key = "fg" if c == 38 else "bg"
                if codes[i + 1] == 5 and i + 2 < len(codes):
                    style[key] = colour256(codes[i + 2])
                    i += 2
                elif codes[i + 1] == 2 and i + 4 < len(codes):
                    style[key] = "#%02x%02x%02x" % tuple(codes[i + 2:i + 5])
                    i += 4
            i += 1
    emit(line[pos:])
    return "".join(out)


def tmux(*args):
    return subprocess.run([TMUX, *args], capture_output=True, text=True, timeout=5)


def screen():
    window = tmux("display-message", "-p", "-t", SESSION, "#{window_width} #{window_height}")
    if window.returncode != 0:
        return {"waiting": True}
    width, height = (int(x) for x in window.stdout.split())
    listing = tmux("list-panes", "-t", SESSION, "-F",
                   "#{pane_id}\t#{pane_left}\t#{pane_top}\t#{pane_width}\t#{pane_height}\t#{pane_active}\t#{pane_title}")
    panes = []
    for row in listing.stdout.splitlines():
        pane_id, left, top, w, h, active, title = row.split("\t", 6)
        captured = tmux("capture-pane", "-p", "-e", "-N", "-t", pane_id).stdout.split("\n")[: int(h)]
        panes.append({"left": int(left), "top": int(top), "width": int(w), "height": int(h),
                      "active": active == "1", "title": title, "lines": [ansi_to_html(l) for l in captured]})
    return {"width": width, "height": height, "panes": panes}


REPO = Path(__file__).resolve().parent.parent
# Plumbing the coach doesn't need, matching the learner's files.exclude (setup.sh), plus .git and the
# OpenSpec workflow files under .claude/.
HIDDEN_PARTS = {".git", ".session", ".vscode", ".claude", "__pycache__", ".pytest_cache"}
HIDDEN_FILES = {"setup.sh", ".curriculumconfig", "docker-compose.yml", "attendance_id", ".gitkeep"}
MAX_FILE_BYTES = 512 * 1024


def visible(rel):
    return not (set(rel.parts) & HIDDEN_PARTS) and rel.name not in HIDDEN_FILES


def files():
    """Every visible file in the repo, with when it last changed."""
    entries = []
    for path in sorted(REPO.rglob("*")):
        rel = path.relative_to(REPO)
        if path.is_file() and visible(rel):
            try:
                entries.append({"path": rel.as_posix(), "mtime": path.stat().st_mtime})
            except OSError:
                pass
    return {"now": time.time(), "files": entries}


def file_contents(rel_path):
    """One visible file's text, or None if the path is outside the repo, hidden or not a file."""
    try:
        path = (REPO / rel_path).resolve()
        rel = path.relative_to(REPO)
    except (ValueError, OSError):
        return None
    if not path.is_file() or not visible(rel):
        return None
    data = path.read_bytes()[:MAX_FILE_BYTES]
    return {"path": rel.as_posix(), "mtime": path.stat().st_mtime,
            "truncated": path.stat().st_size > MAX_FILE_BYTES, "text": data.decode("utf-8", errors="replace")}


PAGE = (Path(__file__).parent / "watch.html").read_bytes()


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        url = urlparse(self.path)
        if url.path == "/screen":
            body, kind = json.dumps(screen()).encode(), "application/json"
        elif url.path == "/files":
            body, kind = json.dumps(files()).encode(), "application/json"
        elif url.path == "/file":
            found = file_contents(parse_qs(url.query).get("path", [""])[0])
            if found is None:
                self.send_error(404)
                return
            body, kind = json.dumps(found).encode(), "application/json"
        elif url.path in ("/", "/index.html"):
            body, kind = PAGE, "text/html; charset=utf-8"
        else:
            self.send_error(404)
            return
        self.send_response(200)
        self.send_header("Content-Type", kind)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


if __name__ == "__main__":
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
