# Handoff: DeepInfra labels + Bluesky app login

**Status (2026-09-29):** Code wiring landed on `cursor/bluesky-deepinfra-b667`. `api.deepinfra.com` is allow-listed, `OPENAI_BASE_URL` is forwarded in `pipeline.yml`, `atproto` is installed on the daily job, and `--relabel` rebuilds names from `live_corpus.db` without Bluesky. Secrets were **not** present in that agent run, so the 1,000-post snapshot is still heuristic. Human steps below are still required.

Copy the prompt in the next section into a **new cloud-agent run** only if you still need someone to *use* the secrets after they exist (live fetch + DeepInfra relabel of the saved 1,000). Do not redo the allow-list / workflow work.

Related: [Pipeline Audit 2026-09-28](Pipeline%20Audit%202026-09-28.md), [PR #22](https://github.com/Data-Science-Link/perspectiverse/pull/22), branch `cursor/live-bluesky-corpus-5215`.

---

## Prompt to paste

```text
You are continuing Perspectiverse (github.com/Data-Science-Link/perspectiverse).

GOAL
Wire two things that the live 1,000-post snapshot still lacks:
1) Bluesky authenticated search (app password) so GitHub Actions can fetch new posts instead of 403ing.
2) DeepInfra as the OpenAI-compatible LLM for planet names, face titles, and steelman arguments.

Do NOT start from main. Continue PR #22 / branch cursor/live-bluesky-corpus-5215 (or branch from it if that PR already merged). Do not rebuild the 3D app. Do not throw away pipeline/data/live_corpus.db. Relabel the existing 1,000 when DeepInfra works; do not refetch Bluesky just to rename planets.

HELP THE HUMAN ALONG
Michael (linkmichaelj@gmail.com) is in the loop. Pause and tell him exactly which click to make before you need a secret. Never print a secret back. Never commit .env or tokens. If a secret is missing, stop that path and walk him through creating it — do not stall the whole PR on both secrets if one is ready.

============================================================
PART A — Bluesky 403 / app password (why + what to do)
============================================================

What happened:
- Public search is anonymous GET to app.bsky.feed.searchPosts.
- public.api.bsky.app (CDN) 403s from many cloud/datacenter IPs.
- api.bsky.app 403s from GitHub Actions (datacenter). From the previous Cursor VM it returned 200 on first pages, then 403 on heavy pagination (rate limit).
- The previous agent still got 1,000 posts because that VM was not Actions: first page of many queries (nfl, ukraine, chatgpt, …), spam filter, merge into SQLite. That will not reliably work on the daily Actions runner.

What an account does:
- BLUESKY_HANDLE + BLUESKY_APP_PASSWORD (an app password, NEVER the account password) logs in via atproto and searches as a user. Higher trust/quota; often works from IPs that anonymous GET cannot use.
- Code already exists: pipeline/data_sources/extract_bluesky.py _fetch_authenticated. Daily job already forwards the secrets in .github/workflows/pipeline.yml. They were empty, so it used public search and 403d.

Walk Michael through this, in order:
1. Open https://bsky.app/settings/app-passwords (must be logged into the account you want the job to use).
2. Create an app password. Name it something like "perspectiverse-pipeline". Copy it once.
3. Note the full handle (e.g. something.bsky.social).
4. Add GitHub Actions secrets on https://github.com/Data-Science-Link/perspectiverse/settings/secrets/actions
   - BLUESKY_HANDLE
   - BLUESKY_APP_PASSWORD
5. Optional for local/cloud-agent live fetches: same two values in a gitignored .env (see .env.example). Also add them as Cursor cloud-agent environment secrets for THIS Perspectiverse environment if you want agents to fetch; secrets from another project do not carry over.

Then: run --live once with auth (keep the existing sqlite; it should rotate ~1/7 and add new posts, not wipe the 1,000). Confirm logs are not "HTTP 403". If fetch still 403s, report the host and whether login succeeded.

The job must keep this property: if Bluesky fails, do NOT shrink the retained corpus; rebuild data.json from the saved 1,000.

============================================================
PART B — DeepInfra (labels / synthesis)
============================================================

Not required for ingest. Only for nicer names than heuristic term-bags (Learning, Llm, Chatgpt Intelligence Artificial).

Code today:
- pipeline/label.py: auto → Ollama, else OPENAI_API_KEY, else heuristic.
- _openai_generate already uses OPENAI_BASE_URL (default https://api.openai.com/v1).
- BLOCKER: pipeline/http_json.py allow-list is only api.openai.com. DeepInfra (api.deepinfra.com) will be refused until you add that host.
- BLOCKER: .github/workflows/pipeline.yml forwards OPENAI_API_KEY and OPENAI_MODEL but NOT OPENAI_BASE_URL. Add it.

Walk Michael through this:
1. Open https://deepinfra.com/dash (API keys / dashboard). Create or copy an API token.
2. GitHub Actions secrets:
   - OPENAI_API_KEY = the DeepInfra token (reuse the existing secret name; the client is OpenAI-compatible)
   - OPENAI_BASE_URL = https://api.deepinfra.com/v1/openai
   - OPENAI_MODEL = meta-llama/Llama-3.3-70B-Instruct-Turbo
     (good/cheap default. Alternatives: deepseek-ai/DeepSeek-V4-Flash, or Qwen/Qwen3.5-9B if he wants cheaper/faster. Llama 3.1 8B Turbo is cheapest but JSON is flakier.)
3. Same three in gitignored .env and, if he wants this agent to relabel now, as Cursor cloud-agent secrets for THIS environment.
4. Previous run checked this VM, this Cursor environment, and GitHub secret list: no DeepInfra token was injected. A token stored for another project will not appear here until he adds it.

Cost (DeepInfra list prices, ~50 short JSON calls per snapshot, ~45k in / ~11k out):
- Llama 3.3 70B Turbo ($0.10 / $0.32 per 1M): ~$0.01 per snapshot, ~$0.30/month daily
- DeepSeek-V4-Flash ($0.09 / $0.18): similar
- 8B Turbo: fractions of a cent
Even with retries this stays cents/month, not dollars.

Agent work after secrets exist:
- Allow-list api.deepinfra.com (and keep api.openai.com).
- Forward OPENAI_BASE_URL in pipeline.yml.
- Update .env.example comments for DeepInfra.
- Tests: allow-list accepts deepinfra; a mocked generate still works; do not put real tokens in tests.
- Relabel using the existing sqlite (export posts → run live with fixture or add a --relabel path). Do not require a Bluesky refetch to update titles.
- Confirm public/data.json still validates, mode=live, ~10 planets, arguments look like steelmans not Untitled cluster.
- If the key is not in THIS run's env, do the code wiring anyway and tell Michael the one-line local command to relabel once .env exists:
  python -m pipeline.run_pipeline --live --fixture <exported corpus json> --db pipeline/data/live_corpus.db
  (or equivalent that does not wipe the db on failure)

============================================================
DONE WHEN
============================================================
- Allow-list + workflow env wired for DeepInfra even if the token is not present yet.
- README/pipeline README says how to use DeepInfra via OPENAI_* vars.
- If Bluesky secrets are present in this run: a live fetch succeeds without 403.
- If DeepInfra secrets are present in this run: one relabel of the 1,000 produces better planet/face copy; commit the new data.json.
- If a secret is missing: PR still has the wiring; a short "what Michael still needs to click" section in the PR body.
- Do not commit secrets. Do not expand scope to firehose, chat clerk, or BERTopic-on-Actions.
```
