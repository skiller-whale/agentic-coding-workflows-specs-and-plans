"""Runs the city app and restarts it whenever a .py or .txt file in the repo changes.

Session plumbing for the right-hand pane, not part of the exercise. If the app
exits (q, or a crash), it waits for the next change, or Enter, to start it again.
"""

import os
import select
import signal
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
# Leaves the alternate screen and turns off mouse reporting, in case the app was
# killed before it could tidy up the terminal itself.
RESET = "\x1b[?1049l\x1b[?1000l\x1b[?1002l\x1b[?1003l\x1b[?1006l\x1b[?25h\x1b[0m"
CLEAR = "\x1b[2J\x1b[H"


def snapshot():
    files = {}
    for path in REPO.rglob("*"):
        rel = path.relative_to(REPO)
        if rel.parts[0].startswith(".") or rel.parts[0] in ("tests", "openspec"):
            continue
        if path.suffix in (".py", ".txt") and path.is_file():
            files[path] = path.stat().st_mtime
    return files


def stop(proc):
    if proc.poll() is None:
        proc.send_signal(signal.SIGTERM)
        try:
            proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()


def tidy_terminal(clear):
    subprocess.run(["stty", "sane"], stderr=subprocess.DEVNULL)
    sys.stdout.write(RESET + (CLEAR if clear else ""))
    sys.stdout.flush()


def main():
    os.chdir(REPO)
    while True:
        seen = snapshot()
        proc = subprocess.Popen([sys.executable, "app.py"])
        while proc.poll() is None and snapshot() == seen:
            time.sleep(0.5)
        changed = proc.poll() is None
        stop(proc)
        # Keep the screen after a crash, so its traceback stays readable.
        tidy_terminal(clear=changed)
        if changed:
            continue
        print(f"\nThe city app exited (code {proc.returncode}).")
        print("It restarts when the code changes, or press Enter to start it now.")
        while snapshot() == seen:
            ready, _, _ = select.select([sys.stdin], [], [], 0.5)
            if ready:
                sys.stdin.readline()
                break


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
