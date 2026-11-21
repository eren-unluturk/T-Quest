---
description: Regenerate the AUTO blocks in PLAN.md and PITCH.md
---
Run `node scripts/sync-docs.mjs`. It updates only the blocks between `AUTO` markers (roadmap progress, open issue counts, open blockers, Tiger Data numbers) and never touches hand-written text. If it exits non-zero, a marker is missing: fix the marker, do not edit the generated text by hand. Run it after completing or verifying a roadmap item.
