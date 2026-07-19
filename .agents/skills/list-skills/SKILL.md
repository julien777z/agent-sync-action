---
name: list-skills
description: List the names of skills in the canonical .agents skills folder. Use when the user asks to list available repository skills.
---

# List Skills

Read the canonical `.agents/skills` folder and return the name of each direct child skill folder.

## Output

Return only this heading and Markdown list, sorted alphabetically, with no status summary or extra prose:

```markdown
Skills

- skill-name
```

If no skills exist, return `- None`.
