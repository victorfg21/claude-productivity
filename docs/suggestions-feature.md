# Feature: Skill & MCP Suggestions Based on Usage Data

## Problem

The productivity dashboard already collects detailed usage data (tools, bash commands, file extensions, file paths) but does not use that data to recommend tools that could improve the user's workflow.

## Solution

Analyse real patterns in the local database and suggest relevant Claude Code skills and MCPs directly in the Insights tab.

---

## Architecture

### New module: `claude_productivity/suggestions.py`

- `Suggestion` dataclass: `name`, `kind` (skill/mcp), `icon`, `reason_key`, `activation_key`, `score`, `count`
- `detect_suggestions(max_results=5) -> List[Suggestion]`
- 3 aggregated SQL queries (not one per rule) for performance:
  - **Query 1** – Bash command patterns (`CASE WHEN command LIKE ...`)
  - **Query 2** – File extensions (`GROUP BY file_extension`)
  - **Query 3** – File path patterns + tool usage counts
- 30-day rolling window (`ts >= datetime('now', '-30 days')`)
- Score: `min(1.0, count / threshold)` for ranking
- Deduplication: if two rules suggest the same skill, keep the higher score

### Detection rules

| Pattern | Min count | Threshold | Suggestion |
|---------|-----------|-----------|------------|
| `git` in Bash command | 5 | 20 | `/commit` skill |
| `git` in Bash command | 8 | 15 | `/commit-push-pr` skill |
| `docker` / `kubectl` in Bash | 3 | 10 | `gke-kubernetes-expert` |
| `npm` / `yarn` / `pnpm` in Bash | 5 | 15 | `frontend-design` skill |
| `pytest` / `jest` / `vitest` in Bash | 3 | 10 | `code-reviewer` skill |
| `curl` / `http` in Bash | 3 | 10 | `api-architect` skill |
| `.vue` file extension | 3 | 5 | `vue-component-architect` |
| `.tsx` / `.jsx` file extension | 3 | 5 | `react-component-architect` |
| `.cs` file extension | 3 | 5 | `dotnet-aspnet-core-expert` |
| `next.config` in file path | 1 | 3 | `react-nextjs-expert` |
| `nuxt.config` in file path | 1 | 3 | `vue-nuxt-expert` |
| `manage.py` in file path/command | 2 | 5 | `django-backend-expert` |
| WebSearch / WebFetch tool usage | 5 | 10 | `Context7` MCP |
| Agent tool usage | 10 | 15 | `agent-deck` skill |
| `Dockerfile` / `.github/workflows/` in path | 2 | 5 | `gke-kubernetes-expert` |

### New widget: `SuggestionsWidget` (`tui/app.py`)

Rendered below `InsightsWidget` in the Insights tab scroll container.

Visual layout:
```
  ──────────────────────────────────────────────────
  SUGGESTED SKILLS & MCPs

  ⚙ [SKILL]  /commit
    47 git commands in the last 30 days — automate your commits
    ▸ Use /commit in Claude Code

  ◆ [MCP]  Context7
    23 web searches/fetches — access docs without leaving Claude
    ▸ Add Context7 MCP to ~/.claude/settings.json
```

### i18n keys added (`i18n.py`)

| Key | Purpose |
|-----|---------|
| `suggestions_title` | Section header |
| `cat_suggestion` | Category label |
| `sug_no_suggestions` | Empty state message |
| `sug_activate_skill` | Generic activation template for skills (`{name}`) |
| `sug_activate_mcp` | Generic activation template for MCPs (`{name}`) |
| `sug_git_reason` | Reason for /commit suggestion (`{count}`) |
| `sug_git_pr_reason` | Reason for /commit-push-pr suggestion |
| `sug_container_reason` | Reason for K8s suggestion (`{count}`) |
| `sug_node_reason` | Reason for frontend-design suggestion (`{count}`) |
| `sug_test_reason` | Reason for code-reviewer suggestion (`{count}`) |
| `sug_api_reason` | Reason for api-architect suggestion (`{count}`) |
| `sug_vue_reason` | Reason for vue-component-architect suggestion (`{count}`) |
| `sug_react_reason` | Reason for react-component-architect suggestion (`{count}`) |
| `sug_dotnet_reason` | Reason for dotnet-aspnet-core-expert suggestion (`{count}`) |
| `sug_nextjs_reason` | Reason for react-nextjs-expert suggestion |
| `sug_nuxt_reason` | Reason for vue-nuxt-expert suggestion |
| `sug_django_reason` | Reason for django-backend-expert suggestion (`{count}`) |
| `sug_web_reason` | Reason for Context7 MCP suggestion (`{count}`) |
| `sug_agent_reason` | Reason for agent-deck suggestion (`{count}`) |

### Data flow

1. `ProductivityApp._load_db_data()` runs every 3 seconds
2. Suggestions are cached with a 30-second minimum interval (`_suggestions_last_refresh`)
3. `detect_suggestions()` runs 3 SQL queries and returns ranked `Suggestion` objects
4. `SuggestionsWidget.update_suggestions()` renders them with i18n text and theme colors

---

## Files Modified

| File | Type | Description |
|------|------|-------------|
| `claude_productivity/suggestions.py` | **NEW** | Detection engine and `Suggestion` dataclass |
| `claude_productivity/i18n.py` | MODIFIED | 20 new translation keys (pt-BR, en, es) |
| `claude_productivity/tui/app.py` | MODIFIED | `SuggestionsWidget` class, layout wiring, cache logic |

---

## Testing

1. Run `claude-metrics` and navigate to the Insights tab — suggestions should appear based on real DB data
2. Press `L` to toggle language — suggestion text should translate immediately
3. Test with an empty DB — the "no suggestions yet" message should appear
4. Verify no flicker on the 3-second refresh cycle (cache prevents re-query before 30s)
