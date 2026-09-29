# Data Sources

## Bluesky

`extract_bluesky.py` pulls a small English sample from the last 168 hours.

- No secrets: public AppView search at `https://api.bsky.app` (often HTTP 403 from Actions/cloud IPs).
- Required for the daily job: `BLUESKY_HANDLE` and `BLUESKY_APP_PASSWORD` (app password) so `_fetch_authenticated` logs in via `atproto`.

Cleaned rows go to `pipeline/data/live_corpus.db`. See `pipeline/README.md` for the full live command.
