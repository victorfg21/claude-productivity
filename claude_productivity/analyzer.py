"""
Tipos compartilhados para insights.
A geração real de insights agora é feita via claude --print em claude_client.py.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List

from .db import SessionStats, DailyStats


@dataclass
class Insight:
    category: str   # "warning" | "tip" | "strength" | "info"
    title: str
    detail: str


CATEGORY_ICON = {
    "warning":  "⚠",
    "tip":      "⚡",
    "strength": "✓",
    "info":     "◈",
}


def analyze(session: SessionStats, history: List[DailyStats]) -> List[Insight]:
    insights: List[Insight] = []

    # ── 1. Arquivos editados múltiplas vezes ─────────────────────────────
    for file_path, count in session.repeated_files:
        name = Path(file_path).name if file_path else "arquivo"
        insights.append(Insight(
            category="warning",
            title=f"`{name}` editado {count}x nesta sessão",
            detail=(
                "Muitas iterações no mesmo arquivo sugerem alta complexidade. "
                "Considere dividir em módulos menores ou refatorar responsabilidades."
            ),
        ))

    # ── 2. Ratio Bash/Edit alto — trial-and-error ────────────────────────
    if session.edit_count > 0:
        ratio = session.bash_count / session.edit_count
        if ratio > 2.5:
            insights.append(Insight(
                category="tip",
                title=f"Alto ratio Bash/Edit ({ratio:.1f}x)",
                detail=(
                    "Muitos comandos para poucos edits indica ciclos de tentativa-e-erro. "
                    "Considere escrever testes primeiro (TDD) ou revisar o approach antes de executar."
                ),
            ))

    # ── 3. Muitos reads antes do primeiro edit — dificuldade de navegação ─
    if session.read_count > 0 and session.edit_count > 0:
        read_edit_ratio = session.read_count / session.edit_count
        if read_edit_ratio > 3:
            insights.append(Insight(
                category="tip",
                title=f"Muitas leituras por edit ({read_edit_ratio:.1f}x)",
                detail=(
                    "Bastante tempo explorando o código antes de editar. "
                    "Tags, um CLAUDE.md com mapa do projeto, ou melhor estrutura de pastas podem ajudar."
                ),
            ))

    # ── 4. Sessão longa sem pausa ────────────────────────────────────────
    if session.duration_minutes > 120:
        hours = session.duration_minutes / 60
        insights.append(Insight(
            category="warning",
            title=f"Sessão ativa há {hours:.1f}h",
            detail=(
                "Sessões muito longas reduzem a qualidade das decisões. "
                "Considere a técnica Pomodoro (25min foco / 5min pausa)."
            ),
        ))

    # ── 5. Pouca atividade de testes ─────────────────────────────────────
    test_edits = sum(
        1 for e in session.recent_events
        if e.get("file_path") and (
            "test" in (e["file_path"] or "").lower() or
            "spec" in (e["file_path"] or "").lower()
        )
    )
    total_code_edits = len([
        e for e in session.recent_events
        if e.get("tool_name") in ("Edit", "Write", "MultiEdit")
    ])
    if total_code_edits > 5 and test_edits == 0:
        insights.append(Insight(
            category="tip",
            title="Nenhum arquivo de teste editado",
            detail=(
                "Você fez vários edits sem tocar em testes. "
                "Cobertura de testes reduz regressões e acelera iterações futuras."
            ),
        ))
    elif test_edits > 0:
        pct = int((test_edits / max(total_code_edits, 1)) * 100)
        insights.append(Insight(
            category="strength",
            title=f"{test_edits} arquivo(s) de teste editado(s) ({pct}%)",
            detail="Bom ritmo de testes! Manter isso reduz bugs em produção.",
        ))

    # ── 6. Horário de pico ───────────────────────────────────────────────
    hourly = session.hourly_activity
    peak_hour = hourly.index(max(hourly)) if max(hourly) > 0 else -1
    if peak_hour >= 0 and max(hourly) > 5:
        insights.append(Insight(
            category="info",
            title=f"Pico de produtividade: {peak_hour:02d}h",
            detail=(
                f"Você foi mais produtivo às {peak_hour:02d}h com {max(hourly)} ações. "
                "Reserve esse horário para tarefas que exigem mais foco."
            ),
        ))

    # ── 7. Tendência semanal ─────────────────────────────────────────────
    if len(history) >= 3:
        recent_avg = sum(d.total_tools for d in history[-3:]) / 3
        older_avg  = sum(d.total_tools for d in history[:-3]) / max(len(history) - 3, 1)
        if older_avg > 0:
            delta_pct = ((recent_avg - older_avg) / older_avg) * 100
            if delta_pct > 15:
                insights.append(Insight(
                    category="strength",
                    title=f"Produtividade em alta (+{delta_pct:.0f}% vs semana anterior)",
                    detail="Você está usando o Claude de forma mais eficiente. Continue assim!",
                ))
            elif delta_pct < -20:
                insights.append(Insight(
                    category="info",
                    title=f"Atividade reduzida ({delta_pct:.0f}% vs semana anterior)",
                    detail=(
                        "Pode ser uma semana de reuniões ou planejamento — tudo bem. "
                        "Se for bloqueio técnico, tente decompor as tarefas em partes menores."
                    ),
                ))

    # ── 8. Alta diversidade de arquivos — boa ────────────────────────────
    if session.unique_files > 10:
        insights.append(Insight(
            category="strength",
            title=f"{session.unique_files} arquivos únicos editados",
            detail="Boa amplitude na sessão — você está atacando o problema de forma sistêmica.",
        ))

    # ── 9. Sessão muito curta sem edits ─────────────────────────────────
    if session.duration_minutes < 5 and session.edit_count == 0:
        insights.append(Insight(
            category="info",
            title="Sessão iniciada sem edits ainda",
            detail="Fase de exploração — normal. Os insights ficam mais precisos após as primeiras edições.",
        ))

    # ── 10. Taxa de sucesso de comandos Bash ────────────────────────────
    if session.bash_count > 3 and session.bash_success_rate > 0:
        if session.bash_success_rate < 70:
            insights.append(Insight(
                category="warning",
                title=f"Alta taxa de falha em Bash ({100 - session.bash_success_rate:.0f}% falhas)",
                detail=(
                    "Mais de 30% dos comandos estão falhando. "
                    "Verifique erros de compilação, testes ou configuração de ambiente."
                ),
            ))
        elif session.bash_success_rate >= 90:
            insights.append(Insight(
                category="strength",
                title=f"Comandos Bash com {session.bash_success_rate:.0f}% de sucesso",
                detail="Excelente taxa de acerto — boa qualidade nos comandos executados.",
            ))

    # ── 11. Concentração em linguagem ────────────────────────────────────
    if session.language_breakdown:
        total_ext = sum(session.language_breakdown.values())
        top_ext, top_cnt = next(iter(session.language_breakdown.items()))
        if total_ext > 0:
            pct = int((top_cnt / total_ext) * 100)
            if pct >= 80 and len(session.language_breakdown) == 1:
                insights.append(Insight(
                    category="info",
                    title=f"Sessão focada em .{top_ext} ({pct}% dos edits)",
                    detail=f"Toda a atividade de código concentrada em arquivos .{top_ext}. Foco alto na tecnologia.",
                ))

    # ── 12. Uso intenso de subagents ────────────────────────────────────
    if session.agent_calls > 5:
        insights.append(Insight(
            category="tip",
            title=f"{session.agent_calls} subagents invocados nesta sessão",
            detail=(
                "Alto uso de subagents pode indicar tarefas complexas ou exploração ampla. "
                "Avalie se alguns podem ser substituídos por comandos diretos para ganhar velocidade."
            ),
        ))

    # ── 13. Edits muito fragmentados ─────────────────────────────────────
    if session.edit_count > 10 and 0 < session.avg_edit_burst < 1.5:
        insights.append(Insight(
            category="tip",
            title=f"Edits fragmentados (burst médio: {session.avg_edit_burst:.1f})",
            detail=(
                "Cada edit é frequentemente interrompido por leitura ou comando. "
                "Tente agrupar mudanças relacionadas antes de verificar o resultado."
            ),
        ))
    elif session.avg_edit_burst >= 4.0:
        insights.append(Insight(
            category="strength",
            title=f"Alto foco nos edits (burst médio: {session.avg_edit_burst:.1f})",
            detail="Você está editando em blocos contínuos — padrão de alta concentração.",
        ))

    # ── 14. Continuidade entre sessões ──────────────────────────────────
    if len(session.cross_session_files) >= 3:
        insights.append(Insight(
            category="info",
            title=f"{len(session.cross_session_files)} arquivos retomados de sessões anteriores",
            detail=(
                "Você está continuando trabalho de sessões passadas. "
                "Considere um CLAUDE.md ou TODO atualizado para retomar contexto mais rápido."
            ),
        ))

    if not insights:
        insights.append(Insight(
            category="info",
            title="Dados insuficientes para análise",
            detail="Continue trabalhando — os insights aparecem após alguns minutos de atividade.",
        ))

    return insights
