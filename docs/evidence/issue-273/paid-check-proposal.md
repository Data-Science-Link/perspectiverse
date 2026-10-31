# Paid check, not built

The free self-check already names the failing planets and the stage that should have stopped them. On the Oct 19 snapshot that is 20 planets: 17 labeling, 3 ingest. No paid Jev call and no section relabel was run for this check.

Jev's published price in `pipeline/costs.py` is $0.042 per million input tokens (dated 2026-10-08). This proposal did not send a prompt, so there is no measured token count and no measured dollar cost for a second pass. The daily pipeline budget is about $0.25 to $0.30, and the morning loop already spends that on labeling. A second model opinion on the 20 failures would be another labeling bill for planets the free report already points at `labeling`. It is not worth adding until that stage count drops and the remaining failures are ones a free signal cannot see.
