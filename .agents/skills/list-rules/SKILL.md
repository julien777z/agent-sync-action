---
name: list-rules
description: List the names of rules in the canonical .agents rules folder. Use when the user asks to list available repository rules.
---

# List Rules

Read the canonical `.agents/rules` folder and return the name of each rule file without its extension.

## Output

Return only this heading and Markdown list, sorted alphabetically, with no status summary or extra prose:

```markdown
Rules

- rule-name
```

If no rules exist, return `- None`.
