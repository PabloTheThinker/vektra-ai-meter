#!/usr/bin/env bash
set -euo pipefail

METER="${VEKTRA_AI_METER_BIN:-$HOME/.local/bin/ai-meter}"
SNAPSHOT="$HOME/.local/share/vektra-ai-meter/snapshot.json"

if [[ ! -f "$SNAPSHOT" ]]; then
  "$METER" snapshot --write >/dev/null
fi

python3 - <<'PY'
import json, os
path = os.path.expanduser("~/.local/share/vektra-ai-meter/snapshot.json")
with open(path, encoding="utf-8") as f:
    data = json.load(f)
summary = data.get("summary", {})
text = f"Meter {summary.get('total_tokens_fmt', '—')} · {summary.get('active_sessions', 0)} active"
tooltip = []
for provider in data.get("providers", []):
    tooltip.append(
        f"{provider.get('label')}: {provider.get('total_tokens', 0)} tokens, "
        f"{provider.get('sessions', 0)} sessions"
    )
print(json.dumps({
    "text": text,
    "tooltip": "\n".join(tooltip),
    "class": "vektra-ai-meter",
}))
PY