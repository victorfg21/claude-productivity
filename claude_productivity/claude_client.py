"""
Chama `claude --print` via subprocess para gerar insights reais com IA.
Padrão idêntico ao usado em checkout-report.
"""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
from pathlib import Path

from .analyzer import analyze
from .db import SessionStats, DailyStats


def _clean_env() -> dict:
    """Remove vars que bloqueiam sessões claude aninhadas."""
    env = os.environ.copy()
    env.pop("CLAUDECODE", None)
    env.pop("CLAUDE_CODE_ENTRYPOINT", None)
    return env


def _run_claude(prompt: str, timeout: int = 60) -> str:
    """Invoca `claude --print` com o prompt via stdin. Retorna o texto de saída."""
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".txt", delete=False, encoding="utf-8"
    ) as tmp:
        tmp.write(prompt)
        tmp_path = tmp.name

    try:
        with open(tmp_path, "r", encoding="utf-8") as stdin_fh:
            result = subprocess.run(
                ["claude", "--print"],
                stdin=stdin_fh,
                capture_output=True,
                text=True,
                timeout=timeout,
                env=_clean_env(),
            )
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip() or f"exit code {result.returncode}")
        return result.stdout.strip()
    finally:
        os.unlink(tmp_path)


def _build_prompt(session: SessionStats, history: list[DailyStats]) -> str:
    repeated = "\n".join(
        f"  - {fp}: {cnt}x" for fp, cnt in session.repeated_files
    ) or "  (nenhum)"

    hist_lines = "\n".join(
        f"  {d.date}: {d.total_tools} tools, {d.edit_count} edits, "
        f"{d.bash_count} bash, {int(d.active_minutes)}min"
        for d in history
    )

    peak_hour = session.hourly_activity.index(max(session.hourly_activity)) \
        if max(session.hourly_activity) > 0 else -1

    # Linguagens formatadas
    lang_lines = ", ".join(
        f".{ext}({cnt})" for ext, cnt in session.language_breakdown.items()
    ) or "(sem dados)"

    # Cross-session files
    cross_files = "\n".join(
        f"  - {fp}" for fp in session.cross_session_files
    ) or "  (nenhum)"

    project_info = session.project_name or "(não detectado)"
    bash_health = (
        f"{session.bash_success_rate:.0f}% sucesso"
        if session.bash_success_rate > 0 else "(sem dados)"
    )

    return f"""Você é um assistente de produtividade para desenvolvedores que usam Claude Code.

Analise os dados abaixo e gere insights REAIS e ACIONÁVEIS em português brasileiro.

SESSÃO ATUAL:
- Projeto: {project_info}
- Duração: {session.duration_minutes:.0f} minutos
- Total de tool calls: {session.total_tools}
- Edits/Writes (código): {session.edit_count}
- Reads/Greps (leitura): {session.read_count}
- Bash (comandos): {session.bash_count}
- Bash health: {bash_health}
- Arquivos únicos editados: {session.unique_files}
- Pico de atividade: {peak_hour:02d}h
- Subagents invocados: {session.agent_calls}
- Burst médio de edits: {session.avg_edit_burst:.1f} edits consecutivos
- Linguagens editadas: {lang_lines}
- Arquivos com múltiplas edições:
{repeated}
- Arquivos retomados de sessões anteriores:
{cross_files}

HISTÓRICO 7 DIAS:
{hist_lines}

Gere de 4 a 6 insights específicos, diretos e acionáveis com base nos dados reais acima.
Foque em padrões concretos: se o ratio bash/edit é alto, fale disso; se há arquivos repetidos, mencione-os pelo nome; se a produtividade caiu, diga quando; se a taxa de falha em Bash está alta, mencione; se há concentração em uma linguagem, comente.

Responda APENAS com JSON válido, sem texto adicional, neste formato:
[
  {{"category": "tip|warning|strength|info", "title": "título curto (max 65 chars)", "detail": "explicação de 1-2 frases com recomendação concreta"}},
  ...
]"""


def generate_insights(session: SessionStats, history: list[DailyStats]) -> list[dict]:
    """
    Gera insights reais via Claude CLI.
    Retorna lista de dicts com keys: category, title, detail.
    Em caso de erro, retorna insight de fallback.
    """
    prompt = _build_prompt(session, history)
    try:
        raw = _run_claude(prompt, timeout=60)
        # Extrai o JSON da resposta (pode vir com markdown code fences)
        raw = raw.strip()
        if raw.startswith("```"):
            lines = raw.splitlines()
            raw = "\n".join(lines[1:-1] if lines[-1] == "```" else lines[1:])
        return json.loads(raw)
    except (subprocess.TimeoutExpired, FileNotFoundError, json.JSONDecodeError, Exception):
        local = analyze(session, history)
        return [{"category": i.category, "title": i.title, "detail": i.detail} for i in local]
