#!/usr/bin/env bash
# install.sh — configura claude-productivity no Claude Code
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HOOK_SCRIPT="$SCRIPT_DIR/hooks/logger.py"
SETTINGS_FILE="$HOME/.claude/settings.json"

echo "══════════════════════════════════════════"
echo "  claude-productivity // install"
echo "══════════════════════════════════════════"

# 1. Detecta o comando pip disponível
echo "▶ Instalando dependências..."
if command -v pip3 &>/dev/null; then
    PIP="pip3"
elif command -v pip &>/dev/null; then
    PIP="pip"
elif python3 -m pip --version &>/dev/null 2>&1; then
    PIP="python3 -m pip"
else
    echo "✗ Nenhum pip encontrado. Instale com:"
    echo "  sudo apt install python3-pip   # Debian/Ubuntu/Fedora"
    echo "  brew install python3           # macOS"
    exit 1
fi

$PIP install -q -e "$SCRIPT_DIR"

# 2. Garante que settings.json existe
mkdir -p "$HOME/.claude"
if [ ! -f "$SETTINGS_FILE" ]; then
    echo '{}' > "$SETTINGS_FILE"
fi

# 3. Injeta hooks via Python (manipulação segura do JSON)
python3 - <<PYEOF
import json, sys

settings_path = "$SETTINGS_FILE"
hook_script   = "$HOOK_SCRIPT"

with open(settings_path) as f:
    settings = json.load(f)

settings.setdefault("hooks", {})

# PreToolUse — registra início de cada tool call para medir duração
settings["hooks"]["PreToolUse"] = [
    {
        "matcher": ".*",
        "hooks": [
            {
                "type": "command",
                "command": f"CLAUDE_HOOK_EVENT=PreToolUse python3 {hook_script}"
            }
        ]
    }
]

# PostToolUse — captura cada tool call
settings["hooks"]["PostToolUse"] = [
    {
        "matcher": ".*",
        "hooks": [
            {
                "type": "command",
                "command": f"CLAUDE_HOOK_EVENT=PostToolUse python3 {hook_script}"
            }
        ]
    }
]

# Stop — fecha a sessão
settings["hooks"]["Stop"] = [
    {
        "hooks": [
            {
                "type": "command",
                "command": f"CLAUDE_HOOK_EVENT=Stop python3 {hook_script}"
            }
        ]
    }
]

with open(settings_path, "w") as f:
    json.dump(settings, f, indent=2)

print("✓ Hooks configurados em", settings_path)
PYEOF

echo ""
echo "══════════════════════════════════════════"
echo "  Instalação concluída!"
echo ""
echo "  Para abrir o dashboard:"
echo "    claude-metrics"
echo ""
echo "  Os dados são coletados automaticamente"
echo "  em ~/.claude/productivity.db"
echo "══════════════════════════════════════════"
