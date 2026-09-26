# Data Sources

## Bluesky

`extract_bluesky.py` pulls a small English sample from the last 168 hours.

- No secrets: public AppView search at `https://api.bsky.app`.
- Optional: `BLUESKY_HANDLE` and `BLUESKY_APP_PASSWORD` use the `atproto` client.

Cleaned rows go to `pipeline/data/posts.db`. That directory is gitignored. See `pipeline/README.md` for the full live command.
