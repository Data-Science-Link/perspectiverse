# Model routing

How the factory manager picks a model for each cloud agent it launches. The goal is the cheapest model that can do the job well, with escalation only when needed. Each repo may tune this table; keep the structure.

Defaults below assume **Cursor Pro+** (as of 2026-10). Cursor has two monthly pools:
- **Cursor Models** (Grok 4.7 / 4.6 / 4.5, Composer 2.5): much larger included allowance; use first.
- **Other Models** (third-party: Claude, GPT, Gemini, …): small allowance at API prices; exceptions only.

Prices per million tokens (input / output): Composer 2.5 $0.50 / $2.50 · Grok 4.7 $2 / $6 · Claude Opus 5.5 $4 / $20 · GPT-5.6 Sol $4 / $20. Check https://cursor.com/docs/models when updating.

## Routing table

| Work | Model (pin it) | Pool |
|---|---|---|
| **Simple**: docs, typos, issue filing, rebases, Dependabot, playbook syncs | `composer-2.5` | Cursor |
| **Standard**: features, bug fixes, UI | `composer-2.5`; escalate to `grok-4.7` (effort medium) after one failed attempt | Cursor |
| **Complex**: workflows, algorithms (clustering, ML), data stores, security, multi-file refactors, tech specs | `grok-4.7` (effort high) | Cursor |
| **Writing**: product specs, roadmap, methodology / user-facing copy | `grok-4.7` (effort medium) | Cursor |
| **Agent review** | A different model than the builder (e.g. Grok reviews Composer work) | Cursor |
| **Stuck after two Cursor-model attempts**, or a second opinion on high-risk work | `claude-opus-5-5` or `gpt-5.6-sol` | Other — only if the pool has room or a human approves |

## Cost rules

0. **Rate complexity first.** Every issue gets a triage line on the issue and in the PR body (`Complexity: simple|standard|complex — reason; Risk: …; Model: …`) before any launch. Complexity words are separate from risk class (trivial/normal/high), which sets the merge gate. When in doubt between standard and complex, pick complex (`grok-4.7`): a failed cheap attempt costs more than the difference.
1. **Always pin the model** on every launch. Don't leave it on Auto — Auto can route to a third-party model and draw from Other Models.
2. **No Fast mode, no long-context (500k / 1M) variants** unless a human asks; both roughly double the price.
3. Escalate one step at a time, and say why on the issue. A failed agent review counts as a failed attempt. The next round moves one step up this table for the task's complexity and type of work (e.g. Standard: `composer-2.5` to `grok-4.7` medium; Complex: raise effort or reach the Stuck row). `grok-4.7` is one allowed step, not the automatic one, and routing is never just a choice between `composer-2.5` and `grok-4.7`.
4. Record the model used and the cloud agent run ID(s) in the PR body (AI disclosure). The run IDs let dev cost be matched to each PR later. A cloud agent's token can't comment, so the manager posts that agent's review and report.

## When limits are hit

- **Other Models used up** → keep working on Cursor Models only. Don't ask; don't enable on-demand.
- **Cursor Models used up** → finish nothing new. Tell the human and ask: enable on-demand spending, wait for the monthly reset, or run ready issues himself on the local fallback below.
- **Never turn on on-demand spending yourself.**
- **At most 4 cloud agents running at once.** When usage stops a run, comment a restart note on its issue (agent ID, model, head SHA, what was left) so it can be relaunched cleanly.

## Outside coding agents (not Cursor)

- Approved: the **local fallback** below (desktop Cursor + DeepInfra), per Michael's 2026-10-27 ask (DECISIONS 2026-10-27). Any other agent: before first use, Michael gives an explicit cost OK, and the agent, model and expected cost are logged in `DECISIONS.md` and in the routing table above.
- They run the same loop as Cursor agents: triage line, review by a different model, verify (CI and evidence), and the human gate for normal/high work. Record the tool, model and run ID in the PR's AI disclosure.

## Local fallback (desktop Cursor + DeepInfra)

When Cursor usage runs out, Michael can run a ready issue himself in **desktop Cursor** with his own DeepInfra key, using the model in the issue's handoff block. Steps: `FACTORY.md` → Local fallback run. Same loop, agent review, CI and human gates as cloud runs.

**Setup (once).** Per [Cursor help: bring your own API key](https://cursor.com/help/models-and-usage/api-keys) (checked 2026-10-27): in Cursor Settings → Models, put the DeepInfra key in the OpenAI API key field and turn it on, turn on the OpenAI base-URL override with `https://api.deepinfra.com/v1/openai`, and add each model ID below as a custom model (name must match the ID exactly). While the override is on, Cursor's own OpenAI-family models also go to DeepInfra; turn it off to go back. Own keys work only in desktop Chat and Agent, not cloud agents or Auto. Menu names change; follow Cursor's current page if it differs.

**The key is never committed** — local Cursor settings or env only; never in the repo, an issue, a PR, a workflow or chat.

| Tier | Routing row | DeepInfra model ID (pin it) | Price / 1M tokens (in / out) |
|---|---|---|---|
| **S** — small fix | Simple | `deepseek-ai/DeepSeek-V4-Flash` | $0.09 / $0.18 |
| **M** — normal code | Standard | `Qwen/Qwen3-Coder-480B-A35B-Instruct-Turbo` | $0.30 / $1.00 |
| **L** — high-risk or complex code, specs, user-facing copy | Complex, Writing | `deepseek-ai/DeepSeek-V4-Pro` | $1.30 / $2.60 |
| **Agent review** | Agent review | `moonshotai/Kimi-K2.6` (a different model than the builder) | $0.75 / $3.50 |

Checked 2026-10-27 on the DeepInfra model pages (https://deepinfra.com/models) and https://api.deepinfra.com/v1/openai/models. Recheck IDs and prices every 3 months. High-risk work and specs always use the **L** row, never a cheaper one. No priority or long-context tiers unless Michael asks.

## Human's editor default

Recommended Cursor default model: `composer-2.5` (cheapest, Cursor pool, and the fallback for any unpinned launch). Switch to Grok 4.7 by hand for hard work.
