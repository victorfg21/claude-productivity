"""Leitura direta dos .jsonl de sessões do Claude Code.

Não depende de hooks — lê ~/.claude/projects/**/*.jsonl diretamente.
Fornece dados em tempo real: tool calls, thinking blocks, tokens, subagents.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

CLAUDE_PROJECTS_DIR = Path.home() / ".claude" / "projects"
ACTIVE_THRESHOLD_MINUTES = 10

EDIT_TOOLS  = {"Edit", "Write", "MultiEdit", "NotebookEdit"}
BASH_TOOLS  = {"Bash"}
READ_TOOLS  = {"Read", "Grep", "Glob", "LS"}
AGENT_TOOLS = {"Agent", "Task"}


# ── Dataclasses ────────────────────────────────────────────────────────────

@dataclass
class ParsedEvent:
    ts: str
    event_type: str          # "tool_use" | "thinking" | "tool_result"
    tool_name: str = ""
    tool_id: str = ""
    file_path: str = ""
    command: str = ""
    is_error: bool = False
    duration_ms: int = 0
    thinking_len: int = 0    # tamanho do texto de thinking (chars)


@dataclass
class SubagentSummary:
    agent_id: str
    agent_type: str          # de .meta.json
    slug: str
    tool_calls: int
    edit_count: int
    bash_count: int
    input_tokens: int
    output_tokens: int


@dataclass
class LiveSessionData:
    session_id: str
    project_name: str        # derivado do dir name
    project_dir: str
    cwd: str
    started_at: str
    last_activity: str
    is_active: bool

    total_tools: int
    edit_count: int
    bash_count: int
    read_count: int
    thinking_count: int

    input_tokens: int
    output_tokens: int
    cache_read_tokens: int

    git_branch: str
    version: str
    model: str

    events: List[ParsedEvent] = field(default_factory=list)
    subagents: List[SubagentSummary] = field(default_factory=list)
    tool_durations: Dict[str, List[int]] = field(default_factory=dict)


# ── Helpers ────────────────────────────────────────────────────────────────

def _dir_to_project_name(dir_name: str) -> str:
    """Converte '-home-user-Desktop-Workspace-myapp' → 'myapp'."""
    parts = [p for p in dir_name.split("-") if p]
    # Pular partes comuns de path home
    skip = {"home", "root", "usr", "Desktop", "Workspace", "Users"}
    filtered = [p for p in parts if p not in skip]
    if filtered:
        return filtered[-1]
    return parts[-1] if parts else dir_name


def _ts_delta_ms(ts_start: str, ts_end: str) -> int:
    """Calcula diferença em ms entre dois timestamps ISO8601 com sufixo Z."""
    try:
        t0 = datetime.fromisoformat(ts_start.replace("Z", "+00:00"))
        t1 = datetime.fromisoformat(ts_end.replace("Z", "+00:00"))
        return max(0, int((t1 - t0).total_seconds() * 1000))
    except Exception:
        return 0


def _extract_file_path(tool_name: str, tool_input: dict) -> str:
    """Extrai file_path do input de um tool_use."""
    if tool_name in EDIT_TOOLS | READ_TOOLS:
        return tool_input.get("file_path") or tool_input.get("path") or ""
    return ""


def _extract_command(tool_name: str, tool_input: dict) -> str:
    """Extrai comando de um tool_use Bash."""
    if tool_name in BASH_TOOLS:
        return tool_input.get("command") or ""
    return ""


# ── Parser de subagente ────────────────────────────────────────────────────

def _parse_subagent(jsonl_path: Path, agent_id: str) -> SubagentSummary:
    meta_path = jsonl_path.with_suffix(".meta.json")
    agent_type = slug = ""
    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        agent_type = meta.get("agentType", "")
        slug       = meta.get("description", "")[:40]
    except Exception:
        pass

    tool_calls = edit_count = bash_count = 0
    input_tokens = output_tokens = 0
    pending: Dict[str, str] = {}  # tool_id → ts

    try:
        with open(jsonl_path, encoding="utf-8", errors="replace") as _fh:
            for line in _fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue

                msg = obj.get("message", {})
                usage = msg.get("usage", {})
                if usage:
                    input_tokens  += usage.get("input_tokens", 0)
                    output_tokens += usage.get("output_tokens", 0)

                for block in msg.get("content", []) if isinstance(msg.get("content"), list) else []:
                    if not isinstance(block, dict):
                        continue
                    btype = block.get("type", "")
                    if btype == "tool_use":
                        tool_calls += 1
                        tn = block.get("name", "")
                        if tn in EDIT_TOOLS:  edit_count += 1
                        if tn in BASH_TOOLS:  bash_count += 1
    except Exception:
        pass

    return SubagentSummary(
        agent_id=agent_id,
        agent_type=agent_type or "Agent",
        slug=slug,
        tool_calls=tool_calls,
        edit_count=edit_count,
        bash_count=bash_count,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
    )


# ── Parser de sessão principal ─────────────────────────────────────────────

def parse_session(jsonl_path: Path) -> Optional[LiveSessionData]:
    """Parseia um arquivo .jsonl de sessão e retorna LiveSessionData."""
    session_id   = jsonl_path.stem
    proj_dir     = jsonl_path.parent.name
    project_name = _dir_to_project_name(proj_dir)

    events: List[ParsedEvent] = []
    cwd = started_at = last_activity = git_branch = version = model = ""
    input_tokens = output_tokens = cache_read = thinking_count = 0
    tool_durations: Dict[str, List[int]] = {}

    # tool_id → (ts, tool_name) — para calcular duração
    pending: Dict[str, Tuple[str, str]] = {}

    try:
        _file = open(jsonl_path, encoding="utf-8", errors="replace")
    except Exception:
        return None

    with _file:
        for line in _file:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue

            ts = obj.get("timestamp", "")
            if ts:
                if not started_at:
                    started_at = ts
                last_activity = ts

            if not cwd        and obj.get("cwd"):       cwd        = obj["cwd"]
            if not git_branch and obj.get("gitBranch"): git_branch = obj["gitBranch"]
            if not version    and obj.get("version"):   version    = obj["version"]

            # Ignorar mensagens de subagentes embutidas na sessão principal
            if obj.get("isSidechain"):
                continue

            msg = obj.get("message", {})
            if not isinstance(msg, dict):
                continue

            usage = msg.get("usage", {})
            if usage:
                input_tokens  += usage.get("input_tokens", 0)
                output_tokens += usage.get("output_tokens", 0)
                cache_read    += usage.get("cache_read_input_tokens", 0)
                if not model and msg.get("model"):
                    model = msg["model"]

            content = msg.get("content", [])
            if not isinstance(content, list):
                continue

            for block in content:
                if not isinstance(block, dict):
                    continue
                btype = block.get("type", "")

                if btype == "tool_use":
                    tid  = block.get("id", "")
                    tname = block.get("name", "")
                    tinp  = block.get("input", {}) if isinstance(block.get("input"), dict) else {}
                    pending[tid] = (ts, tname)
                    events.append(ParsedEvent(
                        ts=ts,
                        event_type="tool_use",
                        tool_name=tname,
                        tool_id=tid,
                        file_path=_extract_file_path(tname, tinp),
                        command=_extract_command(tname, tinp),
                    ))

                elif btype == "tool_result":
                    tid      = block.get("tool_use_id", "")
                    is_error = bool(block.get("is_error", False))
                    dur = 0
                    if tid in pending:
                        pending_ts, pending_name = pending.pop(tid)
                        dur = _ts_delta_ms(pending_ts, ts)
                        if dur > 0:
                            tool_durations.setdefault(pending_name, []).append(dur)
                    # Retroativamente atualiza o evento tool_use correspondente
                    for ev in reversed(events):
                        if ev.tool_id == tid:
                            ev.duration_ms = dur
                            ev.is_error    = is_error
                            break

                elif btype == "thinking":
                    thinking_count += 1
                    t_len = len(block.get("thinking", ""))
                    events.append(ParsedEvent(
                        ts=ts,
                        event_type="thinking",
                        thinking_len=t_len,
                    ))

    # Subagentes
    subagents: List[SubagentSummary] = []
    subagents_dir = jsonl_path.parent / session_id / "subagents"
    if subagents_dir.exists():
        for sa_jsonl in sorted(subagents_dir.glob("*.jsonl")):
            subagents.append(_parse_subagent(sa_jsonl, sa_jsonl.stem))

    mtime    = jsonl_path.stat().st_mtime
    is_active = (datetime.now().timestamp() - mtime) < (ACTIVE_THRESHOLD_MINUTES * 60)

    tool_events = [e for e in events if e.event_type == "tool_use"]

    return LiveSessionData(
        session_id=session_id,
        project_name=project_name,
        project_dir=proj_dir,
        cwd=cwd,
        started_at=started_at,
        last_activity=last_activity,
        is_active=is_active,
        total_tools=len(tool_events),
        edit_count=sum(1 for e in tool_events if e.tool_name in EDIT_TOOLS),
        bash_count=sum(1 for e in tool_events if e.tool_name in BASH_TOOLS),
        read_count=sum(1 for e in tool_events if e.tool_name in READ_TOOLS),
        thinking_count=thinking_count,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cache_read_tokens=cache_read,
        git_branch=git_branch,
        version=version,
        model=model,
        events=events[-30:],
        subagents=subagents,
        tool_durations=tool_durations,
    )


# ── API pública ────────────────────────────────────────────────────────────

def scan_sessions(active_only: bool = True,
                  max_sessions: int = 20,
                  active_minutes: int = ACTIVE_THRESHOLD_MINUTES) -> List[Path]:
    """Retorna paths de .jsonl ordenados por mtime desc."""
    if not CLAUDE_PROJECTS_DIR.exists():
        return []

    cutoff = datetime.now().timestamp() - active_minutes * 60
    paths: List[Tuple[float, Path]] = []

    for proj_dir in CLAUDE_PROJECTS_DIR.iterdir():
        if not proj_dir.is_dir():
            continue
        for jsonl in proj_dir.glob("*.jsonl"):
            mtime = jsonl.stat().st_mtime
            if active_only and mtime < cutoff:
                continue
            paths.append((mtime, jsonl))

    paths.sort(key=lambda x: x[0], reverse=True)
    return [p for _, p in paths[:max_sessions]]


def get_live_sessions(active_only: bool = True) -> List[LiveSessionData]:
    """Retorna sessões parseadas diretamente dos .jsonl do Claude Code."""
    result = []
    for path in scan_sessions(active_only=active_only):
        data = parse_session(path)
        if data:
            result.append(data)
    return result


def aggregate_tool_durations(sessions: List[LiveSessionData]) -> Dict[str, float]:
    """Agrega duração média por tipo de tool em todas as sessões."""
    combined: Dict[str, List[int]] = {}
    for s in sessions:
        for tool, durs in s.tool_durations.items():
            combined.setdefault(tool, []).extend(durs)
    return {
        tool: sum(durs) / len(durs)
        for tool, durs in combined.items()
        if durs
    }
