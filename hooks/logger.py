#!/usr/bin/env python3
"""
Claude Code hook — captura eventos e persiste no banco local.
Configurado via install.sh no settings.json do Claude Code.

Recebe JSON via stdin com o payload do hook.
"""

from __future__ import annotations

import io
import json
import os
import re
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

# Garante leitura de stdin em UTF-8 no Windows (cmd /c pode usar cp1252 por padrão)
if hasattr(sys.stdin, "buffer"):
    sys.stdin = io.TextIOWrapper(sys.stdin.buffer, encoding="utf-8", errors="replace")

DB_PATH = Path.home() / ".claude" / "productivity.db"


# ---------------------------------------------------------------------------
# DB
# ---------------------------------------------------------------------------

def get_db() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    _migrate(conn)
    return conn


def _migrate(conn: sqlite3.Connection) -> None:
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS sessions (
            session_id  TEXT PRIMARY KEY,
            started_at  TEXT NOT NULL,
            ended_at    TEXT,
            total_tools INTEGER DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS events (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id  TEXT    NOT NULL,
            ts          TEXT    NOT NULL,
            tool_name   TEXT,
            file_path   TEXT,
            command     TEXT,
            extra       TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_events_session   ON events(session_id);
        CREATE INDEX IF NOT EXISTS idx_events_ts        ON events(ts);
        CREATE INDEX IF NOT EXISTS idx_events_file_path ON events(file_path);
        CREATE INDEX IF NOT EXISTS idx_events_tool_name ON events(tool_name);

        CREATE TABLE IF NOT EXISTS pending_starts (
            session_id TEXT NOT NULL,
            tool_name  TEXT NOT NULL,
            started_at TEXT NOT NULL,
            PRIMARY KEY (session_id, tool_name)
        );
    """)
    # Adiciona novas colunas de forma segura (ignora se já existirem)
    for col_sql in [
        "ALTER TABLE events ADD COLUMN exit_code      INTEGER",
        "ALTER TABLE events ADD COLUMN project_name   TEXT",
        "ALTER TABLE events ADD COLUMN file_extension TEXT",
        "ALTER TABLE events ADD COLUMN agent_subtype  TEXT",
        "ALTER TABLE events ADD COLUMN duration_ms    INTEGER",
    ]:
        try:
            conn.execute(col_sql)
        except sqlite3.OperationalError:
            pass  # coluna já existe
    conn.commit()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def extract_file_path(tool_name: str, tool_input: dict) -> str | None:
    for key in ("file_path", "path", "filename"):
        if key in tool_input:
            return tool_input[key]
    return None


def extract_command(tool_name: str, tool_input: dict) -> str | None:
    if tool_name == "Bash":
        return tool_input.get("command", "")[:200]
    return None


def extract_exit_code(tool_name: str, tool_response: dict | None) -> int | None:
    """Extrai código de saída de comandos Bash a partir do tool_response."""
    if tool_name != "Bash" or not isinstance(tool_response, dict):
        return None
    # Formato direto
    for key in ("exit_code", "returncode", "return_code"):
        if key in tool_response:
            try:
                return int(tool_response[key])
            except (ValueError, TypeError):
                pass
    # Formato com lista de content
    content = tool_response.get("content")
    if isinstance(content, list):
        for item in content:
            if isinstance(item, dict):
                for key in ("exit_code", "returncode"):
                    if key in item:
                        try:
                            return int(item[key])
                        except (ValueError, TypeError):
                            pass
    # Fallback: is_error como proxy (True → falhou)
    if "is_error" in tool_response:
        return 1 if tool_response["is_error"] else 0
    return None


def extract_project_name(file_path: str | None) -> str | None:
    """Extrai nome do projeto a partir do caminho do arquivo."""
    if not file_path:
        return None
    parts = Path(file_path).parts
    workspace_markers = {
        "Workspace", "workspace", "Projects", "projects",
        "repos", "src", "code", "dev", "work",
    }
    for i, part in enumerate(parts):
        if part in workspace_markers and i + 1 < len(parts):
            return parts[i + 1]
    # Fallback: terceiro segmento após / e home/<user>/
    if len(parts) >= 4 and parts[1] in ("home", "Users"):
        return parts[3] if len(parts) > 3 else None
    return None


def extract_file_extension(file_path: str | None) -> str | None:
    """Extrai extensão do arquivo sem o ponto, em minúsculas."""
    if not file_path:
        return None
    suffix = Path(file_path).suffix
    return suffix.lstrip(".").lower() if suffix else None


def extract_agent_subtype(tool_name: str, tool_input: dict) -> str | None:
    """Extrai o subtipo do agente quando tool_name == Agent."""
    if tool_name != "Agent":
        return None
    return tool_input.get("subagent_type") or tool_input.get("type") or None


def store_pre_event(conn: sqlite3.Connection, session_id: str, tool_name: str) -> None:
    """Registra o início de um tool use para cálculo posterior de duração."""
    now = datetime.now(timezone.utc).replace(tzinfo=None).isoformat()
    conn.execute("""
        INSERT OR REPLACE INTO pending_starts (session_id, tool_name, started_at)
        VALUES (?, ?, ?)
    """, (session_id, tool_name, now))
    conn.commit()


def pop_pre_event(conn: sqlite3.Connection, session_id: str, tool_name: str) -> str | None:
    """Remove e retorna o timestamp de início de um tool use pendente."""
    row = conn.execute("""
        SELECT started_at FROM pending_starts
        WHERE session_id = ? AND tool_name = ?
    """, (session_id, tool_name)).fetchone()
    if row:
        conn.execute(
            "DELETE FROM pending_starts WHERE session_id = ? AND tool_name = ?",
            (session_id, tool_name),
        )
        conn.commit()
        return row["started_at"]
    return None


def upsert_session(conn: sqlite3.Connection, session_id: str) -> None:
    now = datetime.now(timezone.utc).replace(tzinfo=None).isoformat()
    conn.execute("""
        INSERT INTO sessions (session_id, started_at)
        VALUES (?, ?)
        ON CONFLICT(session_id) DO NOTHING
    """, (session_id, now))
    conn.commit()


def record_event(
    conn: sqlite3.Connection,
    session_id: str,
    tool_name: str,
    file_path: str | None,
    command: str | None,
    extra: dict,
    exit_code: int | None = None,
    project_name: str | None = None,
    file_extension: str | None = None,
    agent_subtype: str | None = None,
    duration_ms: int | None = None,
) -> None:
    now = datetime.now(timezone.utc).replace(tzinfo=None).isoformat()
    conn.execute("""
        INSERT INTO events
            (session_id, ts, tool_name, file_path, command, extra,
             exit_code, project_name, file_extension, agent_subtype, duration_ms)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (session_id, now, tool_name, file_path, command, json.dumps(extra),
          exit_code, project_name, file_extension, agent_subtype, duration_ms))
    conn.execute("""
        UPDATE sessions SET total_tools = total_tools + 1 WHERE session_id = ?
    """, (session_id,))
    conn.commit()


def close_session(conn: sqlite3.Connection, session_id: str) -> None:
    now = datetime.now(timezone.utc).replace(tzinfo=None).isoformat()
    conn.execute("""
        UPDATE sessions SET ended_at = ? WHERE session_id = ?
    """, (now, session_id))
    conn.commit()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    try:
        raw = sys.stdin.read().strip()
        if not raw:
            return

        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            return

        hook_event = os.environ.get("CLAUDE_HOOK_EVENT", "PostToolUse")
        session_id = payload.get("session_id", "unknown")

        conn = get_db()

        if hook_event == "Stop":
            close_session(conn, session_id)
            return

        tool_name     = payload.get("tool_name", "Unknown")
        tool_input    = payload.get("tool_input", {})
        tool_response = payload.get("tool_response")

        if hook_event == "PreToolUse":
            upsert_session(conn, session_id)
            store_pre_event(conn, session_id, tool_name)
            return

        # PostToolUse
        file_path      = extract_file_path(tool_name, tool_input)
        command        = extract_command(tool_name, tool_input)
        exit_code      = extract_exit_code(tool_name, tool_response)
        project_name   = extract_project_name(file_path)
        file_extension = extract_file_extension(file_path)
        agent_subtype  = extract_agent_subtype(tool_name, tool_input)

        pre_ts_str = pop_pre_event(conn, session_id, tool_name)
        duration_ms: int | None = None
        if pre_ts_str:
            try:
                pre_ts = datetime.fromisoformat(pre_ts_str)
                duration_ms = int((datetime.now(timezone.utc).replace(tzinfo=None) - pre_ts).total_seconds() * 1000)
            except (ValueError, TypeError):
                pass

        upsert_session(conn, session_id)
        record_event(
            conn,
            session_id=session_id,
            tool_name=tool_name,
            file_path=file_path,
            command=command,
            extra={},
            exit_code=exit_code,
            project_name=project_name,
            file_extension=file_extension,
            agent_subtype=agent_subtype,
            duration_ms=duration_ms,
        )
    except Exception as exc:
        print(f"[claude-productivity] hook error: {exc}", file=sys.stderr)


if __name__ == "__main__":
    main()
