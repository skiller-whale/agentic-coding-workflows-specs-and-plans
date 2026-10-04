"""The dispatch pane: shows one feature card at a time. n for the next card, p for the previous.

Session plumbing, not part of the exercise. The cards are in cards.txt, one per line. Which card is
on screen, and the furthest reached, are kept in ~/.city-session/dispatch.json, where the coach
summary reads them, so they survive the pane restarting.
"""

import json
import os
import shutil
import signal
import sys
import termios
import textwrap
import tty
from pathlib import Path

CARDS = [line.strip() for line in (Path(__file__).parent / "cards.txt").read_text().splitlines() if line.strip()]
STATE = Path.home() / ".city-session" / "dispatch.json"

BOLD, DIM, YELLOW, RESET = "\x1b[1m", "\x1b[2m", "\x1b[33m", "\x1b[0m"


def load():
    try:
        state = json.loads(STATE.read_text())
        return max(0, min(int(state["current"]), len(CARDS) - 1)), max(0, min(int(state["furthest"]), len(CARDS) - 1))
    except (OSError, ValueError, KeyError, TypeError):
        return 0, 0


def save(current, furthest):
    STATE.parent.mkdir(parents=True, exist_ok=True)
    tmp = STATE.with_suffix(".tmp")
    tmp.write_text(json.dumps({"current": current, "furthest": furthest, "total": len(CARDS)}))
    os.replace(tmp, STATE)


def draw(current):
    cols = shutil.get_terminal_size((60, 8)).columns
    width = max(20, cols - 4)
    lines = [f"{YELLOW}{BOLD}Feature {current + 1} of {len(CARDS)}{RESET}", ""]
    lines += [f"{BOLD}{line}{RESET}" for line in textwrap.wrap(CARDS[current], width)]
    keys = []
    if current + 1 < len(CARDS):
        keys.append("n next")
    if current > 0:
        keys.append("p previous")
    lines += ["", f"{DIM}{'  ·  '.join(keys)}{RESET}"]
    sys.stdout.write("\x1b[2J\x1b[H\x1b[?25l" + "\r\n".join("  " + line for line in lines))
    sys.stdout.flush()


def main():
    current, furthest = load()
    save(current, furthest)
    old = termios.tcgetattr(sys.stdin)
    signal.signal(signal.SIGWINCH, lambda *_: draw(current))
    try:
        tty.setcbreak(sys.stdin.fileno())
        while True:
            draw(current)
            key = sys.stdin.read(1)
            if key in ("n", "N", " ") and current + 1 < len(CARDS):
                current += 1
            elif key in ("p", "P") and current > 0:
                current -= 1
            else:
                continue
            furthest = max(furthest, current)
            save(current, furthest)
    except KeyboardInterrupt:
        pass
    finally:
        termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old)
        sys.stdout.write("\x1b[?25h\x1b[0m\n")


if __name__ == "__main__":
    main()
