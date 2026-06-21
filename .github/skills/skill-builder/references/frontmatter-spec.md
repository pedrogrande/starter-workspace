# SKILL.md Frontmatter Specification

Complete reference for YAML frontmatter fields in SKILL.md files.

## Required fields

### `name`

- 1-64 characters
- Lowercase letters (`a-z`), numbers (`0-9`), and hyphens (`-`) only
- Must NOT start or end with a hyphen
- Must NOT contain consecutive hyphens (`--`)
- MUST match the parent directory name exactly
- Invalid names cause SILENT load failure

Valid: `pdf-processing`, `data-analysis`, `code-review`
Invalid: `PDF-Processing` (uppercase), `-pdf` (leading hyphen),
`pdf--processing` (double hyphen)

### `description`

- 1-1024 characters
- Describe what the skill does AND when to use it
- Use imperative phrasing: "Use this skill when..."
- Include specific keywords for trigger matching
- Include indirect trigger contexts (tasks that need the skill but don't
  name it explicitly)

Good:

```
Extracts text and tables from PDF files, fills PDF forms, and merges
multiple PDFs. Use when working with PDF documents or when the user
mentions PDFs, forms, or document extraction.
```

Poor:

```
Helps with PDFs.
```

## Optional fields

### `argument-hint`

Hint text shown in the chat input field when the skill is invoked as a
slash command. Helps users understand what to provide.

```yaml
argument-hint: [test file] [options]
```

### `user-invocable`

Controls whether the skill appears as a slash command in the `/` menu.
Default: `true`. Set `false` to hide from menu while still allowing
automatic loading by the agent.

### `disable-model-invocation`

Controls whether the agent can automatically load the skill based on
relevance. Default: `false`. Set `true` to require manual `/` invocation.

### `context` (experimental)

Controls how the skill loads:

- `inline` (default): Instructions added to parent agent's context
- `fork`: Skill runs in a dedicated subagent; only final result returns

Use `fork` for skills that:

- Read many files or run lengthy investigations
- Produce a focused result (summary, report, small edits)
- Should not influence parent agent beyond final output

Requires `github.copilot.chat.skillTool.enabled` setting in VS Code.

### `license`

License name or reference to a bundled license file.

```yaml
license: Apache-2.0
```

### `compatibility`

Max 500 characters. Indicates environment requirements.

```yaml
compatibility: Requires Python 3.12+ and uv
```

### `metadata`

Arbitrary key-value mapping for additional metadata.

```yaml
metadata:
  author: example-org
  version: "1.0"
```

### `allowed-tools` (experimental)

Space-separated string of pre-approved tools.

```yaml
allowed-tools: Bash(git:*) Bash(jq:*) Read
```

## Invocation modes summary

| Configuration | Slash command | Auto-loaded | Use case |
|---|---|---|---|
| Default (both omitted) | Yes | Yes | General-purpose |
| `user-invocable: false` | No | Yes | Background knowledge |
| `disable-model-invocation: true` | Yes | No | Manual invocation only |
| Both set | No | No | Disabled |

## Plugin distribution note

When a skill is distributed through a plugin, the plugin name is
automatically used as a command prefix (e.g., `/my-plugin:test-runner`).
Do NOT manually add namespace prefixes to the `name` field.
