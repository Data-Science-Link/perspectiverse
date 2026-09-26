# Data Engineering Pipeline

This directory will hold the daily Discourse Universe job: ingest a 7-day window of posts, cluster them into 10 topics and 6 faces, label the faces, and write `public/data.json`.

That live path is not implemented yet. The orchestrator currently emits a schema-compatible **demo** universe so the frontend can ship first.

## Current workflow

```bash
python -m pipeline.run_pipeline
```

or:

```bash
python pipeline/run_pipeline.py
```

Both rewrite `public/data.json` from `generate_demo_data.py`.

## Intended later workflow

1. **Extraction** — pull a 7-day English sample (Bluesky, later others) into `data/`.
2. **Sorting** — BERTopic for 10 planets, then 6 faces per planet.
3. **Explaining** — local Ollama (or an API LLM) writes titles and one-sentence summaries.
4. **Output** — overwrite `public/data.json` with the same schema the React app already consumes.

## Structure

- `generate_demo_data.py`: demo payload and validator
- `run_pipeline.py`: entry point
- `config/`: future YAML and model settings
- `scripts/`: future orchestration helpers
- `data_sources/`: per-source extractors
- `data/`: local raw and intermediate files (gitignored)
