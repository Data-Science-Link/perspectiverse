# Skill: local-open-weights-run

**If you are a local agent running this issue, use the Local open-weights model from the issue's handoff block. Cloud agents never use this file.**

Use when Cursor usage runs out and Michael works a ready issue himself in desktop Cursor (or another local harness on his machine) with his own open-weights provider key. Default provider: DeepInfra. Setup, model IDs and prices: `MODEL_ROUTING.md` → Local open-weights harness. The key stays in local settings only; never commit, paste or log it.

**Status:** pending Michael's (a)/(b) choice: an explicit cost OK (expected cost per issue, monthly cap) and whether a local run is allowed during the coding pause (DECISIONS 2026-10-27). Don't start a local run until both are recorded there.

## Per issue

1. Open the repo in desktop Cursor and pick the Local open-weights model the issue's handoff block names (DeepInfra by default).
2. Say "do issue #N" (or paste the handoff prompt).
3. The agent syncs to latest `main`, branches, and opens a PR linked to the issue; the PR's AI disclosure names the harness (local Cursor + DeepInfra) and model ID.
4. Agent review (different model), CI, evidence and the human gates apply unchanged. The DeepInfra key stays in local Cursor settings only.
