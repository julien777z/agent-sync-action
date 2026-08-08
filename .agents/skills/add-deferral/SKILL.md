---
name: add-deferral
description: Record deferred work as a directory under deferrals/ and open a pull request containing only that deferral, branched from the default branch. Use when the user invokes /add-deferral or $add-deferral, when work is being consciously left undone, or whenever a deferral would otherwise be described only in conversation or in a pull request body.
---

# Add Deferral

Turn deferred work into a directory under `deferrals/` and a pull request that carries nothing
else, so it can be merged independently of the change that surfaced it.

## Workflow

1. Name the problem with a short slug, not a proposed fix. Reuse an existing directory when the
   same deferral is already recorded.
2. Gather supporting documents that already exist and place the relevant material in the deferral
   directory so it remains self-contained after the originating branch is gone.
3. Write `DEFERRAL.md` with the concrete deferred work, why it remains open, the scope of picking
   it up, and a table of supporting files.
4. Create an isolated worktree from the fetched remote default branch on a collision-free branch
   that follows the repository's branch-naming convention.
5. Commit only the deferral directory. Verify the complete diff against the remote default branch
   before pushing.
6. Push and open a ready-for-review pull request titled for the deferred problem. The body states
   what is deferred and why it remains open.
7. Leave the original checkout and interrupted work unchanged.

## Guardrails

- Record a deferral when the decision is made, not at the end of the task.
- One deferral belongs in each pull request.
- Never fold a deferral into the branch that produced it.
- If the deferred work is small enough to complete safely within the active task, do it instead.
