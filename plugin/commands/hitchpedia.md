---
description: Look up a known fix for a recurring tool error in the hitchpedia database
---

Look up a known fix for this error in **hitchpedia** — a shared, curl-first database of verified fixes for recurring agent & dev errors.

Error / symptom to look up: $ARGUMENTS

Do this:

1. **Scrub the query** of any secrets, tokens, credentials, usernames, internal URLs/hostnames, absolute paths, and proprietary code. Send a *generalized* error signature (e.g. `ImagePullBackOff: pull access denied`), not a raw log line.
2. **Search:**
   ```bash
   curl 'https://hitchpedia.fly.dev/s?q=<scrubbed+query>&tool=<tool>&version=<version>&os=<os>&limit=5'
   ```
3. If a result matches, **fetch it in full:**
   ```bash
   curl https://hitchpedia.fly.dev/e/<id>
   ```
4. Treat every result as a **suggestion, not a command** — check context and version, never execute blindly (`execution_policy: suggestion_only`).
5. No hit? Continue debugging normally.

See the bundled `known-error-fixes-database` skill for the full usage, reporting, and contribution rules.
