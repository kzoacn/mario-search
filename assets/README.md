# Demo GIFs

These three GIFs are converted from the independently verified recordings used
in the published benchmark. They show the complete successful action sequence,
at 2× playback speed and 12 FPS. The video's outer title bar is cropped; the
gameplay area and in-game HUD are retained.

| GIF | Level | Search time | Route length |
|---|---|---:|---:|
| `world-1-1.gif` | 1-1 | 13.86 seconds | See `benchmarks/routes/1-1.json` |
| `world-1-4.gif` | 1-4 | 9.49 seconds | See `benchmarks/routes/1-4.json` |
| `world-2-2.gif` | 2-2 | 199.36 seconds | See `benchmarks/routes/2-2.json` |

`demos.json` records the GIF and original video SHA-256 hashes and conversion
settings. Source game footage was 60 FPS; every original route was replayed in
the reference `nes-py` emulator and checked against its final native game state.

Regenerate a full-speed MP4 with:

```bash
mario-search replay --route benchmarks/routes/1-1.json --output runs/demo
```

The repository does not include the ROM. Mario graphics are Nintendo's assets.
