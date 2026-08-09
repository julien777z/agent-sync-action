---
name: generic-push
description: Keep repository publishing metadata generic and isolated. Use when a user requests generic delivery metadata, invokes generic-push, or applies generic publishing rules across multiple repositories.
---

# Generic Publishing Metadata

- Keep branch names, commit messages, pull request titles, and pull request bodies generic without requiring them to repeat one phrase.
- Choose independent wording for each artifact and commit so each message describes its change category without exposing domain names, sensitive identifiers, or repository-specific context.
  Examples: `Fixes action button`, `Fixes UI issue`, or `Updates tests`.
- Use the repository's required branch prefix with a slug derived from a generic description of the overall change.
  Example: `agent/fixes-ui-bugs`, where `agent/` stands for the repository-required prefix.
- Keep pull request titles concise, but allow pull request bodies to use longer paragraphs, bullets, and validation notes when every detail remains generic.
- Longer descriptions may explain behavior and causes with generic nouns such as `action`, `button`, `modal`, `request`, or `page`.
- Prefer an informative generic description over a one-sentence body that omits distinct change categories or validation performed.
- Preserve an existing non-default branch when repository rules require it, while keeping new commit and pull request metadata generic.
- When multiple repositories are involved and this skill applies to any of them, keep every repository's publishing metadata independent and isolated.
- Never mention another involved repository, its branch, pull request, implementation, or coordination context in a repository's branch name, commit message, pull request title, pull request body, or other publishing metadata.
- Leave automation-owned branch and pull request metadata unchanged.
