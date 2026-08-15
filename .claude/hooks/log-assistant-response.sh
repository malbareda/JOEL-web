#!/bin/bash
# Appends Claude's final text response for the turn to CONVERSATION_LOG.md with a timestamp (Stop hook).
log_file="/home/ubuntu/educational-online-judge/CONVERSATION_LOG.md"

transcript_path=$(python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
except Exception:
    sys.exit(0)
sys.stdout.write(data.get('transcript_path') or '')
")

if [ -z "$transcript_path" ] || [ ! -f "$transcript_path" ]; then
  exit 0
fi

response=$(python3 - "$transcript_path" <<'PYEOF'
import sys, json

path = sys.argv[1]
entries = []
with open(path, encoding="utf-8") as f:
    for line in f:
        line = line.strip()
        if not line:
            continue
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            continue

# Anchor on the last genuine user-typed turn (content is a plain string).
# Tool results and skill-injected content also show up as type "user" but
# with list content, so they are excluded.
anchor = -1
for i, d in enumerate(entries):
    if d.get("type") == "user":
        msg = d.get("message", {})
        if isinstance(msg, dict) and isinstance(msg.get("content"), str):
            anchor = i

texts = []
if anchor >= 0:
    for d in entries[anchor + 1:]:
        if d.get("type") != "assistant":
            continue
        msg = d.get("message", {})
        content = msg.get("content") if isinstance(msg, dict) else None
        if isinstance(content, list):
            for block in content:
                if isinstance(block, dict) and block.get("type") == "text":
                    t = block.get("text", "")
                    if t:
                        texts.append(t)

print("\n\n".join(texts))
PYEOF
)

if [ -z "$response" ]; then
  exit 0
fi

ts=$(date '+%Y-%m-%d %H:%M:%S')
{
  echo ""
  echo "## [$ts] Claude"
  echo ""
  echo "$response"
  echo ""
} >> "$log_file"
