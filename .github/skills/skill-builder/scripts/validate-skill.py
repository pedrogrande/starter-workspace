# !/usr/bin/env python3
"""
Skill validation script for Agent Skills (agentskills.io standard).

Checks:

- SKILL.md exists and has valid YAML frontmatter
- name field: lowercase, hyphens, matches directory, ≤64 chars
- description field: non-empty, ≤1024 chars
- SKILL.md line count under 500
- File references in SKILL.md point to existing files
- Optional directory structure (scripts/, references/, assets/)
- evals/evals.json validity (if present)

Usage:
  python scripts/validate-skill.py ./path/to/skill-name
"""

import sys
import os
import re
import json
from pathlib import Path

# ── ANSI colors ──────────────────────────────────────────────

RED = "\033[91m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RESET = "\033[0m"
BOLD = "\033[1m"


def ok(msg: str) -> str:
    return f"{GREEN}✓{RESET} {msg}"


def fail(msg: str) -> str:
    return f"{RED}✗{RESET} {msg}"


def warn(msg: str) -> str:
    return f"{YELLOW}⚠{RESET} {msg}"


# ── Validation functions ─────────────────────────────────────

errors: list[str] = []
warnings: list[str] = []
passes: list[str] = []


def check_name(name: str, dir_name: str) -> None:
    """Validate the name field per the Agent Skills specification."""
    if not name:
        errors.append("name field is empty or missing")
        return

    if len(name) > 64:
        errors.append(f"name too long: {len(name)} chars (max 64)")

    if not re.match(r"^[a-z0-9]+(-[a-z0-9]+)*$", name):
        errors.append(
            f"name '{name}' contains invalid characters. "
            "Only lowercase letters, numbers, and single hyphens allowed."
        )

    if name.startswith("-") or name.endswith("--"):
        errors.append("name must not start or end with a hyphen")

    if "--" in name:
        errors.append("name must not contain consecutive hyphens")

    if name != dir_name:
        errors.append(
            f"name '{name}' does not match directory name '{dir_name}'. "
            "This will cause SILENT load failure."
        )
    else:
        passes.append(f"name matches directory: '{name}'")

    # Check for namespace prefixes
    if "/" in name or ":" in name or "." in name:
        errors.append(
            f"name '{name}' contains namespace separators (/ : .). "
            "These cause SILENT load failure. Plugin prefixes are auto-added."
        )


def check_description(desc: str) -> None:
    """Validate the description field."""
    if not desc or not desc.strip():
        errors.append("description field is empty or missing")
        return

    if len(desc) > 1024:
        errors.append(f"description too long: {len(desc)} chars (max 1024)")

    if len(desc) < 20:
        warnings.append(
            f"description is very short ({len(desc)} chars). "
            "Consider adding more trigger context."
        )

    # Check for imperative phrasing hints
    lower = desc.lower()
    if "use this skill" in lower or "use when" in lower or "use this when" in lower:
        passes.append("description includes trigger phrasing")
    else:
        warnings.append(
            "description may benefit from imperative phrasing "
            "(e.g., 'Use this skill when...')"
        )

    # Check for vague descriptions
    vague_phrases = ["helps with", "a skill for", "this skill does"]
    for phrase in vague_phrases:
        if phrase in lower:
            warnings.append(
                f"description contains vague phrasing: '{phrase}'. "
                "Consider being more specific about when to trigger."
            )


def check_line_count(skill_md_path: Path) -> None:
    """Check SKILL.md line count."""
    with open(skill_md_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    line_count = len(lines)
    if line_count > 500:
        warnings.append(
            f"SKILL.md is {line_count} lines (recommended max 500). "
            "Consider moving detail to references/."
        )
    else:
        passes.append(f"SKILL.md is {line_count} lines (under 500)")


def check_file_references(skill_md_path: Path, skill_dir: Path) -> None:
    """Check that Markdown links in SKILL.md point to existing files."""
    with open(skill_md_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Match [text](relative/path) — exclude URLs
    pattern = r"\[([^\]]*)\]\((?!https?://|mailto:)([^)]+)\)"
    matches = re.findall(pattern, content)

    if not matches:
        return

    for link_text, link_path in matches:
        # Strip any anchor
        clean_path = link_path.split("#")[0]
        if not clean_path:
            continue

        resolved = skill_dir / clean_path
        if not resolved.exists():
            errors.append(
                f"broken file reference: [{link_text}]({link_path}) — "
                f"file not found at {resolved}"
            )
        else:
            passes.append(f"file reference valid: [{link_text}]({link_path})")

    # Check for unreferenced files in optional directories
    referenced_files = {link_path.split("#")[0] for _, link_path in matches}
    for subdir in ["scripts", "references", "assets"]:
        sub_path = skill_dir / subdir
        if sub_path.exists():
            for item in sub_path.rglob("*"):
                if item.is_file():
                    rel = str(item.relative_to(skill_dir))
                    if rel not in referenced_files:
                        # Check if any reference contains this path as a prefix
                        found = any(
                            rel.startswith(r) or r.endswith(rel)
                            for r in referenced_files
                        )
                        if not found:
                            warnings.append(
                                f"unreferenced file in {subdir}/: {rel}. "
                                "Files not referenced in SKILL.md won't be loaded."
                            )


def check_directory_structure(skill_dir: Path) -> None:
    """Check for recommended directory structure."""
    for subdir in ["scripts", "references", "assets", "evals"]:
        sub_path = skill_dir / subdir
        if sub_path.exists():
            passes.append(f"directory present: {subdir}/")

    # Check evals.json if evals/ exists
    evals_path = skill_dir / "evals" / "evals.json"
    if evals_path.exists():
        try:
            with open(evals_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if "skill_name" not in data:
                warnings.append("evals.json missing 'skill_name' field")
            if "evals" not in data:
                warnings.append("evals.json missing 'evals' array")
            else:
                for ev in data["evals"]:
                    if "prompt" not in ev:
                        warnings.append(f"eval id {ev.get('id', '?')} missing 'prompt'")
                    if "expected_output" not in ev:
                        warnings.append(
                            f"eval id {ev.get('id', '?')} missing 'expected_output'"
                        )
                passes.append(f"evals.json valid with {len(data['evals'])} test cases")
        except json.JSONDecodeError as e:
            errors.append(f"evals.json is not valid JSON: {e}")


def parse_frontmatter(content: str) -> tuple[dict | None, str | None]:
    """Parse YAML frontmatter from Markdown content."""
    if not content.startswith("---"):
        return None, "SKILL.md must start with YAML frontmatter (---)"

    parts = content.split("---", 2)
    if len(parts) < 3:
        return None, "Malformed frontmatter — missing closing ---"

    yaml_text = parts[1].strip()
    body = parts[2]

    # Simple YAML parsing (avoid dependency on PyYAML for portability)
    frontmatter: dict[str, str] = {}
    current_key = None
    current_value: list[str] = []

    for line in yaml_text.split("\n"):
        # Skip comments
        if line.strip().startswith("#"):
            continue

        # Key: value pattern
        match = re.match(r"^(\w[\w-]*)\s*:\s*(.*)", line)
        if match:
            if current_key:
                frontmatter[current_key] = "\n".join(current_value).strip()
            current_key = match.group(1)
            current_value = [match.group(2)]
        elif current_key and line.startswith("  "):
            current_value.append(line.strip())
        elif current_key and line.strip() == "":
            # Empty line in a multi-line value
            current_value.append("")

    if current_key:
        frontmatter[current_key] = "\n".join(current_value).strip()

    return frontmatter, None


# ── Main ──────────────────────────────────────────────────────


def main() -> int:
    if len(sys.argv) < 2:
        print(
            f"{BOLD}Usage:{RESET} python scripts/validate-skill.py ./path/to/skill-name"
        )
        return 1

    skill_dir = Path(sys.argv[1]).resolve()

    if not skill_dir.is_dir():
        print(fail(f"directory not found: {skill_dir}"))
        return 1

    skill_md = skill_dir / "SKILL.md"

    if not skill_md.exists():
        print(fail(f"SKILL.md not found in {skill_dir}"))
        return 1

    print(f"\n{BOLD}Validating skill: {skill_dir.name}{RESET}\n")

    # Read and parse
    with open(skill_md, "r", encoding="utf-8") as f:
        content = f.read()

    frontmatter, parse_error = parse_frontmatter(content)
    if parse_error:
        print(fail(parse_error))
        return 1

    if not frontmatter:
        print(fail("no frontmatter fields found"))
        return 1

    # Validate name
    name = frontmatter.get("name", "")
    check_name(name, skill_dir.name)

    # Validate description
    description = frontmatter.get("description", "")
    check_description(description)

    # Check line count
    check_line_count(skill_md)

    # Check file references
    check_file_references(skill_md, skill_dir)

    # Check directory structure
    check_directory_structure(skill_dir)

    # ── Report ────────────────────────────────────────────────
    if passes:
        print(f"\n{BOLD}Passed:{RESET}")
        for p in passes:
            print(ok(p))

    if warnings:
        print(f"\n{BOLD}Warnings:{RESET}")
        for w in warnings:
            print(warn(w))

    if errors:
        print(f"\n{BOLD}Errors:{RESET}")
        for e in errors:
            print(fail(e))
        print(f"\n{RED}{BOLD}{len(errors)} error(s), {len(warnings)} warning(s){RESET}")
        return 1

    print(
        f"\n{GREEN}{BOLD}All checks passed.{RESET} "
        f"{len(passes)} check(s) passed, {len(warnings)} warning(s)."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
