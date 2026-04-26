---
applyTo: "**/*.{py,sh,yml,yaml,toml,cfg,ini}"
description: "Cross-platform encoding rules -- keep all source and CLI output within printable ASCII (does NOT apply to documentation)"
---

# Encoding Rules

## Constraint

**Source code files and CLI output strings** must stay within **printable ASCII** (U+0020-U+007E).

This rule **does NOT apply** to:
- Markdown documentation (`*.md`, `*.mdx`)
- README, CHANGELOG, instruction files, skill files, agent files
- Anything rendered by a Markdown viewer (GitHub, docs sites, IDE preview)

Documentation is rendered by Markdown engines that handle Unicode natively. Restricting prose to ASCII degrades readability (no Unicode box-drawing for trees, no em dashes, no curly quotes) without any cross-platform benefit.

## What is in scope

- Python source files (`*.py`)
- Shell scripts (`*.sh`)
- YAML / TOML / INI / CFG configuration files
- CI workflow files (`.github/workflows/*.yml`)
- CLI help strings, log messages, error messages, and any string emitted to stdout/stderr

In these contexts, do NOT use:
- Emojis (e.g. `:rocket:`, `:sparkles:`, `:x:`)
- Unicode box-drawing characters (e.g. `-`, `|`, `+` used for trees -- ASCII only)
- Em dashes (`--`), en dashes (`-`), curly quotes (`"`, `"`, `'`, `'`)
- Any character outside the ASCII range (codepoint > U+007E)

**Why**: Windows `cp1252` terminals raise `UnicodeEncodeError: 'charmap' codec can't encode character` for any character outside cp1252. Keeping CLI output within ASCII guarantees identical behavior on every platform without dual-path fallback logic.

## Status symbol convention

Use ASCII bracket notation consistently across all CLI output, help text, and log messages:

| Symbol | Meaning              |
|--------|----------------------|
| `[+]`  | success / confirmed  |
| `[!]`  | warning              |
| `[x]`  | error                |
| `[i]`  | info                 |
| `[*]`  | action / processing  |
| `[>]`  | running / progress   |

These map directly to the `STATUS_SYMBOLS` dict in `src/apm_cli/utils/console.py`.

Exception: binary assets and third-party vendored files are excluded.
