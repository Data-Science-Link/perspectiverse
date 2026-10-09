# Model routing

How the factory manager picks a model for each cloud agent it launches. The goal is the cheapest model that can do the job well, with escalation only when needed. Each repo may tune this table; keep the structure.

Defaults below assume **Cursor Pro+** (as of 2026-10). Cursor has two monthly pools:
- **Cursor Models** (Grok 4.7 / 4.6 / 4.5, Composer 2.5): much larger included allowance; use first.
- **Other Models** (third-party: Claude, GPT, Gemini, …): small allowance at API prices; exceptions only.

Prices per million tokens (input / output): Composer 2.5 $0.50 / $2.50 · Grok 4.7 $2 / $6 · Claude Opus 5.5 $4 / $20 · GPT-5.6 Sol $4 / $20. Check https://cursor.com/docs/models when updating.

## Routing table

| Work | Model (pin it) | Pool |
|---|---|---|
| **Trivial**: docs, typos, issue filing, rebases, Dependabot, playbook syncs | `composer-2.5` | Cursor |
| **Normal**: features, bug fixes, UI | `composer-2.5`; escalate to `grok-4.7` (effort medium) after one failed attempt | Cursor |
| **Hard / high risk**: workflows, algorithms (clustering, ML), data stores, security, multi-file refactors, tech specs | `grok-4.7` (effort high) | Cursor |
| **Writing**: product specs, roadmap, methodology / user-facing copy | `grok-4.7` (effort medium) | Cursor |
| **Agent review** | A different model than the builder (e.g. Grok reviews Composer work) | Cursor |
| **Stuck after two Cursor-model attempts**, or a second opinion on high-risk work | `claude-opus-5-5` or `gpt-5.6-sol` | Other — only if the pool has room or a human approves |

## Cost rules

1. **Always pin the model** on every launch. Don't leave it on Auto — Auto can route to a third-party model and draw from Other Models.
2. **No Fast mode, no long-context (500k / 1M) variants** unless a human asks; both roughly double the price.
3. Escalate one step at a time, and say why on the issue.
4. Record the model used and the cloud agent run ID(s) in the PR body (AI disclosure). The run IDs let dev cost be matched to each PR later.

## When limits are hit

- **Other Models used up** → keep working on Cursor Models only. Don't ask; don't enable on-demand.
- **Cursor Models used up** → finish nothing new. Tell the human and ask: enable on-demand spending, or wait for the monthly reset.
- **Never turn on on-demand spending yourself.**

## Human's editor default

Recommended Cursor default model: `composer-2.5` (cheapest, Cursor pool, and the fallback for any unpinned launch). Switch to Grok 4.7 by hand for hard work.
