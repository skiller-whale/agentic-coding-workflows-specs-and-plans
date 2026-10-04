"""Writes CITY.md for the coach: a link to the live read-only watch and a summary of where the learner is.

Session plumbing, not part of the exercise. Started by setup.sh and left running. Every few seconds it
reads the dispatch pane's state, the openspec/ folder, the test results and Claude Code's transcript,
and rewrites ~/.city-session/coach/CITY.md if anything changed. The learnersync container watches that
folder and sends the file to Train, where it appears in the coach's "Recently edited files".
"""

import json
import os
import re
import subprocess
import time
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SESSION_DIR = Path.home() / ".city-session"
OUT = SESSION_DIR / "coach" / "CITY.md"
CARDS = [line.strip() for line in (Path(__file__).parent / "cards.txt").read_text().splitlines() if line.strip()]
WATCH_PORT = os.environ.get("CITY_WATCH_PORT", "1001")  # the exposed port, forwarded to the watch server
INTERVAL = 3


def watch_url():
    """The hosted environment's port proxy serves port N of the VM <id>.<domain> at <id>-port-N.<domain>."""
    host = os.environ.get("SW_HOSTNAME", "")
    if "." not in host:
        return f"http://localhost:{WATCH_PORT}/"
    vm, domain = host.split(".", 1)
    return f"https://{vm}-port-{WATCH_PORT}.{domain}/"


def card_line():
    try:
        state = json.loads((SESSION_DIR / "dispatch.json").read_text())
        current, furthest = int(state["current"]), int(state["furthest"])
    except (OSError, ValueError, KeyError, TypeError):
        return "Feature card: not opened yet"
    text = CARDS[current] if 0 <= current < len(CARDS) else "?"
    furthest_note = f" (furthest reached: {furthest + 1})" if furthest != current else ""
    return f"Feature card: {current + 1} of {len(CARDS)}{furthest_note}. {text}"


def requirement_count(spec):
    try:
        return len(re.findall(r"^### Requirement:", spec.read_text(), re.M))
    except OSError:
        return 0


def openspec_lines():
    changes_dir = REPO / "openspec" / "changes"
    lines = []
    active = sorted(p for p in changes_dir.glob("*") if p.is_dir() and p.name != "archive")
    if not active:
        lines.append("Change in flight: none")
    for change in active:
        parts = []
        for name in ("proposal", "design"):
            parts.append(f"{name} {'✓' if (change / f'{name}.md').exists() else '–'}")
        parts.append(f"specs {'✓' if any(change.glob('specs/*/spec.md')) else '–'}")
        tasks = change / "tasks.md"
        if tasks.exists():
            text = tasks.read_text()
            done = len(re.findall(r"^\s*- \[x\]", text, re.M | re.I))
            total = done + len(re.findall(r"^\s*- \[ \]", text, re.M))
            parts.append(f"tasks {done}/{total}")
        else:
            parts.append("tasks –")
        lines.append(f"Change in flight: {change.name}")
        lines.append("  " + "   ".join(parts))
    archived = sorted((changes_dir / "archive").glob("*"))
    names = [re.sub(r"^\d{4}-\d{2}-\d{2}-", "", p.name) for p in archived if p.is_dir()]
    lines.append(f"Archived: {', '.join(names) if names else 'none yet'}")
    specs = sorted((REPO / "openspec" / "specs").glob("*/spec.md"))
    spec_parts = [f"{s.parent.name} ({requirement_count(s)})" for s in specs]
    lines.append(f"Specs (requirements): {', '.join(spec_parts) if spec_parts else 'none'}")
    return lines


_tests = {"key": None, "line": "Tests: not run yet"}


def code_key():
    files = []
    for path in REPO.rglob("*.py"):
        rel = path.relative_to(REPO)
        if rel.parts[0].startswith("."):
            continue
        try:
            files.append((str(rel), path.stat().st_mtime))
        except OSError:
            pass
    return tuple(sorted(files))


def tests_line():
    """Re-runs the tests only when a Python file has changed since the last run."""
    key = code_key()
    if key != _tests["key"]:
        _tests["key"] = key
        try:
            result = subprocess.run(
                ["python3", "-m", "pytest", "-q", "-p", "no:cacheprovider"],
                cwd=REPO, capture_output=True, text=True, timeout=120,
            )
            summary = [l for l in result.stdout.splitlines() if re.search(r"\b(passed|failed|error|no tests ran)\b", l)]
            last = summary[-1].strip("= ").strip() if summary else "no result"
            last = re.sub(r" in [\d.]+s.*$", "", last)
            _tests["line"] = f"Tests: {last} (at {datetime.now():%H:%M})"
        except subprocess.TimeoutExpired:
            _tests["line"] = "Tests: still running after two minutes"
    return _tests["line"]


def transcript_dir():
    return Path.home() / ".claude" / "projects" / re.sub(r"[^A-Za-z0-9]", "-", str(REPO))


def prompt_text(content):
    if isinstance(content, list):
        if any(isinstance(c, dict) and c.get("type") == "tool_result" for c in content):
            return None
        content = " ".join(c.get("text", "") for c in content if isinstance(c, dict) and c.get("type") == "text")
    if not isinstance(content, str) or not content.strip():
        return None
    command = re.search(r"<command-name>(.*?)</command-name>", content)
    if command:
        args = re.search(r"<command-args>(.*?)</command-args>", content, re.S)
        return f"{command.group(1)} {args.group(1).strip() if args else ''}".strip()
    if content.lstrip().startswith("<"):
        return None
    return content.strip()


def last_prompt_line():
    files = sorted(transcript_dir().glob("*.jsonl"), key=lambda p: p.stat().st_mtime)
    for path in reversed(files):
        try:
            lines = path.read_text().splitlines()
        except OSError:
            continue
        for raw in reversed(lines):
            try:
                entry = json.loads(raw)
            except ValueError:
                continue
            if entry.get("type") != "user" or entry.get("isMeta"):
                continue
            text = prompt_text(entry.get("message", {}).get("content"))
            if text:
                text = " ".join(text.split())
                if len(text) > 200:
                    text = text[:197] + "..."
                when = entry.get("timestamp", "")
                try:
                    when = datetime.fromisoformat(when.replace("Z", "+00:00")).astimezone().strftime("%H:%M")
                except ValueError:
                    when = ""
                return f'Last prompt{f" ({when})" if when else ""}: "{text}"'
    return "Last prompt: none yet"


def summary():
    lines = [
        "# The learner's city",
        "",
        f"Watch live, read-only: {watch_url()}",
        "",
        card_line(),
        "",
        *openspec_lines(),
        tests_line(),
        last_prompt_line(),
    ]
    return "\n".join(lines) + "\n"


def main():
    OUT.parent.mkdir(parents=True, exist_ok=True)
    previous = None
    while True:
        try:
            body = summary()
            if body != previous:
                tmp = OUT.with_suffix(".tmp")
                tmp.write_text(body + f"\nUpdated {datetime.now():%H:%M:%S}\n")
                os.replace(tmp, OUT)
                previous = body
        except Exception as error:  # keep going: a half-written file mid-change shouldn't stop the summary
            print(f"coach summary: {error!r}", flush=True)
        time.sleep(INTERVAL)


if __name__ == "__main__":
    main()
