# Odysseus animation loops

5-second looping character animations generated with MiniMax H3 (first/last frame = same idle image, so each clip loops seamlessly).

## Files

| File | Description |
| --- | --- |
| `odysseus_sip_loop.mp4` | Idle -> raises goblet -> takes a sip -> lowers goblet -> idle. Calm tavern ambience, soft goblet clink. |
| `odysseus_cheers_loop.mp4` | Idle -> big grin -> raises goblet in a celebratory toast -> cheers -> lowers goblet -> idle. Tavern ambience with an enthusiastic "Cheers!" vocal and goblet clink. |
| `warrior_idle_grin.jpg` | Source 2K idle keyframe used as both first and last frame for both loops. |

## Character

Muscular Greek warrior inspired by Odysseus / Dionysus imagery - flowing crimson cape with gold Greek-key trim, gold and dark red armor, lion-head belt buckle, golden greaves, black-and-gold arm bracers, laurel wreath crown with red leaves. Leaning against a wooden wine barrel with a bunch of purple grapes.

## Specs

- Resolution: 2K (H3)
- Duration: 5 seconds
- Aspect: 1:1
- Model: MiniMax-H3 (first/last-frame image-to-video)
- Audio: native H3 audio track per clip

## How to use

Drop the mp4s into a web `<video loop autoplay muted playsinline>` block for a clean infinite loop, or import into After Effects / DaVinci for further work.

To clone on another device:

```
git clone https://github.com/purul3nt/artgen.git
```
