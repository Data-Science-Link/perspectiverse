# Oct 19 blind pair sheet

`oct19-pairs.csv` is the yardstick for issue #275. It was cut from the published Oct 19 edition (`data-snapshot` `44a537b`, `last_updated` 2026-10-19, 100,000 posts) before any method change was proposed.

`is_duplicate` is empty on every row. A reviewer on a different model fills that column without using the grouping code. Those labels are the before/after measure. A similarity score is not a column here, so the sheet does not grade itself.

Each row is either two planets in one solar system or two faces. Sample texts are up to three representative posts from the edition file. Rebuild with:

```bash
python scripts/replay_275_oct19.py --edition /path/to/data_2026-10-19.json
```

The script does not call Jev or a label model and does not dispatch a workflow.
