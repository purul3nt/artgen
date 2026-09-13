# artgen — agent guide

This repo holds short looping character animations generated with MiniMax H3
(first-frame + last-frame image-to-video). Each clip is built by:

1. A source keyframe image (PNG / JPG) — the character in an idle pose.
2. Reusing the same keyframe as the **last_frame** so the clip loops seamlessly.
3. A prompt describing the in-between motion and audio.

## Project layout

```
artgen/
├── AGENTS.md                       # this file
├── README.md                       # public-facing description
├── warrior_idle_grin.jpg           # current source keyframe (2K, 1:1)
├── odysseus_sip_loop.mp4           # idle -> raise goblet -> sip -> idle (5s, 2K)
└── odysseus_cheers_loop.mp4        # idle -> big grin -> toast -> idle (5s, 2K)
```

## The character (Odysseus)

- Muscular Greek warrior (Odysseus / Dionysus flavour)
- Long blonde hair, laurel wreath crown with red leaves
- Flowing crimson cape with gold Greek-key trim
- Gold and dark red armor, lion-head belt buckle, golden greaves
- Black-and-gold arm bracers, bare muscular chest
- Leaning against a wooden wine barrel with a bunch of purple grapes

When prompting H3 (or H3-Max), re-state these attributes so the model keeps the
character consistent across generations.

## Generation conventions

- **Model**: `MiniMax-H3` for quality (account credits, ~15-30 min per clip).
  Use `MiniMax-H3-Max` only when speed matters (~20 s, 480P/768P).
- **Duration**: 5 s (matches a clean single motion cycle).
- **Resolution**: `2K` for H3.
- **Aspect ratio**: `1:1` (matches the source keyframe).
- **Keyframe mode**: `input_image` = idle source; `last_frame_image` = same idle
  source; the prompt describes only the in-between motion.
- **Audio**: included in the H3 prompt (ambient, vocal, sfx). Output is
  `.mp4` with native audio track.

## Tool surface (Mavis side)

- `mcode-tools connector tools --keyword image` -> find `generate_image`
- `mcode-tools connector tools --keyword query` -> find `query_video_generation`
- `mcode-tools upload_temp_url <local_path>` -> get an HTTPS temp URL for a
  local file before passing it as `input_image` / `last_frame_image`
- `mcode-tools get_asset_url <node_id>` -> turn a generated image's `node_id`
  into a short-lived HTTPS URL

## Workflow when generating a new loop

1. Decide the motion (raise/lower/cheers/sip/etc.). The first and last frame
   must remain identical for a clean loop.
2. Write a prompt that:
   - re-states the character attributes (so the model doesn't drift),
   - describes the in-between motion precisely (which arm moves, where the
     goblet goes, what the face does, where the camera is),
   - mentions the audio you want (H3 renders a native audio track).
3. Upload the source keyframe to a temp URL.
4. Call `submit_video_generation` with `input_image` and `last_frame_image`
   both pointing at the temp URL, duration 5, model H3, resolution 2K.
5. Poll with `query_video_generation` every 1-2 min; H3 typically finishes in
   15-30 min. Don't block the user — set up a cron self poll.
6. Download the resulting `video_url` and commit it into this repo.

## When the user switches devices

The repo is pushed to GitHub: `github.com/purul3nt/artgen` (public). The user
can `git clone` it on any device. Pulling in this workspace before starting
work keeps the project in sync.
