# Plano de Enriquecimento de Dados — claude-productivity

## Objetivo
Capturar métricas adicionais no hook `PostToolUse` e expô-las no TUI para gerar insights mais precisos e acionáveis.

---

## 1. Novos dados capturados no hook (`hooks/logger.py`)

| Campo | Tipo | Origem | Descrição |
|---|---|---|---|
| `exit_code` | INTEGER | `tool_response.exit_code` / `is_error` | Código de saída de comandos Bash (0=ok, 1+=falha) |
| `project_name` | TEXT | Derivado de `file_path` | Nome do projeto/repo extraído do caminho do arquivo |
| `file_extension` | TEXT | Derivado de `file_path` | Extensão do arquivo editado (.cs, .ts, .vue, .py...) |
| `agent_subtype` | TEXT | `tool_input.subagent_type` | Subtipo do agente quando tool_name=Agent |

### Migração segura
Cada nova coluna é adicionada via `ALTER TABLE` dentro de try/except, garantindo compatibilidade com bancos existentes.

---

## 2. Enriquecimento do schema SQLite (`db.py`)

### Novos campos em `SessionStats`
```python
bash_success_rate: float       # % de Bash com exit_code conhecido e = 0
language_breakdown: dict       # {"cs": 23, "ts": 15, "vue": 8} — top 5 extensões
project_name: Optional[str]    # projeto mais frequente na sessão
agent_calls: int               # total de invocações de subagents
avg_edit_burst: float          # média de edits consecutivos (sem read/bash no meio)
cross_session_files: List[str] # arquivos editados também em sessões anteriores
```

### Novas queries
- `bash_success_rate`: conta Bash onde `exit_code IS NOT NULL`, calcula % de sucesso
- `language_breakdown`: GROUP BY `file_extension` nos edits da sessão
- `project_name`: SELECT mais frequente por COUNT(*) na sessão
- `agent_calls`: COUNT onde `tool_name = 'Agent'`
- `avg_edit_burst`: calculado em Python a partir dos eventos ordenados por timestamp
- `cross_session_files`: EXISTS em eventos de sessões anteriores para mesmo `file_path`

---

## 3. Novos insights analíticos (`analyzer.py`)

| Condição | Categoria | Insight |
|---|---|---|
| `bash_success_rate < 70%` | warning | Taxa de falha de comandos alta |
| `bash_success_rate >= 90%` | strength | Comandos com alta taxa de sucesso |
| Uma extensão > 80% dos edits | info | Concentração em linguagem única |
| `agent_calls > 5` em sessão | tip | Muitas delegações para subagents |
| `cross_session_files >= 3` | info | Continuação de trabalho de sessões anteriores |
| `avg_edit_burst < 1.5` | tip | Edits muito fragmentados — possível indecisão |
| `avg_edit_burst >= 4.0` | strength | Excelente foco — alto burst de edits |

---

## 4. Melhorias no TUI (`tui/app.py`)

### HeaderWidget
- Exibe `◈ {project_name}` ao lado do título quando disponível

### StatsWidget (campos adicionados)
```
BASH HEALTH  ████████░░  80%  ●12 ok  ●3 fail
LINGUAGENS   ████ cs(38%)  ██ ts(22%)  █ vue(14%)
FOCO         ▓▓▓▓▓▓░░░░   2.4 edits/burst
AGENTES      3 chamadas
```

### claude_client.py
- Prompt enriquecido com `bash_success_rate`, `language_breakdown`, `project_name`, `agent_calls`, `avg_edit_burst`, `cross_session_files`

---

## 5. Prioridade de implementação

```
ALTA (max impacto, baixo esforço):
  [x] exit_code no logger → bash_success_rate no TUI
  [x] file_extension no logger → language breakdown no StatsWidget
  [x] project_name no logger → badge no HeaderWidget

MÉDIA:
  [x] cross_session_files query no db.py
  [x] avg_edit_burst cálculo no db.py
  [x] Novas seções no StatsWidget

BAIXA:
  [x] agent_subtype tracking
  [x] Enriquecimento do prompt do claude_client.py
  [x] Novos insights no analyzer.py
```

---

## 6. Compatibilidade

- Todos os novos campos têm valor padrão (0, `{}`, `None`, `[]`)
- Bancos existentes são migrados automaticamente via ALTER TABLE com try/except
- Demo data atualizada para refletir os novos campos
- Nenhuma breaking change nas interfaces existentes
