---
status: accepted
date: 2026-10-22
---

# The version answer names the oldest app build the room accepts

A tablet installed from a store never learned that the room had moved past it. `/api/version` now also serves `minimum_app: {ios, android}`, the oldest **Store build** the room accepts on each platform. The tablet compares its own build number with it and, when below, sends the team to its store (the app's ADR 0124).

The two numbers come from the settings `internalization_room_minimum_app_ios` and `internalization_room_minimum_app_android`, whole numbers from 0, where 0 means no minimum. Production names both in its deploy file, so raising one is a reviewed pull request that deploys. The number compared is the build number (the `+N` of the app's `pubspec.yaml`), never the `x.y.z`.

## Rejected

- A database row, editable from the Desk: nobody asked for it, and the minimum would change outside review.
- The semantic version: the stores order builds by number, and the app's ADR 0110 makes it one number on both platforms.
- A separate route: the version answer already exists, is public and is never cached.

## Consequences

- The field is a contract with installed builds and cannot be removed while any build reads it.
- Staging names neither setting, so it serves 0 once `dev` is promoted. Until then `dev` has no `minimum_app` at all, and the app reads that as a failed read, which changes nothing.
- The next deploy puts a minimum raised by hand on the service back to the deploy file's value.
- There is no migration.
