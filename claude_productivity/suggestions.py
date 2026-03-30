"""Skill & MCP suggestion engine for claude-productivity.

Analyses usage patterns from the last 30 days (bash commands, file
extensions, file paths, tool usage) and returns a ranked list of
Claude Code skills and MCPs that may improve the user's workflow.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import List

DB_PATH = Path.home() / ".claude" / "productivity.db"


@dataclass
class Suggestion:
    name: str         # Display name, e.g. "/commit" or "Context7"
    kind: str         # "skill" | "mcp"
    icon: str         # ⚙ for skill, ◆ for mcp
    reason_key: str   # i18n key (template with {count})
    activation_key: str  # i18n key (template with {name})
    score: float      # 0.0–1.0, used for ranking
    count: int        # Raw event count, shown in reason text


def detect_suggestions(max_results: int = 5) -> List[Suggestion]:
    """Run detection rules against the DB and return the top suggestions."""
    if not DB_PATH.exists():
        return []
    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            return _run_detection(conn, max_results)
    except Exception:
        return []


# ── Internal helpers ───────────────────────────────────────────────────────

def _score(count: int, threshold: int) -> float:
    return min(1.0, count / threshold) if threshold > 0 else 0.0


def _run_detection(conn: sqlite3.Connection, max_results: int) -> List[Suggestion]:
    results: List[Suggestion] = []

    # ── Query 1: Bash command patterns ────────────────────────────────────
    bash_row = conn.execute("""
        SELECT
          SUM(CASE WHEN command LIKE '% git %' OR command LIKE 'git %'
              THEN 1 ELSE 0 END)                                              AS git_cnt,
          SUM(CASE WHEN command LIKE '%docker%' OR command LIKE '%kubectl%'
              THEN 1 ELSE 0 END)                                              AS container_cnt,
          SUM(CASE WHEN command LIKE '%npm %' OR command LIKE '%yarn %'
               OR  command LIKE '%pnpm %'
              THEN 1 ELSE 0 END)                                              AS node_cnt,
          SUM(CASE WHEN command LIKE '%pytest%' OR command LIKE '% jest%'
               OR  command LIKE '%vitest%'
              THEN 1 ELSE 0 END)                                              AS test_cnt,
          SUM(CASE WHEN command LIKE '%curl %' OR command LIKE '% http %'
              THEN 1 ELSE 0 END)                                              AS api_cnt
        FROM events
        WHERE tool_name = 'Bash'
          AND command IS NOT NULL
          AND ts >= datetime('now', '-30 days')
    """).fetchone()

    if bash_row:
        git_cnt       = bash_row["git_cnt"]       or 0
        container_cnt = bash_row["container_cnt"] or 0
        node_cnt      = bash_row["node_cnt"]      or 0
        test_cnt      = bash_row["test_cnt"]      or 0
        api_cnt       = bash_row["api_cnt"]       or 0

        if git_cnt >= 5:
            results.append(Suggestion(
                "/commit", "skill", "⚙",
                "sug_git_reason", "sug_activate_skill",
                _score(git_cnt, 20), git_cnt,
            ))
        if git_cnt >= 8:
            results.append(Suggestion(
                "/commit-push-pr", "skill", "⚙",
                "sug_git_pr_reason", "sug_activate_skill",
                _score(git_cnt, 15), git_cnt,
            ))
        if container_cnt >= 3:
            results.append(Suggestion(
                "gke-kubernetes-expert", "skill", "⚙",
                "sug_container_reason", "sug_activate_skill",
                _score(container_cnt, 10), container_cnt,
            ))
        if node_cnt >= 5:
            results.append(Suggestion(
                "frontend-design", "skill", "⚙",
                "sug_node_reason", "sug_activate_skill",
                _score(node_cnt, 15), node_cnt,
            ))
        if test_cnt >= 3:
            results.append(Suggestion(
                "code-reviewer", "skill", "⚙",
                "sug_test_reason", "sug_activate_skill",
                _score(test_cnt, 10), test_cnt,
            ))
        if api_cnt >= 3:
            results.append(Suggestion(
                "api-architect", "skill", "⚙",
                "sug_api_reason", "sug_activate_skill",
                _score(api_cnt, 10), api_cnt,
            ))

    # ── Query 2: File extensions ───────────────────────────────────────────
    ext_rows = conn.execute("""
        SELECT file_extension, COUNT(*) AS cnt
        FROM events
        WHERE file_extension IS NOT NULL AND file_extension != ''
          AND ts >= datetime('now', '-30 days')
        GROUP BY file_extension
    """).fetchall()

    ext_counts: dict[str, int] = {r["file_extension"]: r["cnt"] for r in ext_rows}
    vue_cnt  = ext_counts.get("vue", 0)
    tsx_cnt  = ext_counts.get("tsx", 0) + ext_counts.get("jsx", 0)
    cs_cnt   = ext_counts.get("cs", 0)

    if vue_cnt >= 3:
        results.append(Suggestion(
            "vue-component-architect", "skill", "⚙",
            "sug_vue_reason", "sug_activate_skill",
            _score(vue_cnt, 5), vue_cnt,
        ))
    if tsx_cnt >= 3:
        results.append(Suggestion(
            "react-component-architect", "skill", "⚙",
            "sug_react_reason", "sug_activate_skill",
            _score(tsx_cnt, 5), tsx_cnt,
        ))
    if cs_cnt >= 3:
        results.append(Suggestion(
            "dotnet-aspnet-core-expert", "skill", "⚙",
            "sug_dotnet_reason", "sug_activate_skill",
            _score(cs_cnt, 5), cs_cnt,
        ))

    # ── Query 3: File path patterns + tool usage ───────────────────────────
    path_row = conn.execute("""
        SELECT
          SUM(CASE WHEN file_path LIKE '%Dockerfile%'
              THEN 1 ELSE 0 END)                                              AS dockerfile_cnt,
          SUM(CASE WHEN file_path LIKE '%.github/workflows/%'
              THEN 1 ELSE 0 END)                                              AS ci_cnt,
          SUM(CASE WHEN file_path LIKE '%next.config%'
              THEN 1 ELSE 0 END)                                              AS nextjs_cnt,
          SUM(CASE WHEN file_path LIKE '%nuxt.config%'
              THEN 1 ELSE 0 END)                                              AS nuxt_cnt,
          SUM(CASE WHEN file_path LIKE '%manage.py%'
               OR  command  LIKE '%manage.py%'
              THEN 1 ELSE 0 END)                                              AS django_cnt,
          SUM(CASE WHEN tool_name IN ('WebSearch', 'WebFetch')
              THEN 1 ELSE 0 END)                                              AS web_cnt,
          SUM(CASE WHEN tool_name = 'Agent'
              THEN 1 ELSE 0 END)                                              AS agent_cnt
        FROM events
        WHERE ts >= datetime('now', '-30 days')
    """).fetchone()

    if path_row:
        dockerfile_cnt = path_row["dockerfile_cnt"] or 0
        ci_cnt         = path_row["ci_cnt"]         or 0
        nextjs_cnt     = path_row["nextjs_cnt"]     or 0
        nuxt_cnt       = path_row["nuxt_cnt"]       or 0
        django_cnt     = path_row["django_cnt"]     or 0
        web_cnt        = path_row["web_cnt"]        or 0
        agent_cnt      = path_row["agent_cnt"]      or 0

        if nextjs_cnt >= 1:
            results.append(Suggestion(
                "react-nextjs-expert", "skill", "⚙",
                "sug_nextjs_reason", "sug_activate_skill",
                _score(nextjs_cnt, 3), nextjs_cnt,
            ))
        if nuxt_cnt >= 1:
            results.append(Suggestion(
                "vue-nuxt-expert", "skill", "⚙",
                "sug_nuxt_reason", "sug_activate_skill",
                _score(nuxt_cnt, 3), nuxt_cnt,
            ))
        if django_cnt >= 2:
            results.append(Suggestion(
                "django-backend-expert", "skill", "⚙",
                "sug_django_reason", "sug_activate_skill",
                _score(django_cnt, 5), django_cnt,
            ))
        if web_cnt >= 5:
            results.append(Suggestion(
                "Context7", "mcp", "◆",
                "sug_web_reason", "sug_activate_mcp",
                _score(web_cnt, 10), web_cnt,
            ))
        if agent_cnt >= 10:
            results.append(Suggestion(
                "agent-deck", "skill", "⚙",
                "sug_agent_reason", "sug_activate_skill",
                _score(agent_cnt, 15), agent_cnt,
            ))
        container_cnt_path = max(dockerfile_cnt, ci_cnt)
        if container_cnt_path >= 2:
            # Only add if not already suggested from bash commands
            existing = {s.name for s in results}
            if "gke-kubernetes-expert" not in existing:
                results.append(Suggestion(
                    "gke-kubernetes-expert", "skill", "⚙",
                    "sug_container_reason", "sug_activate_skill",
                    _score(container_cnt_path, 5), container_cnt_path,
                ))

    # ── Deduplicate by name, keep highest score, return top N ─────────────
    seen: dict[str, Suggestion] = {}
    for s in results:
        if s.name not in seen or s.score > seen[s.name].score:
            seen[s.name] = s

    return sorted(seen.values(), key=lambda x: x.score, reverse=True)[:max_results]
