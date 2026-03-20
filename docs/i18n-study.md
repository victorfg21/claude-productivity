# Estudo: Internacionalização (i18n)

## Situação atual

Todas as strings visíveis estão hardcoded em português nos widgets de `tui/app.py`
(títulos de seção, labels, status, tooltips) e em `exporter.py` (cabeçalhos das abas Excel).

---

## Abordagem recomendada: dicionário estático em `i18n.py`

### Por que não usar `gettext` / `Babel`?

| Critério | gettext/Babel | Dicionário estático |
|---|---|---|
| Dependências extras | Sim | Não |
| Complexidade de setup | Alta (`.po`/`.mo`, compilação) | Baixa |
| Adequado para TUI pequena | Exagero | Ideal |
| Pluralização | Automática | Manual se necessário |

Para um projeto com ~80 strings e 2-3 idiomas, o dicionário estático é a escolha certa.

---

## Estrutura proposta

```
claude_productivity/
  i18n.py          ← dicionário de traduções + função _t()
  tui/app.py       ← substituir strings por _t("chave")
  exporter.py      ← substituir strings por _t("chave")
```

### `i18n.py`

```python
from __future__ import annotations

LANG = "pt-BR"   # alterável via constante ou variável de ambiente

_STRINGS: dict[str, dict[str, str]] = {
    # ── Dashboard ──────────────────────────────────────────────────────
    "recent_activity":       {"pt-BR": "ATIVIDADE RECENTE",     "en": "RECENT ACTIVITY",       "es": "ACTIVIDAD RECIENTE"},
    "hourly_activity":       {"pt-BR": "ATIVIDADE HORÁRIA",     "en": "HOURLY ACTIVITY",        "es": "ACTIVIDAD HORARIA"},
    "total":                 {"pt-BR": "total",                  "en": "total",                  "es": "total"},
    "peak":                  {"pt-BR": "pico",                   "en": "peak",                   "es": "pico"},
    "current_session":       {"pt-BR": "SESSÃO ATUAL",           "en": "CURRENT SESSION",        "es": "SESIÓN ACTUAL"},
    "duration":              {"pt-BR": "Duração",                "en": "Duration",               "es": "Duración"},
    "tools":                 {"pt-BR": "Tools",                  "en": "Tools",                  "es": "Herramientas"},
    "unique_files":          {"pt-BR": "Arquivos únicos",        "en": "Unique files",           "es": "Archivos únicos"},
    "activity":              {"pt-BR": "Atividade",              "en": "Activity",               "es": "Actividad"},
    "edits":                 {"pt-BR": "Edits",                  "en": "Edits",                  "es": "Ediciones"},
    "bash":                  {"pt-BR": "Bash",                   "en": "Bash",                   "es": "Bash"},
    "reads":                 {"pt-BR": "Leituras",               "en": "Reads",                  "es": "Lecturas"},
    "languages":             {"pt-BR": "Linguagens",             "en": "Languages",              "es": "Lenguajes"},
    "edit_focus":            {"pt-BR": "Foco de Edição",         "en": "Edit Focus",             "es": "Foco de Edición"},
    "continuity":            {"pt-BR": "Continuidade",           "en": "Continuity",             "es": "Continuidad"},
    "avg_duration":          {"pt-BR": "Duração média por tool", "en": "Avg duration per tool",  "es": "Duración media por herramienta"},
    "thinking":              {"pt-BR": "Pensando...",            "en": "Thinking...",            "es": "Pensando..."},
    # ── Status ─────────────────────────────────────────────────────────
    "live":                  {"pt-BR": "LIVE",                   "en": "LIVE",                   "es": "EN VIVO"},
    "last_session":          {"pt-BR": "LAST SESSION",           "en": "LAST SESSION",           "es": "ÚLTIMA SESIÓN"},
    "demo_mode":             {"pt-BR": "DEMO MODE — run install.sh", "en": "DEMO MODE — run install.sh", "es": "MODO DEMO — ejecuta install.sh"},
    # ── Tabs ───────────────────────────────────────────────────────────
    "tab_dashboard":         {"pt-BR": "DASHBOARD",              "en": "DASHBOARD",              "es": "PANEL"},
    "tab_insights":          {"pt-BR": "INSIGHTS",               "en": "INSIGHTS",               "es": "ANÁLISIS"},
    "tab_history":           {"pt-BR": "HISTÓRICO",              "en": "HISTORY",                "es": "HISTORIAL"},
    "tab_projects":          {"pt-BR": "PROJETOS",               "en": "PROJECTS",               "es": "PROYECTOS"},
    "tab_sessions":          {"pt-BR": "SESSÕES",                "en": "SESSIONS",               "es": "SESIONES"},
    # ── History ────────────────────────────────────────────────────────
    "day_names":             {
        "pt-BR": ["Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo"],
        "en":    ["Monday",  "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"],
        "es":    ["Lunes",   "Martes",  "Miércoles", "Jueves",   "Viernes", "Sábado",  "Domingo"],
    },
    # ── Excel ──────────────────────────────────────────────────────────
    "excel_title":           {"pt-BR": "Claude Code — Relatório de Produtividade", "en": "Claude Code — Productivity Report", "es": "Claude Code — Reporte de Productividad"},
    "sheet_summary":         {"pt-BR": "Resumo",                 "en": "Summary",                "es": "Resumen"},
    "sheet_history":         {"pt-BR": "Histórico 7 Dias",       "en": "7-Day History",          "es": "Historial 7 Días"},
    "sheet_projects":        {"pt-BR": "Projetos",               "en": "Projects",               "es": "Proyectos"},
    "sheet_languages":       {"pt-BR": "Linguagens",             "en": "Languages",              "es": "Idiomas"},
}


def _t(key: str) -> str:
    """Retorna string traduzida para o idioma atual. Fallback: en → key."""
    entry = _STRINGS.get(key, {})
    return entry.get(LANG) or entry.get("en") or key


def set_language(lang: str) -> None:
    """Altera o idioma em runtime (ex: 'en', 'pt-BR', 'es')."""
    global LANG
    LANG = lang
```

---

## Como detectar o idioma automaticamente

```python
import locale, os

def detect_language() -> str:
    # 1. Variável de ambiente explícita (maior prioridade)
    if lang := os.environ.get("CLAUDE_METRICS_LANG"):
        return lang
    # 2. Locale do sistema
    system_locale = locale.getlocale()[0] or ""
    if system_locale.startswith("pt"):
        return "pt-BR"
    if system_locale.startswith("es"):
        return "es"
    return "en"
```

Chamado uma vez no `run()` de `app.py`:
```python
from ..i18n import set_language, detect_language
set_language(detect_language())
```

---

## Escopo de mudanças

| Arquivo | Strings afetadas |
|---|---|
| `tui/app.py` | ~40 strings (títulos, labels, status, tabs, footer) |
| `exporter.py` | ~25 strings (cabeçalhos de colunas, títulos de abas, seções) |
| `analyzer.py` | ~10 strings (categorias, recomendações) |

**Total: ~75 strings** — trabalho de ~2-3h.

---

## Adição de novo idioma

Basta adicionar uma chave no dicionário `_STRINGS`:
```python
"recent_activity": {
    "pt-BR": "ATIVIDADE RECENTE",
    "en":    "RECENT ACTIVITY",
    "es":    "ACTIVIDAD RECIENTE",
    "fr":    "ACTIVITÉ RÉCENTE",   # ← novo
},
```

Sem compilação, sem arquivos `.po`, sem ferramentas externas.

---

## Limitações desta abordagem

- **Pluralização**: `"1 arquivo / 3 arquivos"` requer lógica extra (pequena função `_tn(key, n)`)
- **RTL** (árabe, hebraico): Textual não suporta bidi nativamente — inviável por ora
- **Contribuição de tradutores externos**: dicionário Python é menos amigável que `.po`/`.json`
  - Se o projeto crescer, migrar para JSON externo: `i18n/pt-BR.json`, `i18n/en.json`

---

## Próximo passo recomendado

1. Criar `claude_productivity/i18n.py` com o dicionário acima
2. Substituir strings em `app.py` por `_t("chave")` — widget por widget
3. Substituir strings em `exporter.py`
4. Testar com `CLAUDE_METRICS_LANG=en claude-metrics`
