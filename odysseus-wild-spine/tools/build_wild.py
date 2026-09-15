#!/usr/bin/env python3
"""WILD symbol (Odysseus) Spine rig, built from the 04_50_17 PM sprite sheet.

Outputs ../assets/odysseus_wild.{png,atlas,json} and debug renders in ./_debug.
Coordinates are "ref" pixels measured against the finished symbol in the
top-left of the sheet (about 380 x 392); ORIGIN is the symbol centre.
"""
import math
import os

import numpy as np
from PIL import Image

from spine_rig import (Rig, Sheet, attach, centered, feather_bottom, keep_largest, match_skin, osc, osc2, place,
                       remap_alpha, render_onion, render_setup, rgba, rotate, scale, smoothstep, standard_fx, translate,
                       trim, twinkle, write_outputs, write_skeleton, zoom)

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
SRC = os.path.join(REPO, "foranimation", "ChatGPT Image Sep 14, 2026, 04_50_17 PM.png")
ASSETS = os.path.join(HERE, "..", "assets")
DEBUG = os.path.join(HERE, "_debug", "wild")
NAME = "odysseus_wild"
ORIGIN = (190.0, 205.0)
SPARK = "fff2c0"


def rebuild_frame(S):
    """The empty frame has laurels and ribbon ends baked into its lower half.

    The laurels become their own animated layers, so rebuild a clean frame:
    keep the top half, fill the middle from a clean band of the side bars and
    mirror the top border into a new bottom border, painting out the medallion.
    """
    fx0, fy0, fw, fh = 381, 0, 362, 392
    f = S.rgba[fy0:fy0 + fh, fx0:fx0 + fw].astype(np.float32).copy()
    f[..., 3] = remap_alpha(f[..., 3].astype(np.uint8), 20)
    f[:, :6, 3] = 0
    f[:, 353:, 3] = 0
    col = f[..., 3][:, 262]
    top = int(np.nonzero(col > 128)[0].min())
    axis = top + 378  # bottom border lands where the original one was
    band0, band1 = 96, 150
    out = f.copy()
    mid_end = axis - 160  # first row that the mirror fills
    for yy in range(band1, mid_end):
        out[yy] = f[band0 + (yy - band1) % (band1 - band0)]
    for yy in range(mid_end, fh):
        src = axis - yy
        out[yy] = f[src] if 0 <= src < fh else 0
    # paint the mirrored medallion out with a plain stretch of bar
    med0, med1, tile0, tile1 = 112, 238, 250, 282
    rows = np.arange(axis - 84, fh)
    for xx in range(med0, med1):
        out[rows, xx] = out[rows, tile0 + (xx - med0) % (tile1 - tile0)]
    for seam in (band1, mid_end):
        above, below = out[seam - 7].copy(), out[seam + 7].copy()
        for k in range(-6, 7):
            wgt = (k + 7) / 14.0
            out[seam + k] = out[seam + k] * 0.4 + (above * (1 - wgt) + below * wgt) * 0.6
    # the centre of the window was never covered by laurels: keep the original texture there
    yy, xx = np.mgrid[0:fh, 0:fw]
    centre = smoothstep(0, 18, np.minimum(xx - 104, 252 - xx)) * smoothstep(0, 18, np.minimum(yy - 70, 318 - yy))
    out = out * (1 - centre[..., None]) + f * centre[..., None]
    out = keep_largest(out)  # drop stray neighbour hair tips
    part = trim("frame", np.clip(out, 0, 255).astype(np.uint8), fx0, fy0)
    rows_opaque = np.nonzero(part.rgba[..., 3][:, 262 - (part.ox - fx0)] > 128)[0]
    cols_opaque = np.nonzero(part.rgba[..., 3][part.h // 2] > 128)[0]
    part.outer = (cols_opaque.min(), rows_opaque.min(), cols_opaque.max(), rows_opaque.max())
    return part


def feather_left(part, y_from, y_to, depth=16):
    """Soften the straight crop line down the left side of a head drawing (sheet rows y_from..y_to)."""
    a = part.rgba[..., 3].astype(np.float32)
    for sy in range(y_from, y_to):
        cy = sy - part.oy
        if not 0 <= cy < part.h:
            continue
        cols = np.nonzero(a[cy] > 8)[0]
        if len(cols) == 0:
            continue
        left = cols.min()
        c = np.arange(left, min(part.w, left + depth + 1))
        a[cy, c] *= smoothstep(0, depth, (c - left).astype(np.float32))
    part.rgba[..., 3] = a.astype(np.uint8)


def match_hair(part, ref_rgba):
    """Shift a part's hair colours (mean/spread per channel) toward a reference hair sample; dark outlines stay."""
    def hair(rgba):
        rgb = rgba[..., :3].astype(np.float32)
        lum = rgb.mean(-1)
        return (rgba[..., 3] > 200) & (lum > 90) & (rgb[..., 0] > rgb[..., 2] + 30)
    src = part.rgba[..., :3].astype(np.float32)
    s = src[hair(part.rgba)]
    t = ref_rgba[..., :3].astype(np.float32)[hair(ref_rgba)]
    moved = (src - s.mean(0)) * (t.std(0) / (s.std(0) + 1e-3)) + t.mean(0)
    lum = src.mean(-1, keepdims=True)
    w = smoothstep(40, 110, lum)  # keep the ink lines dark
    part.rgba[..., :3] = np.clip(src * (1 - w) + moved * w, 0, 255).astype(np.uint8)


def lock_root(part):
    """Sheet point at the thick root of a loose hair lock (centre of its top quarter)."""
    m = part.rgba[..., 3] > 128
    rows = np.nonzero(m.any(1))[0]
    top = rows[: max(1, len(rows) // 4)]
    ys, xs = np.nonzero(m[top.min():top.max() + 1])
    return part.ox + xs.mean(), part.oy + top.min() + ys.mean()


def build():
    os.makedirs(DEBUG, exist_ok=True)
    S = Sheet(SRC)
    print("cutting parts")
    P = {}
    P["frame"] = rebuild_frame(S)
    P["banner"] = S.cut("banner", (413, 684, 473, 125))
    P["laurel_l"] = S.cut("laurel_l", (443, 398, 178, 279))
    P["laurel_r"] = S.cut("laurel_r", (658, 408, 174, 270))
    P["medallion"] = S.cut("medallion", (570, 529, 114, 115))
    P["torso"] = S.cut("torso", (12, 390, 448, 215))
    P["cape_drape"] = S.cut("cape_drape", (6, 615, 318, 133))
    P["head_roar"] = S.cut("head_roar", (735, 13, 242, 271))
    P["head_grin"] = S.cut("head_grin", (981, 19, 238, 263))
    P["head_snarl"] = S.cut("head_snarl", (1202, 18, 243, 266))
    P["lock_a"] = S.cut("lock_a", (1104, 287, 90, 128))
    P["lock_b"] = S.cut("lock_b", (1063, 420, 111, 117))
    P["lock_c"] = S.cut("lock_c", (1183, 306, 94, 125))
    P["fx_flame"] = S.cut("fx_flame", (812, 842, 636, 244), floor=0, grow=16, min_inside=0.5)
    P["fx_swirl"] = S.cut("fx_swirl", (8, 886, 446, 190), floor=0, grow=14, min_inside=0.5)
    P["fx_swirl2"] = S.cut("fx_swirl2", (470, 915, 400, 160), floor=0, grow=14, min_inside=0.5)
    P.update(standard_fx())

    feather_bottom(P["head_roar"], 740, 900)
    feather_bottom(P["head_grin"], 985, 1125)
    feather_bottom(P["head_snarl"], 1206, 1360)
    # every head drawing is cropped along a straight vertical line down its left side. Only a thin
    # anti-alias fade: a wide fade made that hair see-through and it read as missing hair.
    feather_left(P["head_roar"], 95, 240, depth=3)
    feather_left(P["head_grin"], 95, 235, depth=3)
    feather_left(P["head_snarl"], 95, 245, depth=3)
    # the loose locks are painted a warmer brown than his pale blonde hair: match them to the head
    grin_hair = P["head_grin"].rgba[20:120, 10:110]
    for name in ("lock_a", "lock_b", "lock_c"):
        match_hair(P[name], grin_hair)
    grin = P["head_grin"]
    neck_ref = grin.rgba[222 - grin.oy:262 - grin.oy, 1015 - grin.ox:1085 - grin.ox]
    match_skin(P["torso"], (140, 392, 110, 90), neck_ref)
    for p in P.values():
        print(f"  {p.name:11s} {p.w:4d}x{p.h:<4d} sheet@({p.ox},{p.oy})")

    R = Rig()
    fr = P["frame"]
    ol, ot, orr, ob = fr.outer
    frame_anchor = (fr.ox + (ol + orr) / 2.0, fr.oy + (ot + ob) / 2.0)
    frame_at = (190.0, 206.0)
    frame_place = place(fr, frame_anchor, frame_at, 1.0)
    med_sheet = (381 + 172, 42)
    med_at = (frame_at[0] + med_sheet[0] - frame_anchor[0], frame_at[1] + med_sheet[1] - frame_anchor[1])
    inner = dict(l=frame_at[0] - (orr - ol) / 2 + 35, r=frame_at[0] + (orr - ol) / 2 - 35,
                 t=frame_at[1] - (ob - ot) / 2 + 30, b=frame_at[1] + (ob - ot) / 2 - 18)

    R.bone("root", None, ORIGIN)
    R.bone("symbol", "root", ORIGIN)
    R.bone("fx", "symbol", ORIGIN)
    R.bone("swirl_orbit", "fx", ORIGIN)
    R.bone("swirl_a", "swirl_orbit", (ORIGIN[0] - 222, ORIGIN[1] + 30))
    R.bone("swirl_b", "swirl_orbit", (ORIGIN[0] + 222, ORIGIN[1] - 30))
    R.bone("frame", "symbol", frame_at)
    R.bone("medal", "frame", med_at)
    R.bone("torso", "symbol", (190, 300), length=60)
    R.bone("head", "torso", (186, 258), length=90)
    R.bone("cape_drape", "head", (178, 282), length=80)
    # loose locks tucked behind the head's left crop line: roots hidden under the hair, tips flow out past it
    # locks drawn over the head's left crop line: roots sit on his hair, tips flow out and down past the cut
    # locks drawn over the head's left crop line: roots sit on his hair, tips flow out and down past the cut
    locks = [("hair_l1", "lock_a", (140, 108), 0.66, 16), ("hair_l2", "lock_c", (136, 146), 0.66, 8), ("hair_l3", "lock_b", (138, 186), 0.62, 2)]
    for bone, _, root, _, _ in locks:
        R.bone(bone, "head", root, length=50)
    R.bone("laurel_l", "symbol", (92, 336), length=70)
    R.bone("laurel_r", "symbol", (288, 336), length=70)
    R.bone("banner", "symbol", (190, 338))
    R.bone("shine", "banner", (190, 338))
    # spark 8 is the gleam on his grin: it sits on the teeth and rides the head bone
    sparkle_spots = [(190, 44), (52, 96), (330, 82), (34, 262), (350, 250), (104, 384), (282, 386), (228, 203)]
    for i, spot in enumerate(sparkle_spots):
        R.bone(f"spk{i + 1}", "head" if i == 7 else "fx", spot)

    # heads share one registration (measured against the finished symbol)
    head_tl = {"head_roar": ((735, 13), (98.0, 34.0), 0.920),
               "head_grin": ((981, 19), (108.1, 39.5), 0.911),
               "head_snarl": ((1202, 18), (85.1, 23.9), 0.952)}
    heads = {k: place(P[k], tl, at, s) for k, (tl, at, s) in head_tl.items()}

    hidden = "ffffff00"
    R.slot("fx_rays", "fx", {"rays": centered(P["rays"], ORIGIN, 1.9)}, "rays", color="ffd27a00", blend="additive")
    R.slot("fx_flame", "fx", {"fx_flame": centered(P["fx_flame"], (190, 262), 0.86)}, "fx_flame", color=hidden, blend="additive")
    R.slot("frame", "frame", {"frame": frame_place}, "frame")
    # Only the glow and torso are clipped to the window; the head's hair may pop out over the border.
    window = [(inner["l"], inner["t"]), (inner["r"], inner["t"]), (inner["r"], inner["b"]), (inner["l"], inner["b"])]
    R.slot("glow_clip", "symbol", {"glow_clip": dict(clip=window, end="back_glow")}, "glow_clip")
    R.slot("back_glow", "head", {"glow": centered(P["glow"], (196, 150), 3.1)}, "glow", color="ffb45a55", blend="additive")
    R.slot("window_clip", "symbol", {"window_clip": dict(clip=window, end="torso")}, "window_clip")
    # sits high enough that its shoulders are under the head's (feathered) neck on both sides
    R.slot("torso", "torso", {"torso": place(P["torso"], (192, 420), (186, 244), 0.9)}, "torso")
    R.slot("head", "head", heads, "head_grin")
    for bone, part, root, s, r in locks:
        R.slot(bone, bone, {part: place(P[part], lock_root(P[part]), root, s, rotation=r)}, part)
    # The generated head portraits are cropped along a diagonal that chops the left hair and neck;
    # a cape thrown over that shoulder hides the crop line. Parented to the head so it never uncovers it.
    R.slot("cape_drape", "cape_drape", {"cape_drape": place(P["cape_drape"], (70, 690), (178, 282), 0.55, rotation=-34, flip=True)}, "cape_drape")
    R.slot("laurel_l", "laurel_l", {"laurel_l": place(P["laurel_l"], (540, 668), (92, 336), 0.62, rotation=22)}, "laurel_l")
    R.slot("laurel_r", "laurel_r", {"laurel_r": place(P["laurel_r"], (742, 668), (288, 336), 0.62, rotation=-22)}, "laurel_r")
    R.slot("banner", "banner", {"banner": place(P["banner"], (649.5, 746.5), (190, 338), 0.8)}, "banner")
    banner_clip = [(190 - 138, 338 - 42), (190 + 138, 338 - 42), (190 + 138, 338 + 44), (190 - 138, 338 + 44)]
    R.slot("banner_clip", "banner", {"banner_clip": dict(clip=banner_clip, end="banner_shine")}, "banner_clip")
    R.slot("banner_shine", "shine", {"shine": centered(P["shine"], (190, 338), 1.0, rotation=-18)}, "shine", color="fff3c400", blend="additive")
    R.slot("frame_flash", "frame", {"frame": frame_place}, "frame", color="ffe7a000", blend="additive")
    R.slot("medal_glow", "medal", {"medallion": centered(P["medallion"], med_at, 0.64)}, "medallion", color="ffffff00", blend="additive")
    R.slot("swirl_a", "swirl_a", {"fx_swirl": centered(P["fx_swirl"], R.world["swirl_a"], 0.48, rotation=70)}, "fx_swirl", color=hidden, blend="additive")
    R.slot("swirl_b", "swirl_b", {"fx_swirl2": centered(P["fx_swirl2"], R.world["swirl_b"], 0.55, rotation=250)}, "fx_swirl2", color=hidden, blend="additive")
    R.slot("front_glow", "fx", {"glow": centered(P["glow"], (190, 190), 4.6)}, "glow", color="ffdc9600", blend="additive")
    for i, spot in enumerate(sparkle_spots):
        R.slot(f"sparkle{i + 1}", f"spk{i + 1}", {"sparkle": centered(P["sparkle"], spot, 0.55)}, "sparkle", color="fff2c000", blend="additive")

    R.physics("laurel_l", rotate=0.5, inertia=0.5, strength=160, damping=0.8, mass=1.0)
    R.physics("laurel_r", rotate=0.5, inertia=0.5, strength=160, damping=0.8, mass=1.0)
    R.physics("cape_drape", rotate=0.35, inertia=0.5, strength=120, damping=0.85, mass=1.0)
    for bone, *_ in locks:
        R.physics(bone, rotate=0.8, inertia=0.5, strength=70, damping=0.84, mass=1.1)

    ref = S.rgba[0:392, 0:380]
    render_setup(R, os.path.join(DEBUG, "setup.png"), ref)
    render_setup(R, os.path.join(DEBUG, "setup_teeth_spark.png"), ref, reveal={"sparkle8"})
    zoom(os.path.join(DEBUG, "setup.png"), (90 + 40, 70 + 40, 90 + 250, 70 + 320), 3, os.path.join(DEBUG, "left_side_zoom.png"))
    render_onion(heads, ("head_grin", "head_roar", "head_snarl"), os.path.join(DEBUG, "heads_onion.png"))
    Image.fromarray(fr.rgba).save(os.path.join(DEBUG, "frame_rebuilt.png"))

    skeleton = write_skeleton(R, "odysseus-wild-v1", ("impact", "cheer", "settled"))
    skeleton["animations"] = {"idle": anim_idle(), "land": anim_land(), "connect": anim_connect()}
    write_outputs(NAME, ASSETS, list(P.values()), skeleton)


# --------------------------------------------------------------------------
# Animations
# --------------------------------------------------------------------------
def anim_idle():
    T = 3.2
    bones = {
        "torso": {"scale": osc2(T, 0.006, 0.014, phase=-math.pi / 2, bx=1.006, by=1.014)},
        "head": {"rotate": osc(T, 1.4, phase=-0.5), "translate": osc2(T, 0.0, 2.2, phase=-math.pi / 2 - 0.4, by=0)},
        "laurel_l": {"rotate": osc(T, 1.8, phase=0.0)},
        "laurel_r": {"rotate": osc(T, 1.8, phase=math.pi)},
        "cape_drape": {"rotate": osc(T, 1.2, phase=-1.4)},
        "hair_l1": {"rotate": osc(T, 2.4, phase=-1.0)},
        "hair_l2": {"rotate": osc(T, 2.0, phase=-1.4)},
        "hair_l3": {"rotate": osc(T, 1.8, phase=-1.8)},
        "banner": {"translate": osc2(T, 0, 1.6, phase=0.6)},
        "shine": {"translate": translate((0, -210, 0, None), (1.9, -210, 0, "inout"), (2.55, 210, 0, None))},
    }
    slots = {
        "back_glow": {"rgba": rgba((0, "ffb45a40", "inout"), (T / 2, "ffb45a70", "inout"), (T, "ffb45a40", None))},
        "banner_shine": {"rgba": rgba((0, "fff3c400", None), (1.9, "fff3c400", "soft"), (2.1, "fff3c4d0", "linear"), (2.4, "fff3c4d0", "in"), (2.55, "fff3c400", None))},
        "medal_glow": {"rgba": rgba((0, "ffffff00", "inout"), (1.2, "ffffff00", "inout"), (1.6, "ffffff66", "inout"), (2.1, "ffffff00", None))},
        "head": {"attachment": attach((0, "head_grin"))},
    }
    for idx, t0 in ((1, 1.25), (3, 2.35), (8, 0.3)):
        s, b = twinkle(SPARK, t0, 0.6, peak=0.9, grow=0.8)
        slots[f"sparkle{idx}"] = {"rgba": s}
        bones[f"spk{idx}"] = b
    return {"bones": bones, "slots": slots}


def anim_land():
    bones = {
        "symbol": {
            "translate": translate((0, 0, 56, "in"), (0.12, 0, -7, "out"), (0.26, 0, 3, "inout"), (0.42, 0, 0, None)),
            "scale": scale((0, 0.95, 1.07, "in"), (0.12, 1.09, 0.89, "out"), (0.25, 0.97, 1.04, "inout"), (0.4, 1.01, 0.99, "inout"), (0.56, 1, 1, None)),
        },
        "torso": {"scale": scale((0, 1, 1, None), (0.12, 1, 1, "out"), (0.2, 1.02, 0.95, "inout"), (0.42, 1, 1.02, "inout"), (0.62, 1, 1, None))},
        "head": {
            "rotate": rotate((0, 3, "in"), (0.12, -7, "out"), (0.3, 6, "inout"), (0.5, -2, "inout"), (0.72, 0, None)),
            "translate": translate((0, 0, 4, "in"), (0.12, 0, -9, "out"), (0.28, 0, 6, "inout"), (0.5, 0, 0, None)),
        },
        "laurel_l": {"rotate": rotate((0, -4, None), (0.12, -4, "out"), (0.22, 16, "inout"), (0.42, -5, "inout"), (0.62, 2, "inout"), (0.8, 0, None))},
        "laurel_r": {"rotate": rotate((0, 4, None), (0.12, 4, "out"), (0.22, -16, "inout"), (0.42, 5, "inout"), (0.62, -2, "inout"), (0.8, 0, None))},
        "banner": {
            "scale": scale((0, 1, 1, None), (0.12, 1, 1, "out"), (0.2, 1.2, 1.2, "inout"), (0.36, 0.95, 0.95, "inout"), (0.52, 1.03, 1.03, "inout"), (0.68, 1, 1, None)),
            "translate": translate((0, 0, 0, None), (0.12, 0, 0, "out"), (0.2, 0, 6, "inout"), (0.4, 0, 0, None)),
        },
        "fx": {"scale": scale((0, 0.6, 0.6, None), (0.12, 0.6, 0.6, "out"), (0.7, 1.25, 1.25, None)),
               "rotate": rotate((0, 0, None), (0.12, 0, "out"), (0.9, 24, None))},
        "shine": {"translate": translate((0, -210, 0, None), (0.22, -210, 0, "inout"), (0.62, 210, 0, None))},
    }
    slots = {
        "head": {"attachment": attach((0, "head_snarl"), (0.13, "head_roar"), (0.6, "head_grin"))},
        "fx_flame": {"rgba": rgba((0, "ffffff00", None), (0.11, "ffffff00", "out"), (0.17, "ffffffe6", "soft"), (0.7, "ffffff00", None))},
        "fx_rays": {"rgba": rgba((0, "ffd27a00", None), (0.11, "ffd27a00", "out"), (0.16, "ffd27acc", "soft"), (0.75, "ffd27a00", None))},
        "frame_flash": {"rgba": rgba((0, "ffe7a000", None), (0.11, "ffe7a000", "out"), (0.14, "ffe7a080", "soft"), (0.42, "ffe7a000", None))},
        "medal_glow": {"rgba": rgba((0, "ffffff00", None), (0.12, "ffffff00", "out"), (0.18, "ffffffe6", "soft"), (0.6, "ffffff00", None))},
        "front_glow": {"rgba": rgba((0, "ffdc9600", None), (0.11, "ffdc9600", "out"), (0.14, "ffdc9640", "soft"), (0.36, "ffdc9600", None))},
        "banner_shine": {"rgba": rgba((0, "fff3c400", None), (0.22, "fff3c400", "soft"), (0.32, "fff3c4e0", "linear"), (0.5, "fff3c4e0", "in"), (0.62, "fff3c400", None))},
    }
    for idx, t0 in ((4, 0.13), (5, 0.15), (6, 0.14), (7, 0.16), (2, 0.2), (3, 0.19)):
        s, b = twinkle(SPARK, t0, 0.55, peak=1.0, spin=120, grow=1.0)
        slots[f"sparkle{idx}"] = {"rgba": s}
        bones[f"spk{idx}"] = b
    return {"bones": bones, "slots": slots, "events": [{"time": 0.12, "name": "impact"}, {"time": 0.8, "name": "settled"}]}


def anim_connect():
    D = 1.8
    laugh_rot = [(0, 0, "inout"), (0.14, -3, "out"), (0.3, 8, "inout")]
    laugh_y = [(0, 0, 0, "inout"), (0.14, 0, -4, "out"), (0.3, 0, 8, "inout")]
    t = 0.3
    flip = 1
    while t + 0.12 <= 1.26:
        t += 0.12
        laugh_rot.append((t, 8 + 3.5 * flip, "inout"))
        laugh_y.append((t, 0, 8 + 4.5 * flip, "inout"))
        flip = -flip
    laugh_rot += [(1.5, -2.5, "inout"), (1.66, 1, "inout"), (D, 0, None)]
    laugh_y += [(1.5, 0, -2, "inout"), (1.66, 0, 1, "inout"), (D, 0, 0, None)]
    torso_bounce = [(0, 1, 1, "inout"), (0.14, 1.02, 0.95, "out"), (0.3, 1, 1.04, "inout")]
    t = 0.3
    flip = 1
    while t + 0.12 <= 1.26:
        t += 0.12
        torso_bounce.append((t, 1, 1.02 + 0.02 * flip, "inout"))
        flip = -flip
    torso_bounce += [(1.5, 1, 0.99, "inout"), (D, 1, 1, None)]

    bones = {
        "symbol": {
            "scale": scale((0, 1, 1, "inout"), (0.14, 1.04, 0.95, "out"), (0.32, 1.12, 1.12, "inout"), (0.5, 1.07, 1.07, "inout"),
                           (0.9, 1.09, 1.09, "inout"), (1.3, 1.07, 1.07, "inout"), (1.52, 0.98, 0.98, "inout"), (1.66, 1.01, 1.01, "inout"), (D, 1, 1, None)),
            "rotate": rotate((0, 0, "inout"), (0.32, -2.5, "inout"), (0.46, 2, "inout"), (0.6, -1.2, "inout"), (0.76, 0.6, "inout"), (0.95, 0, None)),
            "translate": translate((0, 0, 0, "inout"), (0.14, 0, -4, "out"), (0.32, 0, 10, "inout"), (1.3, 0, 7, "inout"), (1.55, 0, -2, "inout"), (D, 0, 0, None)),
        },
        "head": {"rotate": rotate(*laugh_rot), "translate": translate(*laugh_y)},
        "torso": {"scale": scale(*torso_bounce)},
        "laurel_l": {"rotate": rotate((0, 0, "inout"), (0.14, -3, "out"), (0.34, 14, "inout"), (0.62, 6, "inout"), (0.9, 12, "inout"), (1.18, 6, "inout"), (1.5, -2, "inout"), (D, 0, None))},
        "laurel_r": {"rotate": rotate((0, 0, "inout"), (0.14, 3, "out"), (0.34, -14, "inout"), (0.62, -6, "inout"), (0.9, -12, "inout"), (1.18, -6, "inout"), (1.5, 2, "inout"), (D, 0, None))},
        "banner": {
            "scale": scale((0, 1, 1, "inout"), (0.16, 0.94, 0.94, "out"), (0.36, 1.16, 1.16, "inout"), (0.56, 1.06, 1.06, "inout"),
                           (0.86, 1.1, 1.1, "inout"), (1.16, 1.06, 1.06, "inout"), (1.5, 0.98, 0.98, "inout"), (D, 1, 1, None)),
            "translate": translate((0, 0, 0, "inout"), (0.36, 0, 4, "inout"), (1.5, 0, 0, None)),
        },
        "fx": {"rotate": rotate((0, 0, "linear"), (D, 60, None)), "scale": scale((0, 0.7, 0.7, "out"), (0.4, 1.15, 1.15, "inout"), (1.2, 1.05, 1.05, "inout"), (D, 1.25, 1.25, None))},
        "swirl_orbit": {"rotate": rotate((0, 60, None), (0.22, 60, "out"), (1.25, -250, None))},
        "shine": {"translate": translate((0, -210, 0, None), (0.36, -210, 0, "inout"), (0.8, 210, 0, None), (1.0, -210, 0, "inout"), (1.44, 210, 0, None))},
    }
    slots = {
        "head": {"attachment": attach((0, "head_grin"), (0.15, "head_roar"), (1.38, "head_grin"))},
        "fx_rays": {"rgba": rgba((0, "ffd27a00", "out"), (0.32, "ffd27ae0", "inout"), (1.2, "ffd27a99", "inout"), (D, "ffd27a00", None))},
        "fx_flame": {"rgba": rgba((0, "ffffff00", "out"), (0.36, "ffffffcc", "inout"), (0.9, "ffffff80", "inout"), (1.25, "ffffffb0", "inout"), (D, "ffffff00", None))},
        "frame_flash": {"rgba": rgba((0, "ffe7a000", None), (0.3, "ffe7a000", "out"), (0.34, "ffe7a060", "soft"), (0.7, "ffe7a000", None))},
        "medal_glow": {"rgba": rgba((0, "ffffff00", "out"), (0.34, "fffffff0", "inout"), (0.8, "ffffff55", "inout"), (1.1, "ffffffb0", "inout"), (D, "ffffff00", None))},
        "front_glow": {"rgba": rgba((0, "ffdc9600", None), (0.3, "ffdc9600", "out"), (0.34, "ffdc963c", "soft"), (0.6, "ffdc9600", None))},
        "back_glow": {"rgba": rgba((0, "ffb45a40", "out"), (0.36, "ffc86ae0", "inout"), (1.3, "ffc86a99", "inout"), (D, "ffb45a40", None))},
        "swirl_a": {"rgba": rgba((0, "ffffff00", None), (0.22, "ffffff00", "out"), (0.4, "ffffffd8", "inout"), (0.9, "ffffff90", "in"), (1.25, "ffffff00", None))},
        "swirl_b": {"rgba": rgba((0, "ffffff00", None), (0.26, "ffffff00", "out"), (0.44, "ffffffd8", "inout"), (0.95, "ffffff90", "in"), (1.25, "ffffff00", None))},
        "banner_shine": {"rgba": rgba((0, "fff3c400", None), (0.36, "fff3c400", "soft"), (0.46, "fff3c4f0", "linear"), (0.68, "fff3c4f0", "in"), (0.8, "fff3c400", "stepped"),
                                      (1.0, "fff3c400", "soft"), (1.1, "fff3c4f0", "linear"), (1.32, "fff3c4f0", "in"), (1.44, "fff3c400", None))},
    }
    pops = [(1, 0.34, 1.2), (2, 0.42, 1.0), (3, 0.5, 1.0), (4, 0.62, 1.1), (5, 0.7, 1.1), (6, 0.84, 0.9), (7, 0.92, 0.9), (8, 1.06, 0.8)]
    for idx, t0, grow in pops:
        s, b = twinkle(SPARK, t0, 0.5, peak=1.0, spin=140, grow=grow)
        slots[f"sparkle{idx}"] = {"rgba": s}
        bones[f"spk{idx}"] = b
    return {"bones": bones, "slots": slots, "events": [{"time": 0.32, "name": "cheer"}]}


if __name__ == "__main__":
    build()
