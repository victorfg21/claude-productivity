"""Persistência de preferências do usuário (tema e idioma).

Salva em ~/.claude/productivity-prefs.json
"""

from __future__ import annotations

import json
from pathlib import Path

PREFS_PATH = Path.home() / ".claude" / "productivity-prefs.json"

_DEFAULTS: dict[str, str] = {
    "theme":    "one_dark",
    "language": "",          # vazio = detectar automaticamente
}


def load() -> dict[str, str]:
    """Carrega preferências do disco. Retorna defaults se o arquivo não existir."""
    try:
        data = json.loads(PREFS_PATH.read_text(encoding="utf-8"))
        return {**_DEFAULTS, **{k: str(v) for k, v in data.items() if k in _DEFAULTS}}
    except Exception:
        return dict(_DEFAULTS)


def save(prefs: dict[str, str]) -> None:
    """Persiste preferências no disco."""
    try:
        PREFS_PATH.parent.mkdir(parents=True, exist_ok=True)
        PREFS_PATH.write_text(
            json.dumps(prefs, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
    except Exception:
        pass
