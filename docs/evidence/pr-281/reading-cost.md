# Reading-screen cost (#270)

Planet held open for 30 seconds. Pixel 7 viewport (412×915), Playwright Chromium, SwiftShader, CDP CPU throttle 4×. Draws are `drawArrays` / `drawElements` (including instanced) on the observatory canvas. Frames are animation frames in which that canvas issued at least one draw.

SwiftShader does not expose a GPU-process memory counter. Texture bytes are live `texStorage2D` / `texImage2D` allocations still bound to that context. The drawing buffer is `width × height × 4`.

| Build | Canvas while reading | Frames/s | WebGL draws/s | JS heap max | JS heap end | Textures live | Drawing buffer |
| --- | --- | --- | --- | --- | --- | --- | --- |
| main `b6340b3` | destroyed | 0 | 0 | 15.8 MB | 8.0 MB | 0 | 0 |
| branch before pause | mounted, still drawing | 60.0 | 289 | 16.1 MB | 9.8 MB | 1.94 MB | 1.43 MB |
| this branch | mounted, `frameloop="never"` | 0 | 0 | 13.5 MB | 9.3 MB | 1.94 MB | 1.43 MB |

The hidden canvas on the branch was rendering every frame (60 frames/s, 289 draws/s) until the phone reading screen set `frameloop` to `never`. After that, the 30s window issued 0 draws and 0 frames. The context stays allocated, so backing out keeps the same canvas and drawing resumes on the next second (1,865 draws, center pixel luminance 211). Main still destroys the canvas and creates a new one on the way back.

No other canvas (including the reading-screen cubes) issued a draw during these windows. JS heap is `performance.memory.usedJSHeapSize`. It did not climb across the 30s. CDP `JSHeapUsedSize` max was 12.4 MB on main, 12.7 MB before the pause, and 10.2 MB on this branch.
