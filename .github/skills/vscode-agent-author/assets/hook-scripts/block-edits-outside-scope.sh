#!/bin/bash
# PreToolUse hook: blocks edits to files outside an allowed scope.
# Adapt the `case` pattern to your project's allowed paths.
#
# Install: chmod +x this file, reference it in agent frontmatter:
#   hooks:
#     PreToolUse:
#       - type: "command"
#         command: "./scripts/hooks/block-edits-outside-scope.sh"
#         timeout: 5
#
# Requires: jq (https://stedolan.github.io/jq/)

set -euo pipefail

INPUT=$(cat)

# Extract file paths from the tool input JSON.
# The schema varies by tool — handle both .tool_input.files[] and .tool_input.file.
FILES=$(echo "$INPUT" | jq -r '.tool_input.files[]? // .tool_input.file // empty' 2>/dev/null || echo "")

for FILE in $FILES; do
  case "$FILE" in
    src/*|test/*) ;;  # Allowed — continue
    *)
      cat <<EOF
{
  "hookSpecificOutput": {
    "hookEventName": "PreToolUse",
    "permissionDecision": "deny",
    "permissionDecisionReason": "File outside allowed scope: $FILE. Only src/ and test/ are permitted."
  }
}
EOF
      exit 0
      ;;
  esac
done

# Allow
exit 0