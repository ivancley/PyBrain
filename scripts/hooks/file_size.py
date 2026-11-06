#!/usr/bin/env python3
"""Hook PostToolUse (Write|Edit): a régua de tamanho na hora da escrita, não no gate.

A guarda `test_file_size` só falha no `make quality`, quando o arquivo já cresceu;
aqui o agente é avisado (300) ou bloqueado (500) na própria edição, com a fronteira
sugerida. Saída 2 devolve a mensagem ao agente e bloqueia; 0 só avisa.
"""

import json
import sys
from pathlib import Path

TRIGGER, LIMIT = 300, 500
EXT = {".py", ".sql"}
IGNORED = ("tests", "node_modules", ".git", ".venv", "scripts")
SUGGESTION = {
    ".py": "um módulo por assunto: temporal.py, store.py, retrieval.py, connection/<adaptador>.py",
    ".sql": "uma migração por mudança de schema; uma migração grande costuma ser duas decisões",
}

data = json.load(sys.stdin)
path = (data.get("tool_input") or {}).get("file_path") or ""
file = Path(path)
if file.suffix not in EXT or any(p in file.parts for p in IGNORED) or not file.exists():
    sys.exit(0)
lines = len(file.read_text(errors="ignore").splitlines())
if lines > LIMIT:
    print(
        f"{file}: {lines} linhas — acima do limite de {LIMIT} (CLAUDE.md, 'Tamanho de arquivo'). "
        f"Divida antes de seguir: {SUGGESTION[file.suffix]}.",
        file=sys.stderr,
    )
    sys.exit(2)
if lines > TRIGGER:
    print(
        f"{file}: {lines} linhas — passou de {TRIGGER}. Hora da fronteira: {SUGGESTION[file.suffix]}."
    )
sys.exit(0)
