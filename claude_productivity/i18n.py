"""Internacionalização (i18n) para claude-productivity.

Uso:
    from .i18n import _t, set_language

    set_language("en")        # ou via CLAUDE_METRICS_LANG
    label = _t("recent_activity")   # → "RECENT ACTIVITY"

Idiomas suportados: pt-BR (padrão), en, es
"""

from __future__ import annotations

import locale
import os

# ── Idioma ativo ───────────────────────────────────────────────────────────

LANG: str = "pt-BR"

# ── Dicionário de traduções ────────────────────────────────────────────────

_S: dict[str, dict[str, object]] = {

    # ── Tabs ─────────────────────────────────────────────────────────────
    "tab_dashboard":   {"pt-BR": "DASHBOARD",   "en": "DASHBOARD",  "es": "PANEL"},
    "tab_insights":    {"pt-BR": "INSIGHTS",     "en": "INSIGHTS",   "es": "ANÁLISIS"},
    "tab_history":     {"pt-BR": "HISTÓRICO",    "en": "HISTORY",    "es": "HISTORIAL"},
    "tab_projects":    {"pt-BR": "PROJETOS",     "en": "PROJECTS",   "es": "PROYECTOS"},
    "tab_sessions":    {"pt-BR": "SESSÕES",      "en": "SESSIONS",   "es": "SESIONES"},

    # ── Header / status ───────────────────────────────────────────────────
    "live":            {"pt-BR": "LIVE",         "en": "LIVE",       "es": "EN VIVO"},
    "last_session":    {"pt-BR": "LAST SESSION", "en": "LAST SESSION", "es": "ÚLTIMA SESIÓN"},
    "demo_mode":       {
        "pt-BR": "DEMO MODE — execute install.sh",
        "en":    "DEMO MODE — run install.sh",
        "es":    "MODO DEMO — ejecuta install.sh",
    },

    # ── ActivityWidget ────────────────────────────────────────────────────
    "recent_activity": {"pt-BR": "ATIVIDADE RECENTE",  "en": "RECENT ACTIVITY",   "es": "ACTIVIDAD RECIENTE"},
    "thinking":        {"pt-BR": "Pensando...",         "en": "Thinking...",        "es": "Pensando..."},
    "chars":           {"pt-BR": "chars",               "en": "chars",              "es": "chars"},

    # ── ChartWidget ───────────────────────────────────────────────────────
    "hourly_activity": {"pt-BR": "ATIVIDADE HORÁRIA",  "en": "HOURLY ACTIVITY",   "es": "ACTIVIDAD HORARIA"},
    "total":           {"pt-BR": "total",               "en": "total",              "es": "total"},
    "peak":            {"pt-BR": "pico",                "en": "peak",               "es": "pico"},

    # ── StatsWidget ───────────────────────────────────────────────────────
    "current_session": {"pt-BR": "SESSÃO ATUAL",       "en": "CURRENT SESSION",   "es": "SESIÓN ACTUAL"},
    "duration":        {"pt-BR": "Duração",             "en": "Duration",           "es": "Duración"},
    "tools":           {"pt-BR": "Tools",               "en": "Tools",              "es": "Herramientas"},
    "unique_files":    {"pt-BR": "Arquivos únicos",     "en": "Unique files",       "es": "Archivos únicos"},

    "sec_activity":    {"pt-BR": "── Atividade",        "en": "── Activity",        "es": "── Actividad"},
    "edits":           {"pt-BR": "Edits   ",            "en": "Edits   ",           "es": "Ediciones"},
    "bash_lbl":        {"pt-BR": "Bash    ",            "en": "Bash    ",           "es": "Bash    "},
    "reads":           {"pt-BR": "Leituras",            "en": "Reads   ",           "es": "Lecturas"},

    "sec_bash_health": {"pt-BR": "── Bash Health",      "en": "── Bash Health",     "es": "── Bash Health"},
    "ok":              {"pt-BR": "ok",                  "en": "ok",                 "es": "ok"},
    "fail":            {"pt-BR": "falha",               "en": "fail",               "es": "fallo"},
    "excellent":       {"pt-BR": "excelente",           "en": "excellent",          "es": "excelente"},
    "attention":       {"pt-BR": "atenção",             "en": "attention",          "es": "atención"},

    "sec_languages":   {"pt-BR": "── Linguagens",       "en": "── Languages",       "es": "── Lenguajes"},
    "files_abbr":      {"pt-BR": "arqs",                "en": "files",              "es": "arch"},

    "sec_edit_focus":  {"pt-BR": "── Foco de Edição",   "en": "── Edit Focus",      "es": "── Foco de Edición"},
    "consec_edits":    {"pt-BR": "edits consecutivos",  "en": "consecutive edits",  "es": "ediciones consecutivas"},
    "high_focus":      {"pt-BR": "alto foco",           "en": "high focus",         "es": "alto foco"},
    "fragmented":      {"pt-BR": "fragmentado",         "en": "fragmented",         "es": "fragmentado"},
    "moderate":        {"pt-BR": "moderado",            "en": "moderate",           "es": "moderado"},

    "sec_subagents":   {"pt-BR": "── Subagents",        "en": "── Subagents",       "es": "── Subagentes"},
    "invocations":     {"pt-BR": "invocações",          "en": "invocations",        "es": "invocaciones"},
    "no_subtype":      {
        "pt-BR": "chamadas sem subtipo registrado",
        "en":    "calls with no registered subtype",
        "es":    "llamadas sin subtipo registrado",
    },

    "sec_continuity":  {
        "pt-BR": "── Continuidade (retomados de sessões anteriores) ──",
        "en":    "── Continuity (resumed from previous sessions) ──",
        "es":    "── Continuidad (retomados de sesiones anteriores) ──",
    },

    "sec_avg_duration":{"pt-BR": "── Duração média por tool", "en": "── Avg duration per tool", "es": "── Duración media por herramienta"},
    "avg":             {"pt-BR": "avg",                 "en": "avg",                "es": "prom"},

    # ── InsightsWidget ────────────────────────────────────────────────────
    "insights_title":  {"pt-BR": "INSIGHTS & RECOMENDAÇÕES",  "en": "INSIGHTS & RECOMMENDATIONS", "es": "PERSPECTIVAS Y RECOMENDACIONES"},
    "analyzing":       {
        "pt-BR": "Analisando dados com Claude AI",
        "en":    "Analyzing data with Claude AI",
        "es":    "Analizando datos con Claude AI",
    },
    "analyzing_wait":  {
        "pt-BR": "Isso pode levar alguns segundos...",
        "en":    "This may take a few seconds...",
        "es":    "Esto puede tardar unos segundos...",
    },
    "cat_warning":     {"pt-BR": "ATENÇÃO",     "en": "WARNING",     "es": "ATENCIÓN"},
    "cat_tip":         {"pt-BR": "DICA",        "en": "TIP",         "es": "CONSEJO"},
    "cat_strength":    {"pt-BR": "PONTO FORTE", "en": "STRENGTH",    "es": "FORTALEZA"},
    "cat_info":        {"pt-BR": "INFO",        "en": "INFO",        "es": "INFO"},

    # ── HistoryWidget ─────────────────────────────────────────────────────
    "history_title":   {"pt-BR": "HISTÓRICO 7 DIAS",    "en": "7-DAY HISTORY",     "es": "HISTORIAL 7 DÍAS"},
    "goal":            {"pt-BR": "meta",                 "en": "goal",               "es": "meta"},
    "tools_per_day":   {"pt-BR": "tools/dia",            "en": "tools/day",          "es": "herr/día"},
    "no_activity":     {"pt-BR": "sem atividade",        "en": "no activity",        "es": "sin actividad"},
    "today":           {"pt-BR": "hoje",                 "en": "today",              "es": "hoy"},
    "daily_avg":       {"pt-BR": "Média diária",         "en": "Daily average",      "es": "Promedio diario"},
    "avg_time":        {"pt-BR": "Tempo médio",          "en": "Avg time",           "es": "Tiempo medio"},
    "goal_reached":    {"pt-BR": "Meta atingida",        "en": "Goal reached",       "es": "Meta alcanzada"},
    "days":            {"pt-BR": "dias",                 "en": "days",               "es": "días"},
    "active_days":     {"pt-BR": "dias ativos",          "en": "active days",        "es": "días activos"},
    "day_names":       {
        "pt-BR": ["Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo"],
        "en":    ["Monday",  "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"],
        "es":    ["Lunes",   "Martes",  "Miércoles", "Jueves",   "Viernes", "Sábado",  "Domingo"],
    },

    # ── ProjectsWidget ────────────────────────────────────────────────────
    "projects_title":      {"pt-BR": "PROJETOS",         "en": "PROJECTS",           "es": "PROYECTOS"},
    "no_projects":         {
        "pt-BR": "Nenhum projeto detectado ainda.",
        "en":    "No projects detected yet.",
        "es":    "Ningún proyecto detectado aún.",
    },
    "no_projects_hint":    {
        "pt-BR": "Os projetos são detectados a partir dos caminhos de arquivo.",
        "en":    "Projects are detected from file paths.",
        "es":    "Los proyectos se detectan a partir de las rutas de archivos.",
    },
    "session_singular":    {"pt-BR": "sessão",           "en": "session",            "es": "sesión"},
    "session_plural":      {"pt-BR": "sessões",          "en": "sessions",           "es": "sesiones"},

    # ── MultiSessionWidget ────────────────────────────────────────────────
    "sessions_title":  {"pt-BR": "SESSÕES",              "en": "SESSIONS",           "es": "SESIONES"},
    "active":          {"pt-BR": "ativas",               "en": "active",             "es": "activas"},
    "recent":          {"pt-BR": "recentes",             "en": "recent",             "es": "recientes"},
    "sec_recent":      {"pt-BR": "── Recentes",          "en": "── Recent",          "es": "── Recientes"},
    "no_sessions":     {
        "pt-BR": "Nenhuma sessão ativa no momento.",
        "en":    "No active sessions at the moment.",
        "es":    "No hay sesiones activas en este momento.",
    },
    "no_sessions_hint":{
        "pt-BR": "Sessões aparecem aqui ao abrir o Claude Code em qualquer projeto do seu sistema.",
        "en":    "Sessions appear here when you open Claude Code in any project on your system.",
        "es":    "Las sesiones aparecen aquí al abrir Claude Code en cualquier proyecto.",
    },
    "ago":             {"pt-BR": "atrás",                "en": "ago",                "es": "hace"},
    "inactive":        {"pt-BR": "inativo",              "en": "inactive",           "es": "inactivo"},
    "subagents_lbl":   {"pt-BR": "◈ subagents:",         "en": "◈ subagents:",       "es": "◈ subagentes:"},
    "tokens":          {"pt-BR": "Tokens",               "en": "Tokens",             "es": "Tokens"},

    # ── Notifications (action_export) ─────────────────────────────────────
    "openpyxl_missing":    {
        "pt-BR": "Rode: pip install openpyxl",
        "en":    "Run: pip install openpyxl",
        "es":    "Ejecuta: pip install openpyxl",
    },
    "openpyxl_title":      {
        "pt-BR": "openpyxl não instalado",
        "en":    "openpyxl not installed",
        "es":    "openpyxl no instalado",
    },
    "export_saved":        {"pt-BR": "Arquivo salvo em:",    "en": "File saved to:",     "es": "Archivo guardado en:"},
    "export_ok_title":     {"pt-BR": "✓ Planilha exportada", "en": "✓ Spreadsheet exported", "es": "✓ Hoja exportada"},
    "export_err_title":    {"pt-BR": "Erro ao exportar",     "en": "Export error",        "es": "Error al exportar"},

    # ── Bindings (footer) ─────────────────────────────────────────────────
    "bind_dashboard":  {"pt-BR": "Dashboard",   "en": "Dashboard",  "es": "Panel"},
    "bind_insights":   {"pt-BR": "Insights",    "en": "Insights",   "es": "Análisis"},
    "bind_history":    {"pt-BR": "Histórico",   "en": "History",    "es": "Historial"},
    "bind_projects":   {"pt-BR": "Projetos",    "en": "Projects",   "es": "Proyectos"},
    "bind_sessions":   {"pt-BR": "Sessões",     "en": "Sessions",   "es": "Sesiones"},
    "bind_theme":      {"pt-BR": "Tema",        "en": "Theme",      "es": "Tema"},
    "bind_refresh":    {"pt-BR": "Refresh",     "en": "Refresh",    "es": "Refrescar"},
    "bind_export":     {"pt-BR": "Exportar .xlsx", "en": "Export .xlsx", "es": "Exportar .xlsx"},
    "bind_quit":       {"pt-BR": "Sair",        "en": "Quit",       "es": "Salir"},

    # ── Excel (exporter.py) ───────────────────────────────────────────────
    "xl_report_title":     {
        "pt-BR": "Claude Code — Relatório de Produtividade",
        "en":    "Claude Code — Productivity Report",
        "es":    "Claude Code — Reporte de Productividad",
    },
    "xl_generated":        {"pt-BR": "Gerado em",       "en": "Generated at",       "es": "Generado el"},
    "xl_sheet_summary":    {"pt-BR": "Resumo",          "en": "Summary",            "es": "Resumen"},
    "xl_sheet_history":    {"pt-BR": "Histórico 7 Dias","en": "7-Day History",      "es": "Historial 7 Días"},
    "xl_sheet_projects":   {"pt-BR": "Projetos",        "en": "Projects",           "es": "Proyectos"},
    "xl_sheet_languages":  {"pt-BR": "Linguagens",      "en": "Languages",          "es": "Idiomas"},

    "xl_sec_current":      {"pt-BR": "SESSÃO ATUAL",    "en": "CURRENT SESSION",    "es": "SESIÓN ACTUAL"},
    "xl_sec_languages":    {"pt-BR": "LINGUAGENS DA SESSÃO", "en": "SESSION LANGUAGES", "es": "LENGUAJES DE LA SESIÓN"},

    "xl_project":          {"pt-BR": "Projeto",         "en": "Project",            "es": "Proyecto"},
    "xl_status":           {"pt-BR": "Status",          "en": "Status",             "es": "Estado"},
    "xl_active":           {"pt-BR": "Ativa",           "en": "Active",             "es": "Activa"},
    "xl_ended":            {"pt-BR": "Encerrada",       "en": "Ended",              "es": "Terminada"},
    "xl_duration":         {"pt-BR": "Duração",         "en": "Duration",           "es": "Duración"},
    "xl_total_actions":    {"pt-BR": "Total de ações",  "en": "Total actions",      "es": "Total de acciones"},
    "xl_unique_files":     {"pt-BR": "Arquivos únicos", "en": "Unique files",       "es": "Archivos únicos"},
    "xl_edits_writes":     {"pt-BR": "Edits / Writes",  "en": "Edits / Writes",     "es": "Edits / Writes"},
    "xl_bash_cmds":        {"pt-BR": "Comandos Bash",   "en": "Bash Commands",      "es": "Comandos Bash"},
    "xl_reads":            {"pt-BR": "Leituras",        "en": "Reads",              "es": "Lecturas"},
    "xl_subagents":        {"pt-BR": "Subagents usados","en": "Subagents used",     "es": "Subagentes usados"},
    "xl_bash_rate":        {"pt-BR": "Bash — Taxa de sucesso", "en": "Bash — Success rate", "es": "Bash — Tasa de éxito"},
    "xl_edit_burst":       {
        "pt-BR": "Burst médio de edits",
        "en":    "Avg edit burst",
        "es":    "Ráfaga media de edits",
    },
    "xl_cross_files":      {
        "pt-BR": "Arquivos retomados (cross-session)",
        "en":    "Resumed files (cross-session)",
        "es":    "Archivos retomados (entre sesiones)",
    },
    "xl_consec_edits":     {
        "pt-BR": "edits consecutivos",
        "en":    "consecutive edits",
        "es":    "ediciones consecutivas",
    },
    "xl_no_lang":          {
        "pt-BR": "Nenhum dado de linguagem registrado",
        "en":    "No language data recorded",
        "es":    "No hay datos de lenguaje registrados",
    },

    "xl_hist_title":       {
        "pt-BR": "Histórico de Atividade — Últimos 7 Dias",
        "en":    "Activity History — Last 7 Days",
        "es":    "Historial de Actividad — Últimos 7 Días",
    },
    "xl_date":             {"pt-BR": "Data",            "en": "Date",               "es": "Fecha"},
    "xl_weekday":          {"pt-BR": "Dia da Semana",   "en": "Weekday",            "es": "Día de la Semana"},
    "xl_total_actions2":   {"pt-BR": "Total de Ações",  "en": "Total Actions",      "es": "Total de Acciones"},
    "xl_unique_files2":    {"pt-BR": "Arquivos Únicos", "en": "Unique Files",       "es": "Archivos Únicos"},
    "xl_active_time":      {"pt-BR": "Tempo Ativo",     "en": "Active Time",        "es": "Tiempo Activo"},
    "xl_avgs_section":     {"pt-BR": "MÉDIAS (dias com atividade)", "en": "AVERAGES (active days)", "es": "PROMEDIOS (días con actividad)"},
    "xl_avg_actions":      {"pt-BR": "Média de ações/dia",  "en": "Avg actions/day",    "es": "Prom. acciones/día"},
    "xl_avg_edits":        {"pt-BR": "Média de edits/dia",  "en": "Avg edits/day",      "es": "Prom. edits/día"},
    "xl_avg_bash":         {"pt-BR": "Média de bash/dia",   "en": "Avg bash/day",       "es": "Prom. bash/día"},
    "xl_avg_time":         {"pt-BR": "Tempo médio/dia",     "en": "Avg time/day",       "es": "Tiempo prom./día"},
    "xl_active_days":      {"pt-BR": "Dias ativos",         "en": "Active days",        "es": "Días activos"},

    "xl_proj_title":       {"pt-BR": "Métricas por Projeto","en": "Metrics by Project", "es": "Métricas por Proyecto"},
    "xl_last_seen":        {"pt-BR": "Último uso",          "en": "Last seen",          "es": "Último uso"},
    "xl_sessions":         {"pt-BR": "Sessões",             "en": "Sessions",           "es": "Sesiones"},
    "xl_total_time":       {"pt-BR": "Tempo Total",         "en": "Total Time",         "es": "Tiempo Total"},
    "xl_bash_success":     {"pt-BR": "Bash Sucesso",        "en": "Bash Success",       "es": "Éxito Bash"},
    "xl_main_langs":       {"pt-BR": "Linguagens Principais","en": "Main Languages",    "es": "Lenguajes Principales"},

    "xl_lang_title":       {
        "pt-BR": "Breakdown de Linguagens por Projeto",
        "en":    "Language Breakdown by Project",
        "es":    "Desglose de Lenguajes por Proyecto",
    },
    "xl_extension":        {"pt-BR": "Extensão",            "en": "Extension",          "es": "Extensión"},
    "xl_files_edited":     {"pt-BR": "Arquivos editados",   "en": "Files edited",       "es": "Archivos editados"},
    "xl_pct_project":      {"pt-BR": "% no projeto",        "en": "% in project",       "es": "% en proyecto"},
    "xl_usage_level":      {"pt-BR": "Nível de uso",        "en": "Usage level",        "es": "Nivel de uso"},
    "xl_files_edited2":    {"pt-BR": "Arquivos editados",   "en": "Files edited",       "es": "Archivos editados"},
    "xl_pct_total":        {"pt-BR": "% do total",          "en": "% of total",         "es": "% del total"},
}


# ── API pública ────────────────────────────────────────────────────────────

def _t(key: str) -> str:
    """Retorna string traduzida. Fallback: en → key literal."""
    entry = _S.get(key, {})
    value = entry.get(LANG) or entry.get("en") or key
    # day_names e outros valores lista: retornar como string (não deve ser chamado via _t)
    return str(value) if not isinstance(value, list) else key


def _tl(key: str) -> list[str]:
    """Retorna lista traduzida (ex: day_names)."""
    entry = _S.get(key, {})
    value = entry.get(LANG) or entry.get("en") or []
    return value if isinstance(value, list) else []


def set_language(lang: str) -> None:
    """Altera o idioma em runtime. Ex: 'en', 'pt-BR', 'es'."""
    global LANG
    supported = {"pt-BR", "en", "es"}
    LANG = lang if lang in supported else "en"


def detect_language() -> str:
    """Detecta o idioma pelo ambiente. CLAUDE_METRICS_LANG tem prioridade."""
    if env_lang := os.environ.get("CLAUDE_METRICS_LANG", "").strip():
        return env_lang
    try:
        sys_locale = locale.getlocale()[0] or ""
        if sys_locale.startswith("pt"):
            return "pt-BR"
        if sys_locale.startswith("es"):
            return "es"
    except Exception:
        pass
    return "en"
