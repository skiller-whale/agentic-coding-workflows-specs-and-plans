#!/usr/bin/env bash
# Idempotent hosted-environment setup for the specs_and_plans module (city prototype).
#
# Runs on every VM boot (startup_commands re-run on reboot), so almost every
# step below is guarded: a learner may already be mid-way through an
# OpenSpec change, have their own git history, or have edited
# openspec/config.yaml, and none of that should be clobbered.
#
# Invoked as: bash "$HOME/$DEFAULT_FOLDER/setup.sh" from exercise_config.yaml's
# startup_commands, AFTER the shared `!include* ai/hle_claude_setup.yaml`
# commands (AWS credentials, Bedrock env in .zshrc, the extension's .vscode
# settings, .claude.json theme, the CLI install). DEFAULT_FOLDER and
# SW_ATTENDANCE_ID are prefixed onto that one simple command by the harness
# (Train/the emulator) — so both reach this script as real, inherited
# environment variables. Nothing below needs its own env-var prefix.
set -euo pipefail

REPO_DIR="$HOME/$DEFAULT_FOLDER"
OPENSPEC_VERSION="1.14.0"
TMUX_VERSION="3.7c"
NODE_VERSION="24"

# --- Shell extras --------------------------------------------------------
# The shared ai/hle_claude_setup.yaml (spliced into startup_commands before
# this script) rewrites ~/.zshrc with the Bedrock/model exports every boot.
# This appends what the module needs on top: LANG/LC_ALL first (a fresh
# terminal on the real AMI can hit `character not in range` on non-ASCII
# PROMPT content, which aborts sourcing before anything after it runs — see
# the agent_memory module), DISABLE_AUTOUPDATER (keeps the pinned CLI
# pinned), DO_NOT_TRACK (OpenSpec's documented telemetry opt-out), the
# `python` alias, and ~/.local/bin on PATH (where the Claude Code CLI
# installs). `openspec` itself resolves via mise's own shell activation,
# already baked into ~/.zshrc / ~/.bashrc by the base image (`mise
# activate`), once `mise use -g node@<version>` below has made it the
# global default — that covers editor terminals and Claude Code's Bash
# tool the same way it already does for other agentic modules (see
# ai/customising_agents/custom_tools_and_mcp). Guarded by a marker so a
# re-run without the shared rewrite doesn't duplicate it.
if ! grep -q '# specs_and_plans shell extras' "$HOME/.zshrc" 2>/dev/null; then
  cat << EOF >> "$HOME/.zshrc"

# specs_and_plans shell extras
export LANG=C.UTF-8
export LC_ALL=C.UTF-8
export DISABLE_AUTOUPDATER=1
export DO_NOT_TRACK=1
export PATH="\$HOME/.local/bin:\$PATH"
alias python='python3'
EOF
fi

# --- Every editor terminal opens the tmux layout ---------------------------
# An interactive zsh in an editor terminal, not already inside tmux, hands
# over to .session/layout.sh, which attaches to the layout (taking over from
# any earlier terminal). The shells inside the tmux panes have $TMUX set, so
# they stay ordinary shells. The extension opens a terminal on every page
# load because the config has no commandGroups (with commandGroups it skips a
# group whose old terminal is still running, and the editor does not always
# put that terminal back on screen after a reload). Done in .zshrc rather
# than as an editor terminal profile, which a reload sometimes ignores.
# Separate marker from the block above so an existing VM gets it too.
if ! grep -q '# specs_and_plans tmux layout' "$HOME/.zshrc" 2>/dev/null; then
  cat << EOF >> "$HOME/.zshrc"

# specs_and_plans tmux layout
if [[ -o interactive && "\$TERM_PROGRAM" == vscode && -z "\$TMUX" ]]; then
  exec bash "$REPO_DIR/.session/layout.sh"
fi
EOF
fi

# --- Node + OpenSpec, via mise ---------------------------------------------
# mise itself is already installed and activated (base image / real AMI).
# `mise use -g` sets the global version and installs it, but mise's PATH
# hook only refreshes on a new shell / prompt, not mid-script — so the
# install step below uses `mise exec` to guarantee node/npm resolve in
# *this* shell too (same workaround custom_tools_and_mcp uses for pip).
mise use --global "node@${NODE_VERSION}"
if ! mise exec "node@${NODE_VERSION}" -- openspec --version 2>/dev/null | grep -q "^${OPENSPEC_VERSION}$"; then
  mise exec "node@${NODE_VERSION}" -- npm install -g "@fission-ai/openspec@${OPENSPEC_VERSION}"
fi

# Disable OpenSpec's anonymous telemetry ping (documented opt-out: either
# DO_NOT_TRACK or OPENSPEC_TELEMETRY; DO_NOT_TRACK is already exported by
# the shell extras above for interactive shells — this also belt-and-braces
# the global config, via the same `mise exec` PATH workaround as above).
export DO_NOT_TRACK=1
mise exec "node@${NODE_VERSION}" -- openspec config set telemetry.enabled false >/dev/null 2>&1 || true

# --- Python packages: Textual (the city app) and pytest ---------------------
# Guarded so a reboot doesn't hit the package index every time.
if ! python3 -c "import textual, pytest" >/dev/null 2>&1; then
  python3 -m pip install --user -r "$REPO_DIR/requirements.txt"
fi

# --- tmux ----------------------------------------------------------------
# The session layout (Claude Code | city app over a terminal) is one tmux
# session inside one terminal, opened as an editor tab: the editor extension can only
# open terminals in the bottom panel, not arrange them. No sudo on the AMI, so
# the official static build goes in ~/.local/bin, pinned so every VM behaves
# the same whether or not the image ships its own tmux.
mkdir -p "$HOME/.local/bin"
if ! "$HOME/.local/bin/tmux" -V 2>/dev/null | grep -q "tmux ${TMUX_VERSION}$"; then
  case "$(uname -m)" in aarch64|arm64) TMUX_ARCH=arm64 ;; *) TMUX_ARCH=x86_64 ;; esac
  curl -fsSL "https://github.com/tmux/tmux-builds/releases/download/v${TMUX_VERSION}/tmux-${TMUX_VERSION}-linux-${TMUX_ARCH}.tar.gz" \
    | tar -xz -C "$HOME/.local/bin" tmux
fi

# Mouse on so learners click between panes and drag the borders; the prefix
# moves off C-b, which Claude Code uses to background a command; pane titles
# say what each pane is for. extended-keys lets Shift+Enter reach Claude Code.
cat << 'EOF' > "$HOME/.tmux.conf"
set -g mouse on
set -g prefix C-]
unbind C-b
bind C-] send-prefix
set -g status off
set -g pane-border-status top
set -g pane-border-format " #{pane_title} "
set -g allow-rename off
set -g escape-time 10
set -g history-limit 50000
set -g default-terminal "tmux-256color"
set -as terminal-features ",xterm*:RGB"
set -s extended-keys on
set -as terminal-features ",xterm*:extkeys"
EOF

# --- The coach's view --------------------------------------------------------
# Two parts, like the designing agents module's coach sync. A live, read-only view of the learner's
# tmux session in a browser: .session/watch_server.py, which reads the panes with `tmux capture-pane`
# and scales them to fit the coach's window (it never sends anything to tmux). It listens on 8001, and
# the watch-port container forwards the exposed port, 1001, to it. And CITY.md, a summary that
# .session/coach_summary.py rewrites every few seconds, which the learnersync container sends to the
# coach. On the hosted VM, background processes started here don't outlive the startup step, so
# .session/layout.sh starts both in a hidden tmux session when the learner opens the editor. They're
# also started here, if they aren't already running, which keeps the local emulator's port check happy.
mkdir -p "$HOME/.city-session/coach"
if ! pgrep -u "$(id -u)" -f "\.session/watch_server\.py" >/dev/null; then
  setsid nohup python3 "$REPO_DIR/.session/watch_server.py" > "$HOME/.city-session/watch_server.log" 2>&1 < /dev/null &
fi
if ! pgrep -u "$(id -u)" -f "\.session/coach_summary\.py" >/dev/null; then
  setsid nohup python3 "$REPO_DIR/.session/coach_summary.py" > "$HOME/.city-session/coach_summary.log" 2>&1 < /dev/null &
fi
# learnersync reads the attendance id from a file in the repo. Hosted VMs provide it; write it only if
# it's missing (the local emulator), so a real one is never overwritten.
if [ ! -s "$REPO_DIR/attendance_id" ] && [ -n "${SW_ATTENDANCE_ID:-}" ]; then
  printf '%s' "$SW_ATTENDANCE_ID" > "$REPO_DIR/attendance_id"
fi
(cd "$REPO_DIR" && docker compose up --wait)

# --- git identity ----------------------------------------------------------
# Only set if unset, so learners can commit during the session without
# clobbering anything they've configured themselves.
git config --global user.name >/dev/null 2>&1 || git config --global user.name "Learner"
git config --global user.email >/dev/null 2>&1 || git config --global user.email "learner@example.com"

# --- ~/.claude.json: onboarding + project trust ---------------------------
# The shared setup writes this file with just the theme. A learner may also
# have changed keys in here since the last boot, so this is a merge, not an
# overwrite.
REPO_DIR="$REPO_DIR" python3 - << 'PYEOF'
import json
import os

path = os.path.expanduser("~/.claude.json")
try:
    with open(path) as f:
        data = json.load(f)
except (FileNotFoundError, json.JSONDecodeError):
    data = {}

data.setdefault("theme", "light")
data["hasCompletedOnboarding"] = True
data.setdefault("shiftEnterKeyBindingInstalled", True)

projects = data.setdefault("projects", {})
project = projects.setdefault(os.environ["REPO_DIR"], {})
project["hasTrustDialogAccepted"] = True

with open(path, "w") as f:
    json.dump(data, f, indent=4)
PYEOF

# --- Claude Code user settings: start learners in auto mode ---------------
# Has to be user settings — `auto` is ignored from a project's
# .claude/settings.json. Deterministic content, unguarded.
mkdir -p "$HOME/.claude" "$HOME/.claude/projects"
cat << EOF > "$HOME/.claude/settings.json"
{
    "permissions": {
        "defaultMode": "auto"
    }
}
EOF

# --- .vscode/settings.json: terminal in an editor tab, hide plumbing -------
# The shared setup has already written .vscode/settings.json with the
# extension's Bedrock config (a merge, not an overwrite, is needed to keep
# it — its trailing comma is fine for VS Code's JSONC parser but fatal for
# json.load, so strip that first). openspec/ and .claude/ stay visible:
# learners read openspec/ files directly, and .claude/commands/opsx is
# where the /opsx: slash commands live.
mkdir -p "$REPO_DIR/.vscode"
REPO_DIR="$REPO_DIR" python3 - << 'PYEOF'
import json
import os
import re

path = os.path.join(os.environ["REPO_DIR"], ".vscode", "settings.json")
try:
    with open(path) as f:
        raw = f.read()
except FileNotFoundError:
    raw = ""
try:
    data = json.loads(raw)
except json.JSONDecodeError:
    try:
        data = json.loads(re.sub(r",\s*([\]}])", r"\1", raw))
    except json.JSONDecodeError:
        data = {}

data.setdefault("files.exclude", {}).update({
    "setup.sh": True,
    ".vscode": True,
    ".session": True,
    ".curriculumconfig": True,
    "docker-compose.yml": True,
    "attendance_id": True,
    "**/__pycache__": True,
})
# The tmux layout is the whole session, so its terminal (see the .zshrc hook
# above) opens as an editor tab, filling the main area.
data["terminal.integrated.defaultLocation"] = "editor"
data["terminal.integrated.macOptionClickForcesSelection"] = True

with open(path, "w") as f:
    json.dump(data, f, indent=4)
PYEOF
