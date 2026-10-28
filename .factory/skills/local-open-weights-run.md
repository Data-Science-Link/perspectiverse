# Skill: local-open-weights-run

**If you are a local agent running this issue, use the Local open-weights model from the issue's handoff block. Cloud agents never use this file.**

Use when Cursor usage runs out and Michael works a ready issue himself in desktop Cursor (or another local harness on his machine) with his own open-weights provider key. Default provider: DeepInfra. Setup, model IDs and prices: `MODEL_ROUTING.md` → Local open-weights harness. The key stays in local settings only; never commit, paste or log it.

**Status:** Michael chose (b) docs only for now, 2026-10-27; Local open-weights runs are not turned on, no DeepInfra spend approved. Don't start a local run until Michael gives an explicit cost OK (expected cost per issue, monthly cap) and it is recorded in `DECISIONS.md`.

**Model:** default `Qwen/Qwen3-Coder-480B-A35B-Instruct-Turbo` (a non-thinking coder model). Other models in `MODEL_ROUTING.md` are marked *Needs test*; use one only after a short local test with thinking off passes. Keep the handoff prompt first and unchanged, don't switch models, rules or tools mid-run, and start a new chat at about 60-70% of context (`MODEL_ROUTING.md` → Caching and context).

## Per issue

1. Open the repo in desktop Cursor and pick the Local open-weights model the issue's handoff block names (DeepInfra by default).
2. Say "do issue #N" (or paste the handoff prompt).
3. The agent syncs to latest `main`, branches, and opens a PR linked to the issue; the PR's AI disclosure names the harness (local Cursor + DeepInfra) and model ID.
4. Agent review (different model), CI, evidence and the human gates apply unchanged. The DeepInfra key stays in local Cursor settings only.
