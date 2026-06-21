#!/bin/bash
# PostToolUse hook: auto-formats Python files after every edit.
# Adapt the formatter command to your project's stack (prettier, ruff, etc.).
#
# Install: chmod +x this file, reference it in agent frontmatter:
#   hooks:
#     PostToolUse:
#       - type: "command"
#         command: "./scripts/hooks/auto-format.sh"
#         timeout: 10
#
# Requires: ruff (https://docs.astral.sh/ruff/)

set -euo pipefail

INPUT=$(cat)

# Extract the file path from the tool input JSON.
FILE=$(echo "$INPUT" | jq -r '.tool_input.file // .tool_input.files[0] // empty' 2>/dev/null || echo "")

if [[ -z "$FILE" ]]; then
  exit 0
fi

if [[ "$FILE" == *.py ]]; then
  ruff format "$FILE" 2>/dev/null || true
  ruff check --fix "$FILE" 2>/dev/null || true
fi

exit 0