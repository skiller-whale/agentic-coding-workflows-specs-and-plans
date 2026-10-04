#!/usr/bin/env bash
# Opens the session's tmux layout, or re-attaches to it if it is already running:
# Claude Code on the left; on the right, the city app, the dispatch pane (feature cards) and a terminal.
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
  tmux split-window -v -t "$SESSION:0.2" -l 60%
  tmux select-pane -t "$SESSION:0.0" -T "Claude Code"
  tmux select-pane -t "$SESSION:0.1" -T "City"
  tmux select-pane -t "$SESSION:0.2" -T "Dispatch"
  tmux select-pane -t "$SESSION:0.3" -T "Terminal"
  tmux send-keys -t "$SESSION:0.0" "claude" Enter
  tmux send-keys -t "$SESSION:0.1" "python3 .session/run_city.py" Enter
  tmux send-keys -t "$SESSION:0.2" "clear; python3 .session/dispatch.py" Enter
  tmux resize-pane -t "$SESSION:0.2" -y 8
  tmux select-pane -t "$SESSION:0.0"
  # Put the halves back whenever the window changes size: reloading the editor
  # briefly gives the terminal a tiny size, and tmux would keep the squashed panes.
  tmux set-hook -t "$SESSION" window-resized \
    "resize-pane -t $SESSION:0.0 -x 50% ; resize-pane -t $SESSION:0.1 -y 50% ; resize-pane -t $SESSION:0.2 -y 8"
fi
# -d detaches any earlier client (a terminal from before an editor reload), which
# would otherwise keep the window at its own size.
exec tmux attach -d -t "$SESSION"
