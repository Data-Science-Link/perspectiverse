# Phone motion and back-out (#270)

Pixel 7 viewport (412×915), Playwright Chromium (swiftshader), CDP CPU throttle 4×. Frame times are from isolated runs. Dropped frames are frame gaps over 32ms. The stop-start Michael described is the label still-gap: how long a moving orbit pill sits still before it jumps.

| Build | Idle p50 | Idle p95 | Longest idle | Dropped idle | Move p50 | Move p95 | Longest move | Dropped move | Label still-gap p50 | Label still-gap max | Back-out canvas |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `53242b1^` before #234 | 16.7ms | 16.8ms | 16.8ms | 0 | 16.7ms | 16.8ms | 16.8ms | 0 | 206ms | 220ms | destroyed, then a new cleared canvas |
| `53242b1` before #265 | 16.7ms | 16.7ms | 16.8ms | 0 | 16.7ms | 16.7ms | 16.8ms | 0 | 205ms | 220ms | destroyed, then a new cleared canvas |
| main `b6340b3` | 16.7ms | 16.7ms | 16.8ms | 0 | 16.7ms | 16.7ms | 16.8ms | 0 | 211ms | 221ms | destroyed, then a new cleared canvas |
| this branch | 16.7ms | 16.8ms | 16.8ms | 0 | 16.7ms | 16.8ms | 16.8ms | 0 | 56ms | 71ms | same canvas, 0 missing frames |

The 220ms still-gap is `LABEL_HOLD_MS`, added in `ea3de96` and merged in #252 (`831d218`). #234 and #265 did not add it. Frame time stays on vsync the whole way, so this was not a low frame rate.

The black frame is the phone drill unmounting the observatory, in place since `1b25e6b`. It is already there at `53242b1^`. #234 restores the camera after the new canvas boots, which reads as a black flash and then a reload into the right zoom.

Screenshots: `main-back-00.png` is the blank frame on main. `branch-back-01.png` is the first solar frame on this branch, with the same canvas still attached. Videos are the `*.webm` files in this folder.
