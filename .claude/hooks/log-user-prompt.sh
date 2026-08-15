#!/bin/bash
# Appends every user prompt to CONVERSATION_LOG.md with a timestamp (UserPromptSubmit hook).
log_file="/home/ubuntu/educational-online-judge/CONVERSATION_LOG.md"

prompt=$(python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
except Exception:
    sys.exit(0)
sys.stdout.write(data.get('prompt') or '')
")

if [ -z "$prompt" ]; then
  exit 0
fi

ts=$(date '+%Y-%m-%d %H:%M:%S')
{
  echo ""
  echo "## [$ts] Usuari"
  echo ""
  echo "$prompt"
  echo ""
} >> "$log_file"
