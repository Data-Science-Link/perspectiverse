# Issue #104 embedding comparison

Local ONNX comparison of the PR #114 grouping (`density_labels`, author cap 3, `attach_same_story`) on the saved 9,832-post corpus. Production code is not modified. No hosted embedding calls.

- Findings: [RESULTS.md](RESULTS.md)
- Runner: `run_embedding_models.py`
- Vendored attach step (byte-for-byte from PR #114, `af19da9`): `vendor/story_attach.py`
- Metrics and the sampled posts used for the coherence read: `out/*.json`, `out/*.samples.json`

The corpus database and the embedding caches stay outside the repo (`/tmp/issue104/`). Re-running needs that database, the story reference at commit `28c93de9cfb7f43ba46fb3ecf94bb588fdde869c`, and `fastembed` 0.9.

```bash
python3 research/issue-104/run_embedding_models.py --models minilm bge-small bge-base gte-base nomic
```

MiniLM keeps the stock gates. Every other model is retuned to the same rank in the raw k-means cell distributions on posts that are not in the story reference. The reference is scored only after the gates are locked.
