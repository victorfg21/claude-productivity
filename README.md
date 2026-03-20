# claude-productivity

![Python](https://img.shields.io/badge/python-3.10%2B-blue?logo=python&logoColor=white)
![License](https://img.shields.io/badge/license-MIT-green)
![Platform](https://img.shields.io/badge/platform-Linux%20%7C%20macOS%20%7C%20Windows-lightgrey)

Real-time productivity dashboard for [Claude Code](https://claude.ai/code). Tracks your sessions automatically via hooks, reads `.jsonl` files directly, and presents everything in a terminal TUI with 5 tabs. No manual tracking required.

```
┌─────────────────────────────────────────────────────────────────┐
│  claude-productivity   [1] Dashboard  [2] Insights  [3] History │
│─────────────────────────────────────────────────────────────────│
│  Today   47 tools   32 edits   12 bash   85% success            │
│                                                                  │
│  ▁▂▃█▅▄▂▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁  (hourly activity)                   │
│                                                                  │
│  Recent  Edit   src/app.py          230ms                        │
│          Bash   pytest tests/       1.2s                         │
│          💭     Thinking...  (4 321 chars)                       │
└─────────────────────────────────────────────────────────────────┘
```

---

## Features

- **Dashboard** — Current session stats: hourly activity chart, recent events (tool, file, duration), edits, bash calls, read count, bash success rate, edit bursts, languages used, and subagent activity.
- **Insights** — AI-generated recommendations refreshed every 120 seconds via `claude --print`, with fallback to a local analyzer.
- **History** — 7-day history with daily goal tracking (default: 150 tools/day).
- **Projects** — Aggregated project stats: sessions, edits, bash success rate, languages, and time.
- **Sessions** — Live multi-session view sourced directly from `.jsonl` files. Shows all active Claude Code instances simultaneously, including thinking block counts, token usage, and subagents.
- **Tool duration tracking** — Average execution time per tool type (Bash, Edit, Agent, etc.).
- **Thinking blocks** — Activity feed shows when Claude is thinking with character count; text content is never persisted.
- **Excel export** — 4-sheet `.xlsx` report (Summary, 7-Day History, Projects, Languages) saved to `~/`.
- **5 themes** — One Dark, Monokai, Dracula, Nord, Tokyo Night (press `T` to cycle).
- **Direct `.jsonl` reading** — Works even without hooks installed by reading `~/.claude/projects/` directly.

---

## How It Works

```
Claude Code session
      │
      ▼  hooks (PreToolUse / PostToolUse / Stop)
hooks/logger.py ──────────────────► ~/.claude/productivity.db (SQLite)
                                              │
~/.claude/projects/**/*.jsonl ◄───────────────┤
      │                                       │
      ▼                                       ▼
jsonl_reader.py                            db.py
      │                                       │
      └──────────────┬────────────────────────┘
                     ▼
              claude_productivity/tui/app.py (Textual TUI)
                     │
                     ├── ActivityWidget    (recent events + thinking)
                     ├── ChartWidget       (hourly bar chart)
                     ├── StatsWidget       (metrics + duration per tool)
                     ├── InsightsWidget    (AI recommendations)
                     ├── HistoryWidget     (7-day history)
                     ├── ProjectsWidget    (project aggregates)
                     └── MultiSessionWidget (live sessions)
```

The hooks capture per tool call: tool name, file path, bash command (first 200 chars), exit code, project name (derived from path), file extension, agent subtype, and duration in milliseconds. All data is stored locally in `~/.claude/productivity.db`.

---

## Tech Stack

| Component | Library / Tool |
|-----------|---------------|
| TUI framework | [Textual](https://github.com/Textualize/textual) >= 0.47.0 |
| Excel export | [openpyxl](https://openpyxl.readthedocs.io/) >= 3.1.0 |
| Database | sqlite3 (Python stdlib) |
| AI insights | Claude CLI (`claude --print`) — optional |
| Python | 3.10+ |

---

## Installation

### Linux / macOS

**Requirements:** Python 3.10+, Claude Code CLI, Git

```bash
git clone https://github.com/victorfg21/claude-productivity
cd claude-productivity
chmod +x install.sh
./install.sh
```

The script:
1. Installs the package with `pip install -e .`
2. Registers 3 hooks in `~/.claude/settings.json` (PreToolUse, PostToolUse, Stop)
3. Creates `~/.claude/productivity.db` on first use

Then launch the dashboard:

```bash
claude-metrics
```

### Windows

**Requirements:** Python 3.10+ (from [python.org](https://www.python.org/downloads/), added to `PATH`), Claude Code CLI, PowerShell 5.1+

```powershell
git clone https://github.com/victorfg21/claude-productivity
cd claude-productivity
.\install.ps1
```

To install the package only (without hook registration):

```powershell
pip install -e .
```

Then add hooks manually to `%USERPROFILE%\.claude\settings.json` — see the [Hooks](#hooks) section below.

> **WSL2 users:** Use the Linux instructions inside your WSL environment. `claude-metrics` will work in the WSL terminal.

---

## Hooks

Hooks are registered in `~/.claude/settings.json`. Claude Code calls them automatically on each tool use.

| Hook | Fires | What it records |
|------|-------|----------------|
| `PreToolUse` | Before each tool call | Start timestamp (for duration calculation) |
| `PostToolUse` | After each tool call | Tool name, file path, command, exit code, duration |
| `Stop` | Session end | Marks the session as ended |

To register hooks manually if the install script fails, add the following to `~/.claude/settings.json`:

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": ".*",
        "hooks": [
          {
            "type": "command",
            "command": "CLAUDE_HOOK_EVENT=PreToolUse python3 /path/to/hooks/logger.py"
          }
        ]
      }
    ],
    "PostToolUse": [
      {
        "matcher": ".*",
        "hooks": [
          {
            "type": "command",
            "command": "CLAUDE_HOOK_EVENT=PostToolUse python3 /path/to/hooks/logger.py"
          }
        ]
      }
    ],
    "Stop": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "CLAUDE_HOOK_EVENT=Stop python3 /path/to/hooks/logger.py"
          }
        ]
      }
    ]
  }
}
```

Replace `/path/to/hooks/logger.py` with the absolute path to the file in your cloned repository.

---

## Keyboard Shortcuts

| Key | Action |
|-----|--------|
| `1` | Dashboard tab |
| `2` | Insights tab |
| `3` | History tab |
| `4` | Projects tab |
| `5` | Sessions tab |
| `T` | Cycle theme |
| `R` | Force refresh |
| `E` | Export to Excel |
| `Q` | Quit |

---

## Configuration

Configuration is done by editing constants directly in the source files. No config file is needed for basic use.

| Constant | File | Default | Description |
|----------|------|---------|-------------|
| `DAILY_GOAL` | `tui/app.py` | `150` | Daily tool call target shown in History tab |
| `DASHBOARD_REFRESH_SECS` | `tui/app.py` | `3` | Dashboard poll interval in seconds |
| `INSIGHTS_REFRESH_SECS` | `tui/app.py` | `120` | AI insights refresh interval in seconds |
| `ACTIVE_THRESHOLD_MINUTES` | `jsonl_reader.py` | `10` | Time window used to classify a session as "active" in the Sessions tab |

---

## Privacy

- **Bash commands:** The first 200 characters of each bash command are stored in the local database. This may include credentials, tokens, or other sensitive data passed as arguments. The database lives at `~/.claude/productivity.db` and is never transmitted anywhere.
- **Thinking blocks:** The app reads Claude's thinking blocks from `.jsonl` files to count them. Only the character count is stored — the text itself is not persisted.
- **Conversation content:** The app reads `.jsonl` files to extract tool call metadata. It does not store, display, or transmit message text or AI responses.
- **No telemetry:** The only outbound operation is the optional `claude --print` call for AI insights, which runs locally via your Claude Code installation.

---

## Demo Mode

If no hooks are installed or no session data exists yet, the app displays clearly-labeled placeholder data. Run `./install.sh` and start a Claude Code session to see live data populate.

---

## Uninstall

```bash
# 1. Remove hooks — open ~/.claude/settings.json and delete the "hooks" key entries

# 2. Remove the database
rm ~/.claude/productivity.db

# 3. Uninstall the package
pip uninstall claude-productivity
```

---

## Contributing

Contributions are welcome. To get started:

1. Fork the repository and create a feature branch.
2. Keep changes focused — one concern per pull request.
3. Test against a real Claude Code session before submitting.
4. Open a pull request with a clear description of what changed and why.

Bug reports and feature requests can be filed as GitHub Issues.

---

## License

This project is licensed under the [MIT License](LICENSE).
