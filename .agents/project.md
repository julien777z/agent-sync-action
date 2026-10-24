# Agent Sync Action

## Canonical Configuration

Agent Sync owns agent configuration in `.agents/` and generates usable configuration for each
supported harness. A capability is complete only when its generated output includes the wiring
needed for discovery and use. Do not rely on manually maintained harness configuration or assumed
harness behavior to supply missing wiring. Preserve native trust and approval requirements.

For example, copying hook scripts alone is incomplete: their event registrations must also be
configured canonically and generated for each supported harness.

## Skill Metadata

`short_description` is optional local metadata for skill indexes. Agent Sync records the last
upstream value and whether the installed summary is a local edit in the skill's `metadata`, so local
edits survive vendor refreshes while unchanged upstream summaries can update. Agent harnesses do not
recognize this field as a skill feature, so keep it out of consumer-facing capability documentation.
An existing vendored summary without provenance must be classified before refresh: mark
`metadata.agent_sync_local_short_description: true` to keep it, or remove `short_description` to
accept the upstream value.
