# Help, I Broke It

**The terminal tab closed, or a pane disappeared**<br>
Reload the page.
The layout comes back.
If a pane had gone, Claude Code starts a new conversation, but your code and specs are all still there.

**Claude Code or the City app stopped, but its pane is still there**<br>
Type its command in that pane:

```bash
claude                          # Claude Code
python3 .session/run_city.py    # the City app
```

**The City app shows an error**<br>
Ask Claude Code to fix it.
The City app restarts by itself whenever the code changes.

**The code is in a mess**<br>
Run `/checkpoint` in Claude Code, and pick a state to reset to.
This replaces your code, tests and specs.

**Everything is broken**<br>
Go back to the session page.
On the Hosted Environment panel, click the gears button (Info/Settings), then Terminate.
When it says Stopped, click Start.
Use Terminate, not Reboot.
This clears your files, so run `/checkpoint` afterwards to get back to a good point.
