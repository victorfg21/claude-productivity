"""
PRODUCTIVITY.SYS // CLAUDE INTERFACE

Polling em tempo real:
  - Dashboard / Histórico: atualiza a cada 3s (leve, só SQLite)
  - Insights: atualiza a cada 120s (chama claude --print em worker thread)

Temas: T para alternar entre Blade Runner 2049 e Cyberpunk 2077
"""

from __future__ import annotations

import re
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, ScrollableContainer, Vertical
from textual.reactive import reactive
from textual.widgets import Footer, Static, TabbedContent, TabPane

from ..analyzer import CATEGORY_ICON
from ..claude_client import generate_insights
from ..i18n import _t, _tl, set_language, detect_language, LANG as _LANG
from ..prefs import load as _load_prefs, save as _save_prefs

# Carrega preferências persistidas (tema e idioma) antes da definição das classes
# (BINDINGS são avaliados no momento da criação da classe)
_prefs = _load_prefs()
_saved_lang = _prefs.get("language", "")
set_language(_saved_lang if _saved_lang else detect_language())
from ..db import (
    SessionStats, DailyStats, ProjectStats,
    get_current_session_stats, get_daily_history, get_all_project_stats,
    get_tool_duration_stats,
)
from ..jsonl_reader import LiveSessionData, SubagentSummary, get_live_sessions, aggregate_tool_durations

# ── Constantes ─────────────────────────────────────────────────────────────

DASHBOARD_REFRESH_SECS = 3
INSIGHTS_REFRESH_SECS  = 120
DAILY_GOAL             = 150   # meta de tool calls por dia (ajuste conforme preferência)

# ── Demo data ──────────────────────────────────────────────────────────────

_DEMO_HOURLY = [0]*8 + [3, 7, 14, 18, 11, 9, 16, 12, 5, 2] + [0]*6

_DEMO_EVENTS = [
    {"ts": "14:32:01", "tool_name": "Edit",  "file_path": "src/api/routes.py",  "command": None},
    {"ts": "14:31:45", "tool_name": "Bash",  "file_path": None, "command": "pytest tests/ -v"},
    {"ts": "14:30:12", "tool_name": "Read",  "file_path": "README.md",           "command": None},
    {"ts": "14:29:55", "tool_name": "Edit",  "file_path": "src/models/user.py",  "command": None},
    {"ts": "14:28:30", "tool_name": "Write", "file_path": "docs/api.md",         "command": None},
    {"ts": "14:27:11", "tool_name": "Bash",  "file_path": None, "command": 'git commit -m "fix auth"'},
    {"ts": "14:26:44", "tool_name": "Edit",  "file_path": "src/auth/jwt.py",     "command": None},
    {"ts": "14:25:02", "tool_name": "Read",  "file_path": "src/config.py",       "command": None},
    {"ts": "14:24:10", "tool_name": "Grep",  "file_path": None,                  "command": None},
    {"ts": "14:23:55", "tool_name": "Edit",  "file_path": "src/api/routes.py",  "command": None},
]

_DEMO_HISTORY = [
    DailyStats("2026-03-11", 87,  3, 32, 18, 8,  180),
    DailyStats("2026-03-12", 120, 4, 48, 25, 12, 210),
    DailyStats("2026-03-13", 65,  2, 24, 14, 6,  140),
    DailyStats("2026-03-14", 0,   0, 0,  0,  0,  0),
    DailyStats("2026-03-15", 145, 5, 60, 30, 15, 260),
    DailyStats("2026-03-16", 98,  3, 40, 20, 10, 190),
    DailyStats("2026-03-17", 147, 4, 55, 28, 23, 154),
]

_DEMO_SESSION = SessionStats(
    session_id="demo-session",
    started_at=datetime.now().isoformat(),
    ended_at=None,
    total_tools=147,
    duration_minutes=154,
    edit_count=55,
    read_count=34,
    bash_count=28,
    unique_files=23,
    repeated_files=[("src/api/routes.py", 8), ("src/models/user.py", 4)],
    hourly_activity=_DEMO_HOURLY,
    recent_events=_DEMO_EVENTS,
    # Campos enriquecidos
    bash_success_rate=78.6,
    language_breakdown={"py": 23, "ts": 12, "md": 5, "json": 3},
    project_name="my-backend",
    agent_calls=4,
    avg_edit_burst=2.8,
    cross_session_files=["src/api/routes.py", "src/models/user.py", "src/auth/jwt.py"],
    is_active=True,
    agent_subtype_breakdown={"react-component-architect": 2, "django-backend-expert": 1, "Explore": 1},
)

_DEMO_PROJECTS = [
    ProjectStats("my-backend",          12, 480, 210, 320, 87, 1840, "2026-03-17", 82.4, {"vue": 45, "ts": 28, "py": 12}),
    ProjectStats("claude-productivity",  5, 120,  55, 100, 23,  620, "2026-03-16", 90.0, {"py": 80, "md": 10}),
    ProjectStats("my-frontend",          8, 310, 140, 210, 64, 1200, "2026-03-14", 75.3, {"vue": 60, "ts": 30}),
]

_DEMO_LIVE_SESSIONS = [
    LiveSessionData(
        session_id="demo-live-1", project_name="my-backend",
        project_dir="-home-user-projects-my-backend",
        cwd="/home/user/projects/my-backend",
        started_at="2026-03-20T14:00:00Z", last_activity="2026-03-20T16:42:00Z",
        is_active=True, total_tools=87, edit_count=42, bash_count=18, read_count=20,
        thinking_count=12, input_tokens=42000, output_tokens=8000, cache_read_tokens=18000,
        git_branch="feat/new-feature", version="2.1.62", model="claude-opus-4-6",
        tool_durations={"Bash": [8200, 9100, 7800], "Edit": [1400, 1200, 1600],
                        "Read": [300, 280, 320], "Agent": [45000, 48000]},
        subagents=[
            SubagentSummary("a1", "Explore", "Explore codebase", 18, 0, 0, 8000, 2000),
            SubagentSummary("a2", "backend-developer", "Implement sync API", 12, 8, 2, 12000, 4000),
        ],
    ),
    LiveSessionData(
        session_id="demo-live-2", project_name="claude-productivity",
        project_dir="-home-user-claude-productivity",
        cwd="/home/user/Desktop/Workspace/claude-productivity",
        started_at="2026-03-20T10:00:00Z", last_activity="2026-03-20T16:38:00Z",
        is_active=True, total_tools=149, edit_count=68, bash_count=31, read_count=47,
        thinking_count=8, input_tokens=28000, output_tokens=5000, cache_read_tokens=12000,
        git_branch="main", version="2.1.62", model="claude-sonnet-4-6",
        tool_durations={"Bash": [3200, 2800], "Edit": [900, 1100], "Read": [200, 250]},
        subagents=[SubagentSummary("b1", "Explore", "Explore TUI", 8, 0, 0, 4000, 1500)],
    ),
    LiveSessionData(
        session_id="demo-live-3", project_name="api-service",
        project_dir="-home-user-projects-api-service",
        cwd="/home/user/projects/api-service",
        started_at="2026-03-20T08:00:00Z", last_activity="2026-03-20T10:15:00Z",
        is_active=False, total_tools=45, edit_count=20, bash_count=12, read_count=13,
        thinking_count=3, input_tokens=15000, output_tokens=3000, cache_read_tokens=5000,
        git_branch="main", version="2.1.60", model="claude-haiku-4-5-20251001",
        tool_durations={"Bash": [5000], "Edit": [1300]},
        subagents=[],
    ),
]

_DEMO_TOOL_DURATIONS = {"Agent": 46500.0, "Bash": 8033.0, "Edit": 1366.0, "Read": 300.0, "Grep": 150.0}

# ── Temas ──────────────────────────────────────────────────────────────────
# Cada tema tem uma chave CSS usada como classe no Screen (ex: Screen.monokai)

THEMES = {
    "one_dark": {
        "name":       "ATOM ONE DARK",
        "css_class":  "one-dark",
        "primary":    "#61afef",   # blue
        "primary_dim":"#2a4a6a",
        "secondary":  "#98c379",   # green
        "edit_color": "#e5c07b",   # yellow
        "bash_color": "#56b6c2",   # cyan
        "read_color": "#c678dd",   # purple
        "spark_color":"#61afef",
        "warning":    "#e06c75",
        "tip":        "#e5c07b",
        "strength":   "#98c379",
        "info":       "#61afef",
    },
    "monokai": {
        "name":       "MONOKAI PRO",
        "css_class":  "monokai",
        "primary":    "#f92672",   # pink-red
        "primary_dim":"#5a1030",
        "secondary":  "#a6e22e",   # green
        "edit_color": "#e6db74",   # yellow
        "bash_color": "#66d9e8",   # blue
        "read_color": "#ae81ff",   # purple
        "spark_color":"#f92672",
        "warning":    "#f92672",
        "tip":        "#fd971f",
        "strength":   "#a6e22e",
        "info":       "#66d9e8",
    },
    "dracula": {
        "name":       "DRACULA",
        "css_class":  "dracula",
        "primary":    "#bd93f9",   # purple
        "primary_dim":"#44475a",
        "secondary":  "#8be9fd",   # cyan
        "edit_color": "#ff79c6",   # pink
        "bash_color": "#50fa7b",   # green
        "read_color": "#8be9fd",   # cyan
        "spark_color":"#bd93f9",
        "warning":    "#ff5555",
        "tip":        "#ffb86c",
        "strength":   "#50fa7b",
        "info":       "#8be9fd",
    },
    "nord": {
        "name":       "NORD",
        "css_class":  "nord",
        "primary":    "#88c0d0",   # light blue
        "primary_dim":"#3b4252",
        "secondary":  "#a3be8c",   # green
        "edit_color": "#ebcb8b",   # yellow
        "bash_color": "#81a1c1",   # blue
        "read_color": "#b48ead",   # purple
        "spark_color":"#88c0d0",
        "warning":    "#bf616a",
        "tip":        "#ebcb8b",
        "strength":   "#a3be8c",
        "info":       "#88c0d0",
    },
    "tokyo_night": {
        "name":       "TOKYO NIGHT",
        "css_class":  "tokyo-night",
        "primary":    "#7aa2f7",   # blue
        "primary_dim":"#3b4261",
        "secondary":  "#9ece6a",   # green
        "edit_color": "#e0af68",   # orange
        "bash_color": "#7dcfff",   # light blue
        "read_color": "#bb9af7",   # purple
        "spark_color":"#7aa2f7",
        "warning":    "#f7768e",
        "tip":        "#e0af68",
        "strength":   "#9ece6a",
        "info":       "#7aa2f7",
    },
}

THEME_ORDER = list(THEMES.keys())
_saved_theme = _prefs.get("theme", "one_dark")
_current_theme_key = _saved_theme if _saved_theme in THEMES else "one_dark"


def theme() -> dict:
    return THEMES[_current_theme_key]


# ── Helpers de renderização ────────────────────────────────────────────────

BLOCKS = " ▁▂▃▄▅▆▇█"


def _bar_chart(hourly: List[int]) -> str:
    mx = max(hourly) if max(hourly) > 0 else 1
    height = 6
    rows: List[str] = []
    for level in range(height, 0, -1):
        threshold = (level / height) * mx
        line = "  "
        for v in hourly:
            line += "█ " if v >= threshold else "  "
        rows.append(line.rstrip())
    # Labels a cada 3h (cada hora = 2 chars)
    label_line = "  "
    for i in range(24):
        label_line += f"{i:02d}" if i % 3 == 0 else "  "
    rows.append(label_line)
    return "\n".join(rows)


def _sparkbar(values: List[int], width: int = 44) -> str:
    if not values or max(values) == 0:
        return "▁" * width
    mx = max(values)
    result = ""
    for i in range(width):
        src = int(i * len(values) / width)
        idx = round((values[src] / mx) * (len(BLOCKS) - 1))
        result += BLOCKS[idx]
    return result


def _fmt_duration(minutes: float) -> str:
    h, m = int(minutes // 60), int(minutes % 60)
    return f"{h}h {m:02d}m" if h > 0 else f"{m}m"


def _pbar(val: int, cap: int, width: int = 26) -> str:
    pct = min(100, int((val / max(cap, 1)) * 100))
    filled = int((pct / 100) * width)
    return "█" * filled + "░" * (width - filled) + f"  {pct:3}%"


def _hbar(val: float, width: int = 20) -> str:
    """Barra horizontal para percentuais (0-100)."""
    pct = min(100.0, max(0.0, val))
    filled = int((pct / 100) * width)
    return "█" * filled + "░" * (width - filled)


def _lang_bar(cnt: int, total: int, width: int = 8) -> str:
    """Mini barra proporcional para language breakdown."""
    if total == 0:
        return "░" * width
    filled = max(1, int((cnt / total) * width))
    return "█" * filled + "░" * (width - filled)


# ── Widgets ────────────────────────────────────────────────────────────────

class HeaderWidget(Static):
    _clock: reactive[str] = reactive("")
    _project: str = ""
    _is_active: bool = True
    _is_demo: bool = False

    def on_mount(self) -> None:
        self._update_clock()

    def set_project(self, name: str) -> None:
        self._project = name or ""

    def set_active(self, is_active: bool) -> None:
        self._is_active = is_active

    def set_demo(self, is_demo: bool) -> None:
        self._is_demo = is_demo

    def _update_clock(self) -> None:
        self._clock = datetime.now().strftime("%Y-%m-%d  %H:%M:%S")
        self.refresh()

    def render(self) -> str:
        t = theme()
        cursor  = "█" if datetime.now().second % 2 == 0 else " "
        project = f" · {self._project}" if self._project else ""
        if self._is_demo:
            status = f"  [bold yellow]⚠ {_t('demo_mode')}[/bold yellow]"
        elif self._is_active:
            status = f"  [bold green]● {_t('live')}[/bold green]"
        else:
            status = f"  [dim]○ {_t('last_session')}[/dim]"
        left  = f"  ▸ PRODUCTIVITY.SYS{project}{status} {cursor}"
        right = f"  {self._clock}  ◂  {t['name']}  "
        # Strip Rich markup for length calculation
        left_plain  = re.sub(r"\[.*?\]", "", left)
        right_plain = re.sub(r"\[.*?\]", "", right)
        gap = max(1, 120 - len(left_plain) - len(right_plain))
        return f"[bold]{left}{' ' * gap}{right}[/bold]"


class ActivityWidget(Static):
    def update_events(self, events) -> None:
        """Aceita List[dict] (DB) ou List[ParsedEvent] (jsonl_reader)."""
        t = theme()
        ICONS = {
            "Edit": "✎", "Write": "✎", "MultiEdit": "✎",
            "Bash": "▶", "Read": "◎", "Grep": "◎", "Glob": "◎",
            "Agent": "◈", "Task": "◈", "WebFetch": "⊕", "WebSearch": "⊕",
            "SendMessage": "⇢",
        }
        TOOL_SHORT = {
            "Edit": "Edit", "Write": "Write", "MultiEdit": "MEdit",
            "Bash": "Bash", "Read": "Read", "Grep": "Grep", "Glob": "Glob",
            "Agent": "Agent", "Task": "Task",
            "WebFetch": "Fetch", "WebSearch": "Search",
            "SendMessage": "Msg",
        }
        lines = [f"  [bold]{_t('recent_activity')}[/bold]\n  [dim]{'─' * 54}[/dim]\n"]
        for e in events:
            # Normalizar: ParsedEvent ou dict
            if hasattr(e, "event_type"):
                ev_type   = e.event_type
                ts_raw    = str(e.ts or "")
                tn        = e.tool_name or ""
                fp        = e.file_path or ""
                cmd       = e.command or ""
                dur_ms    = e.duration_ms
                is_err    = e.is_error
                think_len = e.thinking_len
            else:
                ev_type   = "tool_use"
                ts_raw    = str(e.get("ts", "") or "")
                tn        = e.get("tool_name", "?")
                fp        = e.get("file_path") or ""
                cmd       = e.get("command") or ""
                dur_ms    = 0
                is_err    = False
                think_len = 0

            ts = ts_raw[11:19] if len(ts_raw) >= 19 else (ts_raw[:8] if len(ts_raw) >= 8 else "--:--:--")

            # ── Thinking block ──────────────────────────────────────────
            if ev_type == "thinking":
                lines.append(
                    f"  [dim]{ts}[/dim]  [{t['info']}]💭  {_t('thinking'):<12}[/{t['info']}]"
                    f"  [dim]{think_len:,} {_t('chars')}[/dim]"
                )
                continue

            # ── Cor por tipo ─────────────────────────────────────────────
            if is_err:
                color = t["warning"]
            elif tn in ("Edit", "Write", "MultiEdit"):
                color = t["edit_color"]
            elif tn == "Bash":
                color = t["bash_color"]
            elif tn in ("Read", "Grep", "Glob"):
                color = t["read_color"]
            elif tn in ("Agent", "Task"):
                color = t["secondary"]
            else:
                color = t["info"]

            # ── Label: mostra parent/arquivo para mais contexto ──────────
            if fp:
                parts = [p for p in fp.split("/") if p]
                if len(parts) >= 2:
                    raw_label = f"{parts[-2]}/{parts[-1]}"
                else:
                    raw_label = parts[-1] if parts else fp
                label = raw_label[:48]
            else:
                label = (cmd[:46] + "…") if len(cmd) > 46 else cmd

            # ── Duração ──────────────────────────────────────────────────
            if dur_ms >= 60_000:
                dur_str = f"  [dim]{dur_ms/60000:.1f}m[/dim]"
            elif dur_ms >= 1000:
                dur_str = f"  [dim]{dur_ms/1000:.1f}s[/dim]"
            elif dur_ms > 0:
                dur_str = f"  [dim]{dur_ms}ms[/dim]"
            else:
                dur_str = ""

            icon     = ICONS.get(tn, "·")
            tn_short = TOOL_SHORT.get(tn, tn[:6])
            err_tag  = f" [{t['warning']}]✗[/{t['warning']}]" if is_err else ""

            lines.append(
                f"  [dim]{ts}[/dim]  [{color}]{icon} {tn_short:<7}[/{color}]"
                f"  {label}{dur_str}{err_tag}"
            )
        self.update("\n".join(lines))


class ChartWidget(Static):
    def update_chart(self, hourly: List[int]) -> None:
        t = theme()
        spark = _sparkbar(hourly)
        chart = _bar_chart(hourly)
        total = sum(hourly)
        peak  = hourly.index(max(hourly)) if max(hourly) > 0 else 0
        self.update(
            f"  [bold]{_t('hourly_activity')}[/bold]"
            f"  [dim]{_t('total')}: {total}  {_t('peak')}: {peak:02d}h[/dim]\n"
            f"  [dim]{'─' * 36}[/dim]\n\n"
            + chart + "\n\n"
            + f"  [dim]24h[/dim]  [{t['spark_color']}]▕{spark}▏[/{t['spark_color']}]"
        )


class StatsWidget(Static):
    def update_stats(self, session: SessionStats,
                     tool_durations: Optional[Dict[str, float]] = None) -> None:
        t = theme()
        p = t["secondary"]
        w = t["warning"]
        s = t["strength"]
        total = max(session.edit_count + session.bash_count + session.read_count, 1)

        # ── Resumo da sessão ──────────────────────────────────────────────
        lines = [
            f"  [bold]{_t('current_session')}[/bold]",
            f"  [dim]{'─' * 38}[/dim]",
            "",
            f"  [dim]{_t('duration')}[/dim]   [{p}]{_fmt_duration(session.duration_minutes):<10}[/{p}]"
            f"  [dim]{_t('tools')}[/dim]  [{p}]{session.total_tools}[/{p}]",
            f"  [dim]{_t('unique_files')}[/dim]  [{p}]{session.unique_files}[/{p}]",
            "",
        ]

        # ── Atividade (barras agrupadas) ──────────────────────────────────
        lines += [
            f"  [dim]{_t('sec_activity')} {'─' * 26}[/dim]",
            "",
            f"  [dim]{_t('edits')}[/dim][{p}]{_pbar(session.edit_count, 80, 20)}[/{p}]"
            f" [{p}]{session.edit_count:>3}[/{p}] [dim]({session.edit_count * 100 // total}%)[/dim]",
            f"  [dim]{_t('bash_lbl')}[/dim][{p}]{_pbar(session.bash_count, 80, 20)}[/{p}]"
            f" [{p}]{session.bash_count:>3}[/{p}] [dim]({session.bash_count * 100 // total}%)[/dim]",
            f"  [dim]{_t('reads')}[/dim][{p}]{_pbar(session.read_count, 80, 20)}[/{p}]"
            f" [{p}]{session.read_count:>3}[/{p}] [dim]({session.read_count * 100 // total}%)[/dim]",
        ]

        # ── Bash Health ──────────────────────────────────────────────────
        if session.bash_count > 0 and session.bash_success_rate > 0:
            rate  = session.bash_success_rate
            ok    = int(session.bash_count * rate / 100)
            fail  = session.bash_count - ok
            color = s if rate >= 80 else (w if rate < 70 else t["tip"])
            label = _t("excellent") if rate >= 90 else (_t("attention") if rate < 70 else _t("ok"))
            lines += [
                "",
                f"  [dim]{_t('sec_bash_health')} {'─' * 24}[/dim]",
                "",
                f"  [{color}]{_hbar(rate, 20)}[/{color}]"
                f"  [{color}]{rate:.0f}%[/{color}]  [dim]{ok} {_t('ok')} · {fail} {_t('fail')} · {label}[/dim]",
            ]

        # ── Linguagens ───────────────────────────────────────────────────
        if session.language_breakdown:
            total_ext = sum(session.language_breakdown.values())
            lines += [
                "",
                f"  [dim]{_t('sec_languages')} {'─' * 25}[/dim]",
                "",
            ]
            for ext, cnt in list(session.language_breakdown.items())[:4]:
                pct = int((cnt / total_ext) * 100)
                bar = _lang_bar(cnt, total_ext, width=14)
                lines.append(
                    f"  [{p}].{ext:<6}[/{p}]  [{p}]{bar}[/{p}]"
                    f"  [dim]{cnt:>3} {_t('files_abbr')}  ({pct}%)[/dim]"
                )

        # ── Foco (edit burst) ────────────────────────────────────────────
        if session.avg_edit_burst > 0:
            burst = session.avg_edit_burst
            color = s if burst >= 4.0 else (t["tip"] if burst < 1.5 else p)
            label = _t("high_focus") if burst >= 4.0 else (_t("fragmented") if burst < 1.5 else _t("moderate"))
            lines += [
                "",
                f"  [dim]{_t('sec_edit_focus')} {'─' * 21}[/dim]",
                "",
                f"  [{color}]{_hbar(min(100.0, burst * 20), 20)}[/{color}]"
                f"  [{color}]{burst:.1f}[/{color}] [dim]{_t('consec_edits')} · {label}[/dim]",
            ]

        # ── Agentes ──────────────────────────────────────────────────────
        if session.agent_calls > 0:
            lines += [
                "",
                f"  [dim]{_t('sec_subagents')} ({session.agent_calls} {_t('invocations')}) {'─' * 16}[/dim]",
                "",
            ]
            for subtype, cnt in list(session.agent_subtype_breakdown.items())[:4]:
                lines.append(f"  [dim]· {subtype[:34]:<34}  {cnt}×[/dim]")
            if not session.agent_subtype_breakdown:
                lines.append(f"  [{p}]{session.agent_calls}[/{p}] [dim]{_t('no_subtype')}[/dim]")

        # ── Continuidade ─────────────────────────────────────────────────
        if session.cross_session_files:
            lines += [
                "",
                f"  [dim]{_t('sec_continuity')}[/dim]",
                "",
            ]
            for fp in session.cross_session_files[:4]:
                name = fp.split("/")[-1]
                lines.append(f"  [dim]↩  {name}[/dim]")

        # ── Duração média por tool ────────────────────────────────────────
        if tool_durations:
            mx_dur = max(tool_durations.values(), default=1)
            lines += [
                "",
                f"  [dim]{_t('sec_avg_duration')} {'─' * 21}[/dim]",
                "",
            ]
            for tool, avg_ms in sorted(tool_durations.items(), key=lambda x: -x[1])[:6]:
                bar_len = max(1, int((avg_ms / mx_dur) * 16))
                bar = "█" * bar_len + "░" * (16 - bar_len)
                dur_str = f"{avg_ms/1000:.1f}s" if avg_ms >= 1000 else f"{avg_ms:.0f}ms"
                lines.append(
                    f"  [dim]{tool:<12}[/dim]  [{p}]{bar}[/{p}]  [{p}]{dur_str:>6}[/{p}] [dim]{_t('avg')}[/dim]"
                )

        self.update("\n".join(lines))


class InsightsWidget(Static):
    def show_loading(self) -> None:
        t = theme()
        cursor = "█" if datetime.now().second % 2 == 0 else "░"
        self.update(
            f"\n  [bold]{_t('insights_title')}[/bold]\n"
            f"  [dim]{'─' * 50}[/dim]\n\n"
            f"  [{t['secondary']}]{_t('analyzing')} {cursor}[/{t['secondary']}]\n\n"
            f"  [dim]{_t('analyzing_wait')}[/dim]"
        )

    def update_insights(self, insights: list[dict]) -> None:
        t = theme()
        CAT_COLOR = {
            "warning":  t["warning"],
            "tip":      t["tip"],
            "strength": t["strength"],
            "info":     t["info"],
        }
        CAT_LABEL = {
            "warning":  _t("cat_warning"),
            "tip":      _t("cat_tip"),
            "strength": _t("cat_strength"),
            "info":     _t("cat_info"),
        }
        lines = [
            f"\n  [bold]{_t('insights_title')}[/bold]\n"
            f"  [dim]{'─' * 50}[/dim]\n"
        ]
        for ins in insights:
            cat   = ins.get("category", "info")
            icon  = CATEGORY_ICON.get(cat, "·")
            color = CAT_COLOR.get(cat, t["secondary"])
            label = CAT_LABEL.get(cat, "INFO")
            title = ins.get("title", "")
            detail = ins.get("detail", "")
            lines.append(f"  [{color}]{icon} [{label}][/{color}]  [bold]{title}[/bold]")
            # Word-wrap detail at 62 chars
            words, buf = detail.split(), "       "
            for w in words:
                if len(buf) + len(w) + 1 > 62:
                    lines.append(f"  [dim]{buf.strip()}[/dim]")
                    buf = "  " + w
                else:
                    buf += " " + w
            if buf.strip():
                lines.append(f"  [dim]{buf.strip()}[/dim]")
            lines.append("")
        self.update("\n".join(lines))


class HistoryWidget(Static):
    def update_history(self, history: List[DailyStats]) -> None:
        t = theme()
        p = t["secondary"]
        today = datetime.now().strftime("%Y-%m-%d")
        lines = [
            f"\n  [bold]{_t('history_title')}[/bold]  [dim]{_t('goal')}: {DAILY_GOAL} {_t('tools_per_day')}[/dim]",
            f"  [dim]{'─' * 56}[/dim]\n",
        ]
        mx = max((d.total_tools for d in history), default=1)
        for d in history:
            is_today = d.date == today
            date_str = f"[{t['primary']}]{d.date}[/{t['primary']}]" if is_today else f"[dim]{d.date}[/dim]"
            if d.total_tools == 0:
                lines.append(f"  {date_str}  [dim]{'─' * 20}  {_t('no_activity')}[/dim]")
                continue
            bar_len = max(1, int((d.total_tools / mx) * 20))
            bar = "█" * bar_len + "░" * (20 - bar_len)
            goal_ok = d.total_tools >= DAILY_GOAL
            meta = f"[{t['strength']}]✓[/{t['strength']}]" if goal_ok else f"[dim]{min(99, int(d.total_tools / DAILY_GOAL * 100)):>2}%[/dim]"
            today_tag = f"  [{t['primary']}]◀ {_t('today')}[/{t['primary']}]" if is_today else ""
            lines.append(
                f"  {date_str}  [{p}]{bar}[/{p}]"
                f"  [bold]{d.total_tools:>4}[/bold] {meta}"
                f"  [dim]edit {d.edit_count:<4}  bash {d.bash_count:<4}  {_fmt_duration(d.active_minutes):>7}[/dim]"
                f"{today_tag}"
            )

        active = [d for d in history if d.total_tools > 0]
        if active:
            avg_t = sum(d.total_tools for d in active) / len(active)
            avg_m = sum(d.active_minutes for d in active) / len(active)
            days_hit = sum(1 for d in history if d.total_tools >= DAILY_GOAL)
            goal_bar = "█" * days_hit + "░" * (len(history) - days_hit)
            lines += [
                "",
                f"  [dim]{'─' * 56}[/dim]",
                "",
                f"  [dim]{_t('daily_avg'):<15}[/dim][{p}]{avg_t:.0f}[/{p}] [dim]{_t('tools')}  ({_t('active_days')})[/dim]",
                f"  [dim]{_t('avg_time'):<15}[/dim][{p}]{_fmt_duration(avg_m)}[/{p}]",
                f"  [dim]{_t('goal_reached'):<15}[/dim][{p}]{goal_bar}[/{p}]  [dim]{days_hit}/{len(history)} {_t('days')}[/dim]",
            ]
        self.update("\n".join(lines))


class ProjectsWidget(Static):
    def update_projects(self, projects: List[ProjectStats]) -> None:
        t = theme()
        p = t["secondary"]
        lines = [
            f"\n  [bold]{_t('projects_title')} ({len(projects)})[/bold]",
            f"  [dim]{'─' * 56}[/dim]\n",
        ]
        if not projects:
            lines.append(f"  [dim]{_t('no_projects')}[/dim]")
            lines.append(f"  [dim]{_t('no_projects_hint')}[/dim]")
            self.update("\n".join(lines))
            return

        mx_edits = max((pr.total_edits for pr in projects), default=1)
        for pr in projects:
            bar_len = max(0, int((pr.total_edits / mx_edits) * 22))
            bar = "█" * bar_len + "░" * (22 - bar_len)
            health_color = t["strength"] if pr.bash_success_rate >= 80 else (
                t["warning"] if 0 < pr.bash_success_rate < 70 else t["tip"]
            )
            lang_str = "  ".join(f".{ext}({cnt})" for ext, cnt in list(pr.language_breakdown.items())[:3])
            bash_str = (
                f"[{health_color}]bash {pr.bash_success_rate:.0f}%[/{health_color}]"
                if pr.bash_success_rate > 0 else "[dim]bash —[/dim]"
            )
            sess_label = _t("session_plural") if pr.total_sessions != 1 else _t("session_singular")
            lines += [
                f"  [{p}]◈[/{p}] [bold]{pr.project_name}[/bold]"
                f"  [dim]{pr.last_seen}  ·  {pr.total_sessions} {sess_label}[/dim]",
                f"    [{p}]{bar}[/{p}]"
                f"  [bold]{pr.total_edits}[/bold] [dim]edits[/dim]"
                f"  [dim]{pr.total_bash} bash  {pr.unique_files} {_t('files_abbr')}  {_fmt_duration(pr.total_minutes)}[/dim]",
                f"    {bash_str}  [dim]{lang_str if lang_str else '—'}[/dim]",
                "",
            ]
        self.update("\n".join(lines))


class MultiSessionWidget(Static):
    """Exibe todas as sessões ativas do Claude Code lidas diretamente dos .jsonl."""

    def update_sessions(self, sessions: List[LiveSessionData]) -> None:
        t  = theme()
        p  = t["primary"]
        s  = t["secondary"]
        w  = t["warning"]

        active   = [x for x in sessions if x.is_active]
        inactive = [x for x in sessions if not x.is_active]

        lines = [
            f"\n  [bold]{_t('sessions_title')} ({len(sessions)})[/bold]"
            f"  [dim]·  {len(active)} {_t('active')}  ·  {len(inactive)} {_t('recent')}[/dim]",
            f"  [dim]{'─' * 58}[/dim]\n",
        ]

        if not sessions:
            lines += [
                f"  [dim]{_t('no_sessions')}[/dim]",
                f"  [dim]{_t('no_sessions_hint')}[/dim]",
            ]
            self.update("\n".join(lines))
            return

        def _session_card(sess: LiveSessionData) -> None:
            if sess.is_active:
                status_str = f"[bold green]● LIVE[/bold green]"
            else:
                # Mostrar há quanto tempo foi a última atividade
                try:
                    last = datetime.fromisoformat(sess.last_activity.replace("Z", "+00:00"))
                    delta_m = int((datetime.now().astimezone() - last).total_seconds() / 60)
                    ago = f"{delta_m}m {_t('ago')}" if delta_m < 60 else f"{delta_m // 60}h {_t('ago')}"
                except Exception:
                    ago = _t("inactive")
                status_str = f"[dim]○ {ago}[/dim]"

            ts = sess.last_activity[11:16] if len(sess.last_activity) >= 16 else "—"
            cwd_short = sess.cwd.replace(str(Path.home()), "~") if sess.cwd else "—"

            mx = max(sess.total_tools, 1)
            bar_len = min(22, max(1, int((sess.total_tools / 200) * 22)))
            bar = "█" * bar_len + "░" * (22 - bar_len)

            tok_in  = f"{sess.input_tokens/1000:.0f}K"  if sess.input_tokens  >= 1000 else str(sess.input_tokens)
            tok_out = f"{sess.output_tokens/1000:.0f}K" if sess.output_tokens >= 1000 else str(sess.output_tokens)
            tok_cac = f"{sess.cache_read_tokens/1000:.0f}K" if sess.cache_read_tokens >= 1000 else str(sess.cache_read_tokens)

            think_str = f"  [dim]💭 {sess.thinking_count}[/dim]" if sess.thinking_count else ""
            branch_str = f"  [dim]{sess.git_branch}[/dim]" if sess.git_branch and sess.git_branch != "HEAD" else ""
            model_short = sess.model.replace("claude-", "").replace("-2025", "")[:18] if sess.model else ""

            lines.append(
                f"  [{p}]◉[/{p}] [bold]{sess.project_name}[/bold]"
                f"  {status_str}  [dim]{ts}[/dim]{branch_str}"
            )
            lines.append(f"  [dim]  {cwd_short[:52]}[/dim]")
            lines.append(
                f"    [{p if sess.is_active else 'dim'}]{bar}[/{p if sess.is_active else 'dim'}]"
                f"  [bold]{sess.total_tools}[/bold] [dim]{_t('tools')}[/dim]"
                f"  [dim]{sess.edit_count}✎  {sess.bash_count}▶  {sess.read_count}◎[/dim]"
                f"{think_str}"
            )

            # Subagentes
            if sess.subagents:
                sa_parts = [f"[{s}]{sa.agent_type}[/{s}] [dim]({sa.tool_calls})[/dim]"
                            for sa in sess.subagents[:3]]
                lines.append(f"    [dim]{_t('subagents_lbl')}[/dim] {'  '.join(sa_parts)}")

            # Tokens
            if sess.input_tokens > 0:
                lines.append(
                    f"    [dim]{_t('tokens')}  ↓{tok_in} in  ↑{tok_out} out"
                    f"  ⚡{tok_cac} cache[/dim]"
                    + (f"  [dim]{model_short}[/dim]" if model_short else "")
                )
            lines.append("")

        for sess in active:
            _session_card(sess)

        if inactive:
            lines.append(f"  [dim]{_t('sec_recent')} {'─' * 45}[/dim]\n")
            for sess in inactive[:5]:
                _session_card(sess)

        self.update("\n".join(lines))


# ── App principal ──────────────────────────────────────────────────────────

class ProductivityApp(App):
    TITLE = "PRODUCTIVITY.SYS"
    BINDINGS = [
        Binding("1", "tab_dashboard",    _t("bind_dashboard")),
        Binding("2", "tab_insights",     _t("bind_insights")),
        Binding("3", "tab_history",      _t("bind_history")),
        Binding("4", "tab_projects",     _t("bind_projects")),
        Binding("5", "tab_sessions",     _t("bind_sessions")),
        Binding("t", "toggle_theme",     _t("bind_theme")),
        Binding("l", "toggle_language",  _t("bind_language")),
        Binding("r", "force_refresh",    _t("bind_refresh")),
        Binding("e", "export",           _t("bind_export")),
        Binding("q", "quit",             _t("bind_quit")),
    ]

    def compose(self) -> ComposeResult:
        yield HeaderWidget(id="header")
        yield Footer(id="footer-bar")
        with TabbedContent(initial="tab-dashboard"):
            with TabPane(f"  {_t('tab_dashboard')}  ", id="tab-dashboard"):
                with Horizontal(id="dashboard-layout"):
                    with Vertical(id="left-col"):
                        yield ActivityWidget(id="activity")
                    with Vertical(id="right-col"):
                        yield ChartWidget(id="chart-area")
                        yield StatsWidget(id="stats-area")
            with TabPane(f"  {_t('tab_insights')}  ", id="tab-insights"):
                with ScrollableContainer(id="insights-scroll"):
                    yield InsightsWidget(id="insights-content")
            with TabPane(f"  {_t('tab_history')}  ", id="tab-history"):
                with ScrollableContainer(id="history-scroll"):
                    yield HistoryWidget(id="history-content")
            with TabPane(f"  {_t('tab_projects')}  ", id="tab-projects"):
                with ScrollableContainer(id="projects-scroll"):
                    yield ProjectsWidget(id="projects-content")
            with TabPane(f"  {_t('tab_sessions')}  ", id="tab-sessions"):
                with ScrollableContainer(id="sessions-scroll"):
                    yield MultiSessionWidget(id="sessions-content")

    def on_mount(self) -> None:
        self._session: Optional[SessionStats] = None
        self._history: List[DailyStats] = []
        self._projects: List[ProjectStats] = []
        self._live_sessions: List[LiveSessionData] = []
        self._tool_durations: Dict[str, float] = {}
        self._insights_loading = False
        # Aplica tema salvo
        if _current_theme_key != "one_dark":
            self.screen.add_class(THEMES[_current_theme_key]["css_class"])
        self._insights_last_refresh = 0.0

        self._load_db_data()
        self._maybe_refresh_insights()

        self.set_interval(DASHBOARD_REFRESH_SECS, self._load_db_data)
        self.set_interval(1.0,  self._tick)
        self.set_interval(30.0, self._maybe_refresh_insights)

    def _tick(self) -> None:
        self.query_one("#header", HeaderWidget)._update_clock()

    def _load_db_data(self) -> None:
        real_session   = get_current_session_stats()
        self._session  = real_session or _DEMO_SESSION
        self._history  = get_daily_history(7) or _DEMO_HISTORY
        self._projects = get_all_project_stats() or _DEMO_PROJECTS
        _is_demo       = real_session is None

        # Leitura direta dos .jsonl para dados em tempo real
        try:
            live = get_live_sessions(active_only=False)
            self._live_sessions = live if live else _DEMO_LIVE_SESSIONS
        except Exception:
            self._live_sessions = _DEMO_LIVE_SESSIONS

        # Duração média por tool: prioriza dados dos .jsonl, cai no DB como fallback
        self._tool_durations = aggregate_tool_durations(self._live_sessions)
        if not self._tool_durations:
            self._tool_durations = get_tool_duration_stats() or _DEMO_TOOL_DURATIONS

        # Atividade recente: usa eventos do .jsonl se disponível (inclui thinking, duração)
        activity_events = self._session.recent_events
        if self._live_sessions:
            most_recent = self._live_sessions[0]
            # Usar eventos do jsonl se a sessão corresponde ou é mais recente
            if most_recent.total_tools > 0:
                activity_events = list(reversed(most_recent.events[-15:]))

        header = self.query_one("#header", HeaderWidget)
        header.set_project(self._session.project_name or "")
        header.set_active(self._session.is_active)
        header.set_demo(_is_demo)
        self.query_one("#activity",          ActivityWidget).update_events(activity_events)
        self.query_one("#chart-area",        ChartWidget).update_chart(self._session.hourly_activity)
        self.query_one("#stats-area",        StatsWidget).update_stats(self._session, self._tool_durations)
        self.query_one("#history-content",   HistoryWidget).update_history(self._history)
        self.query_one("#projects-content",  ProjectsWidget).update_projects(self._projects)
        self.query_one("#sessions-content",  MultiSessionWidget).update_sessions(self._live_sessions)

    def _maybe_refresh_insights(self) -> None:
        now = time.monotonic()
        if self._insights_loading:
            return
        if now - self._insights_last_refresh < INSIGHTS_REFRESH_SECS:
            return
        self._insights_last_refresh = now
        self._refresh_insights_async()

    def _refresh_insights_async(self) -> None:
        if self._insights_loading:
            return
        self._insights_loading = True
        self.query_one("#insights-content", InsightsWidget).show_loading()
        session = self._session or _DEMO_SESSION
        history = self._history or _DEMO_HISTORY
        threading.Thread(
            target=self._insights_thread,
            args=(session, history),
            daemon=True,
        ).start()

    def _insights_thread(self, session: SessionStats, history: List[DailyStats]) -> None:
        result = generate_insights(session, history)
        self.call_from_thread(self._on_insights_done, result)

    def _on_insights_done(self, result: list[dict]) -> None:
        self._insights_loading = False
        self.query_one("#insights-content", InsightsWidget).update_insights(result)

    # ── Actions ────────────────────────────────────────────────────────────

    def action_toggle_theme(self) -> None:
        global _current_theme_key
        idx = (THEME_ORDER.index(_current_theme_key) + 1) % len(THEME_ORDER)
        old_class = THEMES[_current_theme_key]["css_class"]
        self.screen.remove_class(old_class)
        _current_theme_key = THEME_ORDER[idx]
        new_class = THEMES[_current_theme_key]["css_class"]
        self.screen.add_class(new_class)
        # Persiste preferência
        _save_prefs({**_load_prefs(), "theme": _current_theme_key})
        self._load_db_data()
        self.query_one("#header", HeaderWidget)._update_clock()

    def action_toggle_language(self) -> None:
        import claude_productivity.i18n as _i18n
        _LANG_CYCLE = ["pt-BR", "en", "es"]
        cur = _i18n.LANG
        nxt = _LANG_CYCLE[(_LANG_CYCLE.index(cur) + 1) % len(_LANG_CYCLE)] if cur in _LANG_CYCLE else "en"
        set_language(nxt)
        # Persiste preferência
        _save_prefs({**_load_prefs(), "language": nxt})
        # Re-renderiza todos os widgets com o novo idioma
        self._load_db_data()
        self.query_one("#header", HeaderWidget)._update_clock()

    def action_force_refresh(self) -> None:
        self._load_db_data()
        self._insights_last_refresh = 0.0
        self._maybe_refresh_insights()

    def action_tab_dashboard(self) -> None:
        self.query_one(TabbedContent).active = "tab-dashboard"

    def action_tab_insights(self) -> None:
        self.query_one(TabbedContent).active = "tab-insights"

    def action_tab_history(self) -> None:
        self.query_one(TabbedContent).active = "tab-history"

    def action_tab_projects(self) -> None:
        self.query_one(TabbedContent).active = "tab-projects"

    def action_tab_sessions(self) -> None:
        self.query_one(TabbedContent).active = "tab-sessions"

    def action_export(self) -> None:
        try:
            from ..exporter import export_xlsx
        except ImportError:
            self.notify(
                _t("openpyxl_missing"),
                title=_t("openpyxl_title"),
                severity="error",
                timeout=8,
            )
            return

        session  = self._session  or _DEMO_SESSION
        history  = self._history  or _DEMO_HISTORY
        projects = self._projects or _DEMO_PROJECTS

        try:
            out_path = export_xlsx(session, history, projects)
            self.notify(
                f"{_t('export_saved')}\n{out_path}",
                title=_t("export_ok_title"),
                severity="information",
                timeout=10,
            )
        except Exception as exc:
            self.notify(
                str(exc)[:120],
                title=_t("export_err_title"),
                severity="error",
                timeout=8,
            )

    CSS = """
    /* ── Layout base (todos os temas) ──────────────────────── */
    #header         { dock: top; height: 3; text-style: bold; padding: 0 2; }
    TabbedContent   { height: 1fr; }
    ContentSwitcher { height: 1fr; }
    TabPane         { padding: 0; }
    Tab             { padding: 0 3; }
    #dashboard-layout { layout: horizontal; height: 1fr; }
    #left-col  { width: 38%; padding: 1 1; overflow-y: auto; }
    #right-col { width: 62%; layout: vertical; }
    #chart-area { height: 1fr; padding: 1 2; }
    #stats-area { height: auto; padding: 1 2; }
    #insights-scroll  { height: 1fr; padding: 1 2; }
    #history-scroll   { height: 1fr; padding: 1 2; }
    #projects-scroll  { height: 1fr; padding: 1 2; }
    #sessions-scroll  { height: 1fr; padding: 1 2; }

    /* ════════════════════════════════════════════════════════
       1. ATOM ONE DARK (padrão — sem classe extra)
       ════════════════════════════════════════════════════════ */
    Screen          { background: #282c34; color: #61afef; }
    Screen TabPane  { background: #282c34; }
    Screen Tabs     { background: #21252b; border-bottom: solid #181a1f; }
    Screen Tab      { color: #2a4a6a;  background: #21252b; }
    Screen Tab.-active { color: #61afef; text-style: bold; background: #2c313a; }
    Screen Tab:hover   { color: #4d8fcc; }
    Screen #header     { background: #21252b; color: #61afef; border-bottom: solid #61afef; }
    Screen #left-col   { background: #21252b; border-right: solid #181a1f; }
    Screen #right-col  { background: #282c34; }
    Screen #chart-area { background: #21252b; color: #61afef; border-bottom: solid #2c313a; }
    Screen #stats-area { background: #1d2026; color: #98c379; overflow-y: auto; }
    Screen #insights-scroll  { background: #282c34; }
    Screen #history-scroll   { background: #282c34; }
    Screen #projects-scroll  { background: #282c34; }
    Screen #sessions-scroll  { background: #282c34; }
    Screen Footer { background: #21252b; color: #abb2bf; }

    /* ════════════════════════════════════════════════════════
       2. MONOKAI PRO  (.monokai)
       ════════════════════════════════════════════════════════ */
    Screen.monokai          { background: #272822; color: #f92672; }
    Screen.monokai TabPane  { background: #272822; }
    Screen.monokai Tabs     { background: #1e1f1c; border-bottom: solid #3a3b33; }
    Screen.monokai Tab      { color: #5a1030; background: #1e1f1c; }
    Screen.monokai Tab.-active { color: #f92672; text-style: bold; background: #2d2e27; }
    Screen.monokai Tab:hover   { color: #c4174d; }
    Screen.monokai #header     { background: #1e1f1c; color: #f92672; border-bottom: solid #f92672; }
    Screen.monokai #left-col   { background: #1e1f1c; border-right: solid #3a3b33; }
    Screen.monokai #right-col  { background: #272822; }
    Screen.monokai #chart-area { background: #1e1f1c; color: #f92672; border-bottom: solid #3a3b33; }
    Screen.monokai #stats-area { background: #1a1b18; color: #a6e22e; overflow-y: auto; }
    Screen.monokai #insights-scroll  { background: #272822; }
    Screen.monokai #history-scroll   { background: #272822; }
    Screen.monokai #projects-scroll  { background: #272822; }
    Screen.monokai #sessions-scroll  { background: #272822; }
    Screen.monokai Footer { background: #1e1f1c; color: #cfcfc2; }

    /* ════════════════════════════════════════════════════════
       3. DRACULA  (.dracula)
       ════════════════════════════════════════════════════════ */
    Screen.dracula          { background: #282a36; color: #bd93f9; }
    Screen.dracula TabPane  { background: #282a36; }
    Screen.dracula Tabs     { background: #21222c; border-bottom: solid #44475a; }
    Screen.dracula Tab      { color: #44475a; background: #21222c; }
    Screen.dracula Tab.-active { color: #bd93f9; text-style: bold; background: #2d2f3f; }
    Screen.dracula Tab:hover   { color: #9a70d6; }
    Screen.dracula #header     { background: #21222c; color: #bd93f9; border-bottom: solid #ff79c6; }
    Screen.dracula #left-col   { background: #21222c; border-right: solid #44475a; }
    Screen.dracula #right-col  { background: #282a36; }
    Screen.dracula #chart-area { background: #21222c; color: #bd93f9; border-bottom: solid #44475a; }
    Screen.dracula #stats-area { background: #1d1e26; color: #8be9fd; overflow-y: auto; }
    Screen.dracula #insights-scroll  { background: #282a36; }
    Screen.dracula #history-scroll   { background: #282a36; }
    Screen.dracula #projects-scroll  { background: #282a36; }
    Screen.dracula #sessions-scroll  { background: #282a36; }
    Screen.dracula Footer { background: #21222c; color: #f8f8f2; }

    /* ════════════════════════════════════════════════════════
       4. NORD  (.nord)
       ════════════════════════════════════════════════════════ */
    Screen.nord          { background: #2e3440; color: #88c0d0; }
    Screen.nord TabPane  { background: #2e3440; }
    Screen.nord Tabs     { background: #3b4252; border-bottom: solid #434c5e; }
    Screen.nord Tab      { color: #4c566a; background: #3b4252; }
    Screen.nord Tab.-active { color: #88c0d0; text-style: bold; background: #434c5e; }
    Screen.nord Tab:hover   { color: #6fa8c0; }
    Screen.nord #header     { background: #3b4252; color: #88c0d0; border-bottom: solid #88c0d0; }
    Screen.nord #left-col   { background: #3b4252; border-right: solid #434c5e; }
    Screen.nord #right-col  { background: #2e3440; }
    Screen.nord #chart-area { background: #3b4252; color: #88c0d0; border-bottom: solid #434c5e; }
    Screen.nord #stats-area { background: #272c36; color: #a3be8c; overflow-y: auto; }
    Screen.nord #insights-scroll  { background: #2e3440; }
    Screen.nord #history-scroll   { background: #2e3440; }
    Screen.nord #projects-scroll  { background: #2e3440; }
    Screen.nord #sessions-scroll  { background: #2e3440; }
    Screen.nord Footer { background: #3b4252; color: #d8dee9; }

    /* ════════════════════════════════════════════════════════
       5. TOKYO NIGHT  (.tokyo-night)
       ════════════════════════════════════════════════════════ */
    Screen.tokyo-night          { background: #1a1b2e; color: #7aa2f7; }
    Screen.tokyo-night TabPane  { background: #1a1b2e; }
    Screen.tokyo-night Tabs     { background: #16213e; border-bottom: solid #292e42; }
    Screen.tokyo-night Tab      { color: #3b4261; background: #16213e; }
    Screen.tokyo-night Tab.-active { color: #7aa2f7; text-style: bold; background: #1e2030; }
    Screen.tokyo-night Tab:hover   { color: #5a80cc; }
    Screen.tokyo-night #header     { background: #16213e; color: #7aa2f7; border-bottom: solid #7aa2f7; }
    Screen.tokyo-night #left-col   { background: #16213e; border-right: solid #292e42; }
    Screen.tokyo-night #right-col  { background: #1a1b2e; }
    Screen.tokyo-night #chart-area { background: #16213e; color: #7aa2f7; border-bottom: solid #292e42; }
    Screen.tokyo-night #stats-area { background: #13141f; color: #9ece6a; overflow-y: auto; }
    Screen.tokyo-night #insights-scroll  { background: #1a1b2e; }
    Screen.tokyo-night #history-scroll   { background: #1a1b2e; }
    Screen.tokyo-night #projects-scroll  { background: #1a1b2e; }
    Screen.tokyo-night #sessions-scroll  { background: #1a1b2e; }
    Screen.tokyo-night Footer { background: #16213e; color: #a9b1d6; }
    """


def run() -> None:
    ProductivityApp().run()


if __name__ == "__main__":
    run()
