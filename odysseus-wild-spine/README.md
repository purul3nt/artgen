# Odysseus Taverna — Spine slot symbols

This folder has Spine 4.3 rigs for two slot symbols, built straight from the AI
sprite sheets in `foranimation/` without the Spine editor. Both play in PixiJS
through the official `spine-pixi-v8` runtime.

| Symbol | Source sheet | Assets |
| --- | --- | --- |
| WILD (Odysseus) | `ChatGPT Image Sep 14, 2026, 04_50_17 PM.png` | `assets/odysseus_wild.*` |
| BONUS (wine hostess) | `ChatGPT Image Sep 14, 2026, 04_50_24 PM.png` | `assets/odysseus_bonus.*` |

## Preview it

From the repository root:

```bash
python -m http.server 4180 --directory odysseus-wild-spine
```

Open <http://localhost:4180>. Pick WILD or BONUS in the panel; open
<http://localhost:4180/#bonus> to start on BONUS.

- Keys `1` / `2` / `3` switch Idle / Land / Connect.
- The panel also has speed, looping Connect, bone debug and a 3×3 reel grid.
- A spin demo plays too: columns land one after another, then the middle row connects.

The page needs a local server (not `file://`) because Pixi fetches the atlas and
JSON.

## Files

| File | What it is |
| --- | --- |
| `assets/odysseus_<symbol>.json` | Skeleton, skin, physics constraints, animations, events |
| `assets/odysseus_<symbol>.atlas` | Atlas descriptor (straight alpha, `pma:false`) |
| `assets/odysseus_<symbol>.png` | 2048×1024 atlas page |
| `tools/spine_rig.py` | Shared toolkit: cutting, atlas packing, Spine JSON writer, easing helpers, debug renders |
| `tools/build_wild.py`, `tools/build_bonus.py` | One script per symbol: part list, placement, animations |
| `vendor/` | Pinned `pixi.js 8.20.1` and `spine-pixi-v8 4.3.13` browser builds |

## Animations

Both symbols use the same three names, so game code can treat them the same.
Each fires `impact` (0.12 s) and `settled` (0.8 s) during `land`, and `cheer`
during `connect`. `connect` starts and ends on the idle pose, so it loops
cleanly.

### WILD

| Name | Length | What happens |
| --- | --- | --- |
| `idle` | 3.2 s loop | Breathing, head bob, laurel sway, back glow pulse, banner glint, medallion twinkle |
| `land` | 0.9 s | Drops in, squash + rebound, snarl → roar → grin, red flame burst, laurels flare |
| `connect` | 1.8 s | Pops to 112%, belly laugh (roar head bouncing), gold swirls, rays, sparkles, double banner shine |

The laurels and the cape over his left shoulder use Spine physics. The cape also
hides the diagonal crop line of the generated head art, and it's parented to the
head so it keeps covering that line during head shakes.

### BONUS

| Name | Length | What happens |
| --- | --- | --- |
| `idle` | 3.6 s loop | Breathing and sway, goblet swirl, magenta back glow, banner glint, pink/gold twinkles |
| `land` | 0.9 s | Drops in, squash + rebound, closed-eye giggle, goblet jolt with a wine splash, laurels flare |
| `connect` | 1.9 s | "Cheers!": goblet dips then raises in a toast, two wine splashes, giggle bounce, wink, pink swirls, rays, sparkles, double banner shine |

Expressions are whole-bust swaps (smile / laugh / wink). The three busts were
registered against each other on the sheet, so swapping doesn't make the face
jump. The laurels and goblet use Spine physics.

## Using it in a game

```js
import { Assets } from "pixi.js";
import { Spine } from "@esotericsoftware/spine-pixi-v8";

Assets.add({ alias: "bonusSkeleton", src: "odysseus_bonus.json" });
Assets.add({ alias: "bonusAtlas", src: "odysseus_bonus.atlas" });
await Assets.load(["bonusSkeleton", "bonusAtlas"]);

const bonus = Spine.from({ skeleton: "bonusSkeleton", atlas: "bonusAtlas" });
bonus.state.data.defaultMix = 0.12;
bonus.state.setAnimation(0, "idle", true);

// reel stops on the symbol
bonus.state.setAnimation(0, "land", false);
bonus.state.addAnimation(0, "idle", true, 0);

// winning line
bonus.state.setAnimation(0, "connect", false);
bonus.state.addAnimation(0, "idle", true, 0);

bonus.state.addListener({ event: (_, e) => sfx.play(e.data.name) }); // impact / cheer / settled
```

The skeleton origin is the centre of the symbol. The design size is about
380×390 (520×500 including effects), so scale it to your reel cell with
`symbol.scale.set(cellSize / 400)`.

Spine runtimes are covered by the Spine Runtimes License. Shipping them in a
commercial game requires a Spine Editor licence.

## Rebuilding

```bash
python -m pip install pillow numpy scipy
python odysseus-wild-spine/tools/build_wild.py
python odysseus-wild-spine/tools/build_bonus.py
```

Each script:

- **Cuts parts** by connected component, so neighbouring sheet items don't leak into a cut, and trims the faint background-removal halo.
- **Rebuilds the frame.** Both empty frames had laurels baked into their lower half, so the bottom border is mirrored from the clean top border and the medallion copy is painted out. The separate laurels can then animate without doubling up.
- **Hides crop lines and seams in the artwork:**
  - WILD: feathered neck, skin-tone match, and the shoulder cape.
  - BONUS: the forearm cut is faded and sits behind the banner.
- **Generates effect sprites:** glow, light rays, sparkle and shine bar.
- **Packs the atlas, writes the skeleton and animations,** and saves setup-pose checks to `tools/_debug/<symbol>/`. `setup.png` shows the rig next to the original artwork.

Placement, timing and easing are plain Python in the build scripts. Edit and
rerun.
