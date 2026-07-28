---
name: generic-push
description: Keep repository publishing metadata generic and isolated. Use when a user requests generic delivery metadata, invokes generic-push, or applies generic publishing rules across multiple repositories.
---

# Generic Publishing Metadata

- Choose one short, generic phrase that describes the change category without exposing implementation details.
  Examples: `Fixing issue`, `Fixes UI bugs`, or `Updates tests`.
- Use the repository's required branch prefix with a slug derived from that phrase.
  Example: `agent/fixes-ui-bugs`, where `agent/` stands for the repository-required prefix.
- Use the chosen phrase for every agent-authored commit message, the pull request title, and the entire pull request body.
- Preserve an existing non-default branch when repository rules require it, while keeping new commit and pull request metadata generic.
- When multiple repositories are involved and this skill applies to any of them, keep every repository's publishing metadata independent and isolated.
- Never mention another involved repository, its branch, pull request, implementation, or coordination context in a repository's branch name, commit message, pull request title, pull request body, or other publishing metadata.
- Leave automation-owned branch and pull request metadata unchanged.
