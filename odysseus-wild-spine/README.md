# Odysseus Taverna — Spine slot symbols

This folder has Spine 4.3 rigs for 14 slot symbols, built straight from the AI
sprite sheets in `foranimation/` without the Spine editor. All of them play in
PixiJS through the official `spine-pixi-v8` runtime.

| Symbol | Source sheet (`ChatGPT Image Sep 14, 2026, …`) | Assets |
| --- | --- | --- |
| WILD (Odysseus) | `04_50_17 PM.png` | `assets/odysseus_wild.*` |
| BONUS (wine hostess) | `04_50_24 PM.png` | `assets/odysseus_bonus.*` |
| DZ Helmet / Ship / Chalice / Trident (round medallions) | `02_48_33 PM (1)` … `(4)` | `assets/odysseus_dz_helmet.*`, `…dz_ship.*`, `…dz_chalice.*`, `…dz_trident.*` |
| Helmet, Laurel, Ship, Amphora, Chalice, Grapes, Trident, Olive (square) | `02_31_21 PM (1)` … `(8)` | `assets/odysseus_helmet.*`, `…laurel.*`, `…ship.*`, `…amphora.*`, `…chalice.*`, `…grapes.*`, `…trident.*`, `…olive.*` |

## Preview it

From the repository root:

```bash
python -m http.server 4180 --directory odysseus-wild-spine
```

Open <http://localhost:4180> and pick a symbol in the panel. A hash in the URL
opens a symbol directly, e.g. <http://localhost:4180/#dz_ship>. Each rig loads
the first time you select it.

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
| `tools/build_wild.py`, `tools/build_bonus.py` | WILD and BONUS: part list, placement, animations |
| `tools/symbol_kit.py` | Template for the 12 regular symbols: frame, shared FX, cached part fitting, shared idle/land/connect |
| `tools/build_symbols.py` | The 12 regular symbols: cuts, fit hints, pivots, draw order, per-symbol motion |
| `vendor/` | Pinned `pixi.js 8.20.1` and `spine-pixi-v8 4.3.13` browser builds |

## Animations

Every symbol uses the same three names, so game code can treat them all the same.
Each fires `impact` (0.12 s) and `settled` (0.8 s) during `land`, and `cheer`
during `connect`. `connect` starts and ends on the idle pose, so it loops
cleanly.

### WILD

| Name | Length | What happens |
| --- | --- | --- |
| `idle` | 3.2 s loop | Breathing, head bob, laurel sway, back glow pulse, banner glint, medallion twinkle |
| `land` | 0.9 s | Drops in, squash + rebound, snarl → roar → grin, red flame burst, laurels flare |
| `connect` | 1.8 s | Pops to 112%, belly laugh (roar head bouncing), gold swirls, rays, sparkles, double banner shine |

The laurels, the cape over his left shoulder and three hair locks use Spine
physics. The generated head drawings are cropped along a straight line down his
left side. The locks are drawn over that edge, recoloured to his blonde, so his
hair flows past it. The cape covers the lower, diagonal part of the crop. Locks and
cape are parented to the head, so they keep covering the crop during head shakes.

### BONUS

| Name | Length | What happens |
| --- | --- | --- |
| `idle` | 3.6 s loop | Breathing and sway, goblet swirl, magenta back glow, banner glint, pink/gold twinkles |
| `land` | 0.9 s | Drops in, squash + rebound, closed-eye giggle, goblet jolt with a wine splash, laurels flare |
| `connect` | 1.9 s | "Cheers!": goblet dips then raises in a toast, two wine splashes, giggle bounce, wink, pink swirls, rays, sparkles, double banner shine |

Expressions are whole-bust swaps (smile / laugh / wink). The three busts were
registered against each other on the sheet, so swapping doesn't make the face
jump. The laurels and goblet use Spine physics.

### The 12 regular symbols

These share a template (`tools/symbol_kit.py`), so they feel like one set:

- **idle** (3.2 s loop): gentle breathing, a light sweep across the frame, back glow pulse, a few twinkles.
- **land** (0.9 s): drops in with squash and rebound, frame flash, rays, a sparkle burst.
- **connect** (1.8 s): pops to 112% with a wobble, spinning rays, double light sweep, sparkles.

Each symbol adds its own motion on top:

| Symbol | idle | land | connect |
| --- | --- | --- | --- |
| Helmet | gentle tilt, gleams (the crest is fixed to the helmet) | clang and squash | battle nod, glints |
| Laurel | two branches in a U, tip glints (no waving) | branches pulse | branches grow, leaves fly off |
| Ship | rocks on the waves, sail billows | splash-down, bow and stern spray | surges forward, sail fills, spray |
| Amphora | gentle sway | thud, squash, handles jiggle | hop and spin wobble, gold swooshes |
| Chalice | wine slosh, gem glow | wine slosh, drops | toast tilt, wine erupts, drops fly |
| Grapes | bunch bobs, leaves flutter (no pendulum swing) | squash and bounce | jiggle, grapes and juice pop out |
| Trident | float, tip glints | slam, prongs vibrate | thrust, prongs spread, glints |
| Olive | gentle branch sway (olives don't swing) | olives squash, leaves spring | olives pop, a leaf flies off |
| DZ medallions | medal shimmer, slash glow, ribbons and wreath sway, plus their items' idle | medal stamps down, wreaths clamp, ribbons flutter | medal coin-spins, slash flashes, gems spin, plus their items' celebration |

The four DZ medallions also have an **`appear`** animation (1.4 s, no loop) for
when the symbol is revealed on the reels:

- The medallion is cut in two along its diagonal slash. The upper-left half (e.g. the helmet side) slides in from the bottom-left, and the lower-right half slides down from the top-right.
- The halves lock together at 0.42 s with a flash, rays and sparkles. The slash lights up, the ribbons unfurl, the wreath halves swing shut, the DZ medal coin-flips in and the gems spin in.
- It fires `appear` at the lock (0.42 s) and `settled` at 1.26 s, and ends on the idle pose.

The cut frame halves exist only during `appear`: they are clipped copies of the frame that swap back to the single frame once locked, so idle, land and connect pay no clipping cost.

```js
dz.state.setAnimation(0, "appear", false);
dz.state.addAnimation(0, "idle", true, 0);
```

In the preview the Appear button (key `4`) shows up only for these four.

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
python odysseus-wild-spine/tools/build_symbols.py            # all 12, or name some: helmet dz_ship
```

For the 12 regular symbols, `build_symbols.py` finds where each loose part sits in
the finished symbol on its sheet: a masked colour-difference search over scale,
rotation and mirroring. It caches the answers in `tools/_cache/`, so rebuilds are
fast. Delete a symbol's cache file after changing its cut boxes or hints.

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
