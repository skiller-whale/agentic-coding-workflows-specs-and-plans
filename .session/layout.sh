#!/usr/bin/env bash
# Opens the session's tmux layout, or re-attaches to it if it is already running:
# Claude Code on the left; on the right, the city app over a terminal.
# It is the editor's terminal profile, so it can start before setup has finished.
set -eu
if command -v wait_for_startup >/dev/null; then wait_for_startup; fi
cd "$(dirname "$0")/.."
export PATH="$HOME/.local/bin:$PATH"

SESSION=city
if ! tmux has-session -t "$SESSION" 2>/dev/null; then
  tmux new-session -d -s "$SESSION" -x "$(tput cols)" -y "$(tput lines)"
  tmux split-window -h -t "$SESSION:0.0" -l 50%
  tmux split-window -v -t "$SESSION:0.1" -l 50%
  tmux select-pane -t "$SESSION:0.0" -T "Claude Code"
  tmux select-pane -t "$SESSION:0.1" -T "City"
  tmux select-pane -t "$SESSION:0.2" -T "Terminal"
  tmux send-keys -t "$SESSION:0.0" "claude" Enter
  tmux send-keys -t "$SESSION:0.1" "python3 .session/run_city.py" Enter
  tmux select-pane -t "$SESSION:0.0"
  # Put the halves back whenever the window changes size: reloading the editor
  # briefly gives the terminal a tiny size, and tmux would keep the squashed panes.
  tmux set-hook -t "$SESSION" window-resized \
    "resize-pane -t $SESSION:0.0 -x 50% ; resize-pane -t $SESSION:0.1 -y 50%"
fi
# -d detaches any earlier client (a terminal from before an editor reload), which
# would otherwise keep the window at its own size.
# The coach's watch server and CITY.md summary run in a hidden tmux session. Processes that setup.sh
# starts in the background don't outlive the VM's startup step, but this session lasts as long as
# the learner's. Each starts only if it isn't already running.
if ! tmux has-session -t city-services 2>/dev/null; then
  tmux new-session -d -s city-services -n services
fi
pgrep -u "$(id -u)" -f "\.session/watch_server\.py" >/dev/null ||
  tmux new-window -d -t city-services "python3 $PWD/.session/watch_server.py 2>&1 | tee -a $HOME/.city-session/watch_server.log"
pgrep -u "$(id -u)" -f "\.session/coach_summary\.py" >/dev/null ||
  tmux new-window -d -t city-services "python3 $PWD/.session/coach_summary.py 2>&1 | tee -a $HOME/.city-session/coach_summary.log"

exec tmux attach -d -t "$SESSION"
