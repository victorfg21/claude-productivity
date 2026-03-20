"""Camada de acesso ao banco SQLite."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional

DB_PATH = Path.home() / ".claude" / "productivity.db"

TOOL_CATEGORIES = {
    "Edit":      "code",
    "Write":     "code",
    "MultiEdit": "code",
    "Read":      "read",
    "Glob":      "read",
    "Grep":      "read",
    "Bash":      "bash",
    "Agent":     "agent",
    "WebFetch":  "research",
    "WebSearch": "research",
}


@dataclass
class SessionStats:
    session_id: str
    started_at: str
    ended_at: Optional[str]
    total_tools: int
    duration_minutes: float
    edit_count: int
    read_count: int
    bash_count: int
    unique_files: int
    repeated_files: List[tuple]        # (file_path, count)
    hourly_activity: List[int]         # 24 buckets
    recent_events: List[dict]
    # Novos campos enriquecidos
    bash_success_rate: float = 0.0     # % de Bash com exit_code = 0
    language_breakdown: Dict[str, int] = field(default_factory=dict)  # {"cs": 23, ...}
    project_name: Optional[str] = None
    agent_calls: int = 0
    avg_edit_burst: float = 0.0        # média de edits consecutivos
    cross_session_files: List[str] = field(default_factory=list)
    is_active: bool = True
    agent_subtype_breakdown: Dict[str, int] = field(default_factory=dict)


@dataclass
class DailyStats:
    date: str
    total_tools: int
    total_sessions: int
    edit_count: int
    bash_count: int
    unique_files: int
    active_minutes: float


@dataclass
class ProjectStats:
    project_name: str
    total_sessions: int
    total_edits: int
    total_bash: int
    total_reads: int
    unique_files: int
    total_minutes: float
    last_seen: str
    bash_success_rate: float
    language_breakdown: Dict[str, int]


def _migrate_reader(conn: sqlite3.Connection) -> None:
    """Garante que as colunas novas existam em bancos criados por versões anteriores."""
    for col_sql in [
        "ALTER TABLE events ADD COLUMN exit_code      INTEGER",
        "ALTER TABLE events ADD COLUMN project_name   TEXT",
        "ALTER TABLE events ADD COLUMN file_extension TEXT",
        "ALTER TABLE events ADD COLUMN agent_subtype  TEXT",
        "CREATE INDEX IF NOT EXISTS idx_events_file_path ON events(file_path)",
        "CREATE INDEX IF NOT EXISTS idx_events_tool_name ON events(tool_name)",
    ]:
        try:
            conn.execute(col_sql)
        except sqlite3.OperationalError:
            pass
    conn.commit()


def get_db() -> sqlite3.Connection:
    if not DB_PATH.exists():
        raise FileNotFoundError(
            f"Banco não encontrado em {DB_PATH}.\n"
            "Execute install.sh para configurar os hooks."
        )
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    _migrate_reader(conn)
    return conn


def _tool_counts(conn: sqlite3.Connection, session_id: str) -> dict:
    rows = conn.execute("""
        SELECT tool_name, COUNT(*) as cnt
        FROM events WHERE session_id = ?
        GROUP BY tool_name
    """, (session_id,)).fetchall()

    counts: dict[str, int] = {}
    for r in rows:
        cat = TOOL_CATEGORIES.get(r["tool_name"], "other")
        counts[cat] = counts.get(cat, 0) + r["cnt"]
    return counts


def _bash_success_rate(conn: sqlite3.Connection, session_id: str) -> float:
    """Calcula % de comandos Bash que tiveram exit_code = 0."""
    row = conn.execute("""
        SELECT
            COUNT(*) FILTER (WHERE tool_name='Bash' AND exit_code IS NOT NULL) as total,
            COUNT(*) FILTER (WHERE tool_name='Bash' AND exit_code = 0)         as ok
        FROM events WHERE session_id = ?
    """, (session_id,)).fetchone()
    if not row or not row["total"]:
        return 0.0
    return round((row["ok"] / row["total"]) * 100, 1)


def _language_breakdown(conn: sqlite3.Connection, session_id: str) -> Dict[str, int]:
    """Retorna contagem de edits por extensão de arquivo (top 5)."""
    rows = conn.execute("""
        SELECT file_extension, COUNT(*) as cnt
        FROM events
        WHERE session_id = ?
          AND file_extension IS NOT NULL
          AND tool_name IN ('Edit', 'Write', 'MultiEdit')
        GROUP BY file_extension
        ORDER BY cnt DESC
        LIMIT 5
    """, (session_id,)).fetchall()
    return {r["file_extension"]: r["cnt"] for r in rows}


def _project_name(conn: sqlite3.Connection, session_id: str) -> Optional[str]:
    """Retorna o projeto mais frequente na sessão."""
    row = conn.execute("""
        SELECT project_name, COUNT(*) as cnt
        FROM events
        WHERE session_id = ? AND project_name IS NOT NULL
        GROUP BY project_name
        ORDER BY cnt DESC
        LIMIT 1
    """, (session_id,)).fetchone()
    return row["project_name"] if row else None


def _agent_calls(conn: sqlite3.Connection, session_id: str) -> int:
    row = conn.execute("""
        SELECT COUNT(*) as cnt FROM events
        WHERE session_id = ? AND tool_name = 'Agent'
    """, (session_id,)).fetchone()
    return row["cnt"] if row else 0


def _avg_edit_burst(conn: sqlite3.Connection, session_id: str) -> float:
    """Calcula média de edits consecutivos sem read/bash no meio."""
    rows = conn.execute("""
        SELECT tool_name FROM events
        WHERE session_id = ?
        ORDER BY ts ASC
    """, (session_id,)).fetchall()

    edit_tools = {"Edit", "Write", "MultiEdit"}
    bursts: list[int] = []
    current = 0
    for r in rows:
        if r["tool_name"] in edit_tools:
            current += 1
        else:
            if current > 0:
                bursts.append(current)
            current = 0
    if current > 0:
        bursts.append(current)
    return round(sum(bursts) / len(bursts), 1) if bursts else 0.0


def _agent_subtype_breakdown(conn: sqlite3.Connection, session_id: str) -> Dict[str, int]:
    """Retorna contagem de chamadas de Agent por subtipo."""
    rows = conn.execute("""
        SELECT agent_subtype, COUNT(*) as cnt
        FROM events
        WHERE session_id = ? AND tool_name = 'Agent' AND agent_subtype IS NOT NULL
        GROUP BY agent_subtype
        ORDER BY cnt DESC
        LIMIT 5
    """, (session_id,)).fetchall()
    return {r["agent_subtype"]: r["cnt"] for r in rows}


def _cross_session_files(conn: sqlite3.Connection, session_id: str) -> List[str]:
    """Retorna arquivos da sessão atual que também foram editados em sessões anteriores."""
    rows = conn.execute("""
        SELECT DISTINCT e.file_path
        FROM events e
        WHERE e.session_id = ?
          AND e.file_path IS NOT NULL
          AND e.tool_name IN ('Edit', 'Write', 'MultiEdit')
          AND EXISTS (
              SELECT 1 FROM events e2
              JOIN sessions s2 ON e2.session_id = s2.session_id
              WHERE e2.file_path = e.file_path
                AND e2.session_id != ?
                AND e2.tool_name IN ('Edit', 'Write', 'MultiEdit')
                AND s2.started_at < (
                    SELECT started_at FROM sessions WHERE session_id = ?
                )
          )
        LIMIT 5
    """, (session_id, session_id, session_id)).fetchall()
    return [r["file_path"] for r in rows]


def get_current_session_stats() -> Optional[SessionStats]:
    try:
        conn = get_db()
    except FileNotFoundError:
        return None
    try:
        session = conn.execute("""
            SELECT * FROM sessions ORDER BY started_at DESC LIMIT 1
        """).fetchone()
        if not session:
            return None

        sid = session["session_id"]
        started = datetime.fromisoformat(session["started_at"])
        ended_raw = session["ended_at"]
        ended = datetime.fromisoformat(ended_raw) if ended_raw else datetime.now(timezone.utc).replace(tzinfo=None)
        duration = (ended - started).total_seconds() / 60

        counts = _tool_counts(conn, sid)

        unique_files = conn.execute("""
            SELECT COUNT(DISTINCT file_path) FROM events
            WHERE session_id = ? AND file_path IS NOT NULL
        """, (sid,)).fetchone()[0]

        repeated = conn.execute("""
            SELECT file_path, COUNT(*) as cnt FROM events
            WHERE session_id = ? AND file_path IS NOT NULL
            GROUP BY file_path HAVING cnt >= 3
            ORDER BY cnt DESC LIMIT 5
        """, (sid,)).fetchall()

        # hourly activity (0-23)
        hourly = [0] * 24
        rows = conn.execute("""
            SELECT strftime('%H', ts) as hr, COUNT(*) as cnt
            FROM events WHERE session_id = ?
            GROUP BY hr
        """, (sid,)).fetchall()
        for r in rows:
            hourly[int(r["hr"])] += r["cnt"]

        recent = conn.execute("""
            SELECT ts, tool_name, file_path, command
            FROM events WHERE session_id = ?
            ORDER BY ts DESC LIMIT 12
        """, (sid,)).fetchall()

        return SessionStats(
            session_id=sid,
            started_at=session["started_at"],
            ended_at=ended_raw,
            total_tools=session["total_tools"],
            duration_minutes=duration,
            edit_count=counts.get("code", 0),
            read_count=counts.get("read", 0),
            bash_count=counts.get("bash", 0),
            unique_files=unique_files,
            repeated_files=[(r["file_path"], r["cnt"]) for r in repeated],
            hourly_activity=hourly,
            recent_events=[dict(r) for r in recent],
            # Novos campos
            bash_success_rate=_bash_success_rate(conn, sid),
            language_breakdown=_language_breakdown(conn, sid),
            project_name=_project_name(conn, sid),
            agent_calls=_agent_calls(conn, sid),
            avg_edit_burst=_avg_edit_burst(conn, sid),
            cross_session_files=_cross_session_files(conn, sid),
            is_active=session["ended_at"] is None,
            agent_subtype_breakdown=_agent_subtype_breakdown(conn, sid),
        )
    finally:
        conn.close()


def get_all_project_stats() -> List[ProjectStats]:
    """Retorna métricas agregadas por projeto, ordenado por uso recente."""
    try:
        conn = get_db()
    except FileNotFoundError:
        return []
    try:
        rows = conn.execute("""
            SELECT
                e.project_name,
                COUNT(DISTINCT e.session_id)                                                    AS total_sessions,
                SUM(CASE WHEN e.tool_name IN ('Edit','Write','MultiEdit') THEN 1 ELSE 0 END)   AS edits,
                SUM(CASE WHEN e.tool_name = 'Bash'                        THEN 1 ELSE 0 END)   AS bash,
                SUM(CASE WHEN e.tool_name IN ('Read','Grep','Glob')        THEN 1 ELSE 0 END)   AS reads,
                COUNT(DISTINCT e.file_path)                                                     AS unique_files,
                MAX(e.ts)                                                                       AS last_seen,
                COUNT(*) FILTER (WHERE e.tool_name='Bash' AND e.exit_code IS NOT NULL)         AS bash_total,
                COUNT(*) FILTER (WHERE e.tool_name='Bash' AND e.exit_code = 0)                 AS bash_ok
            FROM events e
            WHERE e.project_name IS NOT NULL
            GROUP BY e.project_name
            ORDER BY MAX(e.ts) DESC
            LIMIT 20
        """).fetchall()

        result: List[ProjectStats] = []
        for r in rows:
            minutes_row = conn.execute("""
                SELECT SUM(
                    (julianday(COALESCE(s.ended_at, datetime('now'))) - julianday(s.started_at)) * 1440
                )
                FROM sessions s
                WHERE s.session_id IN (
                    SELECT DISTINCT session_id FROM events WHERE project_name = ?
                )
            """, (r["project_name"],)).fetchone()
            minutes = float(minutes_row[0] or 0)

            lang_rows = conn.execute("""
                SELECT file_extension, COUNT(*) AS cnt
                FROM events
                WHERE project_name = ?
                  AND file_extension IS NOT NULL
                  AND tool_name IN ('Edit', 'Write', 'MultiEdit')
                GROUP BY file_extension
                ORDER BY cnt DESC
                LIMIT 3
            """, (r["project_name"],)).fetchall()
            lang = {lr["file_extension"]: lr["cnt"] for lr in lang_rows}

            bash_rate = round((r["bash_ok"] / r["bash_total"]) * 100, 1) if r["bash_total"] else 0.0

            result.append(ProjectStats(
                project_name=r["project_name"],
                total_sessions=r["total_sessions"],
                total_edits=r["edits"] or 0,
                total_bash=r["bash"] or 0,
                total_reads=r["reads"] or 0,
                unique_files=r["unique_files"] or 0,
                total_minutes=minutes,
                last_seen=(r["last_seen"] or "")[:10],
                bash_success_rate=bash_rate,
                language_breakdown=lang,
            ))
        return result
    finally:
        conn.close()


def get_tool_duration_stats() -> Dict[str, float]:
    """Retorna duração média em ms por tool_name (da tabela de eventos com hooks)."""
    try:
        conn = get_db()
    except FileNotFoundError:
        return {}
    try:
        rows = conn.execute("""
            SELECT tool_name, AVG(duration_ms) as avg_ms
            FROM events
            WHERE duration_ms > 0
            GROUP BY tool_name
            ORDER BY avg_ms DESC
        """).fetchall()
        return {r["tool_name"]: r["avg_ms"] for r in rows}
    except Exception:
        return {}
    finally:
        conn.close()


def get_daily_history(days: int = 7) -> List[DailyStats]:
    try:
        conn = get_db()
    except FileNotFoundError:
        return []
    try:
        result = []
        for i in range(days - 1, -1, -1):
            d = (datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=i)).strftime("%Y-%m-%d")
            row = conn.execute("""
                SELECT
                    COUNT(DISTINCT e.session_id) as sessions,
                    COUNT(*) as total,
                    SUM(CASE WHEN e.tool_name IN ('Edit','Write','MultiEdit') THEN 1 ELSE 0 END) as edits,
                    SUM(CASE WHEN e.tool_name = 'Bash' THEN 1 ELSE 0 END) as bashes,
                    COUNT(DISTINCT e.file_path) as files
                FROM events e
                WHERE date(e.ts) = ?
            """, (d,)).fetchone()

            minutes = conn.execute("""
                SELECT SUM(
                    (julianday(COALESCE(ended_at, datetime('now'))) - julianday(started_at)) * 1440
                ) FROM sessions WHERE date(started_at) = ?
            """, (d,)).fetchone()[0] or 0

            result.append(DailyStats(
                date=d,
                total_tools=row["total"] or 0,
                total_sessions=row["sessions"] or 0,
                edit_count=row["edits"] or 0,
                bash_count=row["bashes"] or 0,
                unique_files=row["files"] or 0,
                active_minutes=float(minutes),
            ))
        return result
    finally:
        conn.close()
