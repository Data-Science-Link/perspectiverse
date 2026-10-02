# Data Sources

## Bluesky

`extract_bluesky.py` pulls an English sample. The public job searches neutral tokens over a rolling 7 days, then only the newest day. `--query` still passes operator terms through `extract_posts`.

- No secrets: public AppView search at `https://api.bsky.app` (often HTTP 403 from Actions/cloud IPs).
- Required for the daily job: `BLUESKY_HANDLE` and `BLUESKY_APP_PASSWORD` (app password) so `_fetch_authenticated` logs in via `atproto`.

Cleaned rows go to `pipeline/data/live_corpus.db`. The daily job syncs that file with private R2 when the `R2_*` secrets are set. See `pipeline/README.md` for the full live command.
