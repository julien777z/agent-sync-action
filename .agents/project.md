# Agent Sync Action

## Skill Metadata

`short_description` is optional local metadata for skill indexes. Agent Sync records the last
upstream value and whether the installed summary is a local edit in the skill's `metadata`, so local
edits survive vendor refreshes while unchanged upstream summaries can update. Agent harnesses do not
recognize this field as a skill feature, so keep it out of consumer-facing capability documentation.
An existing vendored summary without provenance must be classified before refresh: mark
`metadata.agent_sync_local_short_description: true` to keep it, or remove `short_description` to
accept the upstream value.
