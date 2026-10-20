# 287 — fragment attach replay

Guards off. No Jev, no section labeling, no workflow dispatch.

`scripts/replay_287_fragments.py` runs `attach_same_story` on representative posts. The size gate uses `post_count`. A fold is counted only when the allowlisted short subject (`ai`) joins two fragments that today's gates leave apart.

`oct19-pairs-labeled.csv` is the #275 yardstick (copied from the draft on `cursor/root-cause-duplicates-3988`). `is_duplicate` on Oct 20 joins is empty for a separate grok-4.7 labeler.
