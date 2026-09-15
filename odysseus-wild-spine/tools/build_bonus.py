#!/usr/bin/env python3
"""BONUS symbol (wine-goddess hostess) Spine rig, built from the 04_50_24 PM sprite sheet.

Outputs ../assets/odysseus_bonus.{png,atlas,json} and debug renders in ./_debug/bonus.
Coordinates are "ref" pixels measured against the finished symbol in the
top-left of the sheet (about 380 x 380); ORIGIN is the symbol centre.
"""
import math
import os

import numpy as np
from PIL import Image

from spine_rig import (Rig, Sheet, attach, centered, face_patch, feather_bottom, keep_largest, osc, osc2, place,
                       raster_ref, remap_alpha, render_setup, rgba, rotate, scale, standard_fx, translate, trim,
                       twinkle, write_outputs, write_skeleton, zoom)

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
SRC = os.path.join(REPO, "foranimation", "ChatGPT Image Sep 14, 2026, 04_50_24 PM.png")
ASSETS = os.path.join(HERE, "..", "assets")
DEBUG = os.path.join(HERE, "_debug", "bonus")
NAME = "odysseus_bonus"
ORIGIN = (197.0, 199.0)
PINK = "ffc4ee"
GOLD = "fff2c0"
REF = (392, 400)      # ref-space canvas the expression plates are rasterised into
FACE = (204.0, 200.0, 54.0, 52.0, -20.0)  # eyes/nose/mouth ellipse, tilted with her head

# The empty frame sits 357.5 px right of the finished symbol on the sheet (same y).
FRAME_DX = -357.5


def rebuild_frame(S):
    """Remove the laurels baked into the lower corners of the empty frame.

    The rows above the laurels are untouched; everything below is the top half
    mirrored (side bars and background continue seamlessly), with the mirrored
    medallion painted out.
    """
    fx0, fy0, fw, fh = 380, 0, 342, 380
    f = S.rgba[fy0:fy0 + fh, fx0:fx0 + fw].astype(np.float32).copy()
    f[..., 3] = remap_alpha(f[..., 3].astype(np.uint8), 20)
    f[:, :12, 3] = 0
    f[:, 336:, 3] = 0
    a = f[..., 3]
    bar_col = a[:, 262]
    top = int(np.nonzero(bar_col > 128)[0].min())
    bottom = int(np.nonzero(bar_col > 128)[0].max())
    laurel_top = 190  # topmost baked laurel leaf is at y~196 on both sides (read off the gridded sheet)
    axis = min(top + bottom, 2 * laurel_top - 2)
    start = axis - laurel_top + 2
    out = f.copy()
    for yy in range(start, fh):
        src = axis - yy
        out[yy] = f[src] if 0 <= src < fh else 0
    # paint out the mirrored medallion with plain bar
    med0, med1, tile0, tile1 = 136, 212, 226, 256
    rows = np.arange(max(start, axis - 90), fh)
    for xx in range(med0, med1):
        out[rows, xx] = out[rows, tile0 + (xx - med0) % (tile1 - tile0)]
    # soften the mirror seam
    above, below = out[start - 6].copy(), out[start + 6].copy()
    for k in range(-5, 6):
        wgt = (k + 6) / 12.0
        out[start + k] = out[start + k] * 0.4 + (above * (1 - wgt) + below * wgt) * 0.6
    out = keep_largest(out)
    part = trim("frame", np.clip(out, 0, 255).astype(np.uint8), fx0, fy0)
    print(f"  frame rebuild: top={top} bottom={bottom} laurels from y={laurel_top} mirror axis={axis}")
    return part


def chained(box1_tl, anchor1, at1, s1, reg_tl, reg_s, box2_tl):
    """Anchor/at/scale for a part registered against part 1's box (reg_tl, reg_s in box-1 coordinates)."""
    base = (box1_tl[0] + reg_tl[0] - anchor1[0], box1_tl[1] + reg_tl[1] - anchor1[1])
    return box2_tl, (at1[0] + s1 * base[0], at1[1] + s1 * base[1]), s1 * reg_s


def render_faces(bust, faces, path):
    """The one head plate, then each face patch laid over it, to check the seams."""
    base = raster_ref(bust, REF)
    tiles = [base]
    for a in faces.values():
        layer = raster_ref(a, REF).astype(np.float32)
        out = base.astype(np.float32).copy()
        w = layer[..., 3:4] / 255.0
        out[..., :3] = layer[..., :3] * w + out[..., :3] * (1 - w)
        out[..., 3] = np.maximum(out[..., 3], layer[..., 3])
        tiles.append(np.clip(out, 0, 255).astype(np.uint8))
    canvas = Image.new("RGB", (REF[0] * len(tiles), REF[1]), (40, 40, 40))
    for i, t in enumerate(tiles):
        canvas.paste(Image.fromarray(t).convert("RGB"), (i * REF[0], 0), Image.fromarray(t))
    canvas.save(path)


def build():
    os.makedirs(DEBUG, exist_ok=True)
    S = Sheet(SRC)
    print("cutting parts")
    P = {}
    P["frame"] = rebuild_frame(S)
    P["bust_smile"] = S.cut("bust_smile", (721, 58, 247, 314))
    P["bust_laugh"] = S.cut("bust_laugh", (958, 49, 255, 331))
    P["bust_wink"] = S.cut("bust_wink", (1201, 61, 245, 318))
    P["goblet"] = S.cut("goblet", (374, 373, 171, 247))
    P["laurel_l"] = S.cut("laurel_l", (536, 395, 159, 228))
    P["laurel_r"] = S.cut("laurel_r", (730, 395, 151, 228))
    P["medallion"] = S.cut("medallion", (913, 441, 88, 88))
    P["banner"] = S.cut("banner", (1015, 414, 418, 130))
    P["splash_a"] = S.cut("splash_a", (600, 905, 250, 168), floor=12, grow=3, min_inside=0.5)
    P["splash_b"] = S.cut("splash_b", (826, 905, 194, 168), floor=12, grow=3, min_inside=0.5)
    P["fx_pink_a"] = S.cut("fx_pink_a", (990, 880, 250, 206), floor=0, grow=14, min_inside=0.5)
    P["fx_pink_b"] = S.cut("fx_pink_b", (1236, 880, 212, 206), floor=0, grow=14, min_inside=0.5)
    P.update(standard_fx())
    feather_bottom(P["goblet"], 370, 466, depth=14)  # forearm cut, in case it peeks past the banner tail
    for p in P.values():
        print(f"  {p.name:11s} {p.w:4d}x{p.h:<4d} sheet@({p.ox},{p.oy})")

    R = Rig()
    frame_place = place(P["frame"], (553.5, 48), (553.5 + FRAME_DX, 48), 1.0)
    med_at = (196.4, 45.4)
    window = [(58, 60), (335, 60), (335, 332), (58, 332)]

    body_at = (205, 300)
    goblet_at = (76, 298)   # wrist; low enough that the forearm cut hides behind the banner
    splash_at = (96, 148)   # above the goblet bowl
    banner_at = (190.5, 330)
    R.bone("root", None, ORIGIN)
    R.bone("symbol", "root", ORIGIN)
    R.bone("fx", "symbol", ORIGIN)
    R.bone("swirl_orbit", "fx", ORIGIN)
    R.bone("swirl_a", "swirl_orbit", (ORIGIN[0] - 218, ORIGIN[1] + 20))
    R.bone("swirl_b", "swirl_orbit", (ORIGIN[0] + 218, ORIGIN[1] - 20))
    R.bone("frame", "symbol", (196, 199))
    R.bone("medal", "frame", med_at)
    R.bone("body", "symbol", body_at, length=120)
    R.bone("goblet", "body", goblet_at, length=110)
    R.bone("splash", "goblet", splash_at)
    R.bone("splash2", "goblet", splash_at)
    laurel_l_at, laurel_r_at = (100, 332), (294, 332)  # stems, mirrored about the frame centre
    R.bone("laurel_l", "symbol", laurel_l_at, length=70)
    R.bone("laurel_r", "symbol", laurel_r_at, length=70)
    R.bone("banner", "symbol", banner_at)
    R.bone("shine", "banner", banner_at)
    sparkle_spots = [(196, 46), (62, 92), (332, 86), (30, 250), (364, 240), (96, 384), (298, 384), (150, 160)]
    for i, spot in enumerate(sparkle_spots):
        R.bone(f"spk{i + 1}", "fx", spot)

    # The three expressions were registered against each other on the sheet (see README).
    smile_anchor, smile_at, smile_s = (844.5, 58), (228, 45), 0.92
    busts = {"bust_smile": place(P["bust_smile"], smile_anchor, smile_at, smile_s)}
    for name, reg_tl, reg_s, box_tl in (("bust_laugh", (6, 9), 0.965, (958, 45)), ("bust_wink", (-1, 15), 0.970, (1200, 55))):
        anchor, at, s = chained((712, 45), smile_anchor, smile_at, smile_s, reg_tl, reg_s, box_tl)
        busts[name] = place(P[name], anchor, at, s)
    # Only her face swaps. Each expression redraws the hair, the head laurel and the
    # earrings slightly differently, so swapping whole busts made the hair jump every
    # time the expression changed; the smile bust stays put and carries all of that.
    for name in ("laugh", "wink"):
        P[f"face_{name}"] = face_patch(f"face_{name}", busts[f"bust_{name}"], FACE, REF)
    faces = {n: centered(P[n], P[n].center_sheet, 1.0) for n in ("face_laugh", "face_wink")}
    for name in ("bust_laugh", "bust_wink"):
        del P[name]  # only cut to lift the face off; the full plates never reach the atlas
    busts = {"bust_smile": busts["bust_smile"]}

    hidden = "ffffff00"
    R.slot("fx_rays", "fx", {"rays": centered(P["rays"], ORIGIN, 1.9)}, "rays", color="ffb8e800", blend="additive")
    R.slot("frame", "frame", {"frame": frame_place}, "frame")
    R.slot("glow_clip", "symbol", {"glow_clip": dict(clip=window, end="back_glow")}, "glow_clip")
    R.slot("back_glow", "body", {"glow": centered(P["glow"], (205, 150), 3.0)}, "glow", color="ff8ad855", blend="additive")
    # laurels hug the frame but sit behind her and the goblet, as in the finished art
    R.slot("laurel_l", "laurel_l", {"laurel_l": place(P["laurel_l"], (620, 583), laurel_l_at, 0.78, rotation=6)}, "laurel_l")
    R.slot("laurel_r", "laurel_r", {"laurel_r": place(P["laurel_r"], (790, 583), laurel_r_at, 0.78, rotation=-6)}, "laurel_r")
    R.slot("bust", "body", busts, "bust_smile")
    R.slot("face", "body", faces)  # empty in setup: the smile lives on the bust plate
    R.slot("goblet", "goblet", {"goblet": place(P["goblet"], (430, 585), goblet_at, 0.78)}, "goblet")
    R.slot("splash_1", "splash", {"splash_b": centered(P["splash_b"], (splash_at[0] + 4, splash_at[1] - 30), 0.5)}, "splash_b", color=hidden)
    R.slot("splash_2", "splash2", {"splash_a": centered(P["splash_a"], (splash_at[0] + 22, splash_at[1] - 20), 0.42, rotation=25)}, "splash_a", color=hidden)
    R.slot("banner", "banner", {"banner": place(P["banner"], (1015, 414), (18, 276), 0.825)}, "banner")
    R.slot("banner_clip", "banner", {"banner_clip": dict(clip=[(78, 288), (309, 288), (309, 367), (78, 367)], end="banner_shine")}, "banner_clip")
    R.slot("banner_shine", "shine", {"shine": centered(P["shine"], banner_at, 1.0, rotation=-18)}, "shine", color="fff3c400", blend="additive")
    R.slot("frame_flash", "frame", {"frame": frame_place}, "frame", color="ffb0e000", blend="additive")
    R.slot("medal_glow", "medal", {"medallion": centered(P["medallion"], med_at, 0.69)}, "medallion", color=hidden, blend="additive")
    R.slot("swirl_a", "swirl_a", {"fx_pink_a": centered(P["fx_pink_a"], R.world["swirl_a"], 0.62, rotation=60)}, "fx_pink_a", color=hidden, blend="additive")
    R.slot("swirl_b", "swirl_b", {"fx_pink_b": centered(P["fx_pink_b"], R.world["swirl_b"], 0.62, rotation=240)}, "fx_pink_b", color=hidden, blend="additive")
    R.slot("front_glow", "fx", {"glow": centered(P["glow"], (197, 190), 4.6)}, "glow", color="ffa8e000", blend="additive")
    for i, spot in enumerate(sparkle_spots):
        R.slot(f"sparkle{i + 1}", f"spk{i + 1}", {"sparkle": centered(P["sparkle"], spot, 0.55)}, "sparkle", color=PINK + "00", blend="additive")

    R.physics("laurel_l", rotate=0.5, inertia=0.5, strength=160, damping=0.8, mass=1.0)
    R.physics("laurel_r", rotate=0.5, inertia=0.5, strength=160, damping=0.8, mass=1.0)
    R.physics("goblet", rotate=0.25, inertia=0.4, strength=140, damping=0.85, mass=1.0)

    ref = S.rgba[0:392, 0:385]
    render_setup(R, os.path.join(DEBUG, "setup.png"), ref)
    render_setup(R, os.path.join(DEBUG, "setup_fx.png"), ref, reveal={"splash_1", "splash_2"})
    render_faces(busts["bust_smile"], faces, os.path.join(DEBUG, "faces.png"))
    Image.fromarray(P["frame"].rgba).save(os.path.join(DEBUG, "frame_rebuilt.png"))
    zoom(os.path.join(DEBUG, "setup.png"), (90, 70 + 120, 90 + 380, 70 + 340), 3, os.path.join(DEBUG, "setup_lower_zoom.png"))

    skeleton = write_skeleton(R, "odysseus-bonus-v1", ("impact", "cheer", "settled"))
    skeleton["animations"] = {"idle": anim_idle(), "land": anim_land(), "connect": anim_connect()}
    write_outputs(NAME, ASSETS, list(P.values()), skeleton)


# --------------------------------------------------------------------------
# Animations
# --------------------------------------------------------------------------
def splash_burst(slot, t0, dur, rise, grow=1.0):
    """Wine pops out of the goblet: scale up, drift, fade."""
    keys = rgba((0, "ffffff00", None), (t0, "ffffff00", "out"), (t0 + 0.06, "ffffffff", "linear"), (t0 + dur * 0.55, "ffffffff", "in"), (t0 + dur, "ffffff00", None))
    return {slot: {"rgba": keys}}, {
        "scale": scale((0, 0.3, 0.3, None), (t0, 0.3, 0.3, "out"), (t0 + dur * 0.5, grow, grow, "soft"), (t0 + dur, grow * 1.08, grow * 1.08, None)),
        "translate": translate((0, 0, 0, None), (t0, 0, 0, "out"), (t0 + dur, 0, rise, None)),
    }


def anim_idle():
    T = 3.6
    bones = {
        "body": {"scale": osc2(T, 0.004, 0.012, phase=-math.pi / 2, bx=1.004, by=1.012), "rotate": osc(T, 1.1, phase=0.4)},
        "goblet": {"rotate": osc(T / 2, 2.6, phase=0.0, cycles=2), "translate": osc2(T, 1.5, 2.5, phase=1.2)},
        "laurel_l": {"rotate": osc(T, 1.8, phase=0.0)},
        "laurel_r": {"rotate": osc(T, 1.8, phase=math.pi)},
        "banner": {"translate": osc2(T, 0, 1.6, phase=0.6)},
        "shine": {"translate": translate((0, -200, 0, None), (2.7, -200, 0, "inout"), (3.3, 200, 0, None))},
    }
    slots = {
        "face": {"attachment": attach((0, None))},  # clear a face left over from land/connect
        "back_glow": {"rgba": rgba((0, "ff8ad840", "inout"), (T / 2, "ff8ad870", "inout"), (T, "ff8ad840", None))},
        "banner_shine": {"rgba": rgba((0, "fff3c400", None), (2.7, "fff3c400", "soft"), (2.88, "fff3c4d0", "linear"), (3.15, "fff3c4d0", "in"), (3.3, "fff3c400", None))},
        "medal_glow": {"rgba": rgba((0, "ffffff00", "inout"), (0.9, "ffffff00", "inout"), (1.3, "ffffff66", "inout"), (1.8, "ffffff00", None))},
    }
    for idx, t0, color in ((1, 1.0, GOLD), (8, 1.95, PINK), (3, 2.9, PINK)):
        s, b = twinkle(color, t0, 0.6, peak=0.9, grow=0.8)
        slots[f"sparkle{idx}"] = {"rgba": s}
        bones[f"spk{idx}"] = b
    return {"bones": bones, "slots": slots}


def anim_land():
    splash_slot, splash_bone = splash_burst("splash_1", 0.13, 0.6, 26, grow=0.9)
    bones = {
        "symbol": {
            "translate": translate((0, 0, 56, "in"), (0.12, 0, -7, "out"), (0.26, 0, 3, "inout"), (0.42, 0, 0, None)),
            "scale": scale((0, 0.95, 1.07, "in"), (0.12, 1.09, 0.89, "out"), (0.25, 0.97, 1.04, "inout"), (0.4, 1.01, 0.99, "inout"), (0.56, 1, 1, None)),
        },
        "body": {
            "scale": scale((0, 1, 1, None), (0.12, 1, 1, "out"), (0.2, 1.02, 0.95, "inout"), (0.42, 1, 1.02, "inout"), (0.62, 1, 1, None)),
            "rotate": rotate((0, 2, "in"), (0.12, -3, "out"), (0.32, 2.5, "inout"), (0.52, -1, "inout"), (0.72, 0, None)),
        },
        "goblet": {
            "rotate": rotate((0, 4, "in"), (0.12, -12, "out"), (0.3, 7, "inout"), (0.5, -3, "inout"), (0.72, 0, None)),
            "translate": translate((0, 0, 6, "in"), (0.12, 0, -10, "out"), (0.3, 0, 5, "inout"), (0.55, 0, 0, None)),
        },
        "splash": splash_bone,
        "laurel_l": {"rotate": rotate((0, -4, None), (0.12, -4, "out"), (0.22, 16, "inout"), (0.42, -5, "inout"), (0.62, 2, "inout"), (0.8, 0, None))},
        "laurel_r": {"rotate": rotate((0, 4, None), (0.12, 4, "out"), (0.22, -16, "inout"), (0.42, 5, "inout"), (0.62, -2, "inout"), (0.8, 0, None))},
        "banner": {
            "scale": scale((0, 1, 1, None), (0.12, 1, 1, "out"), (0.2, 1.2, 1.2, "inout"), (0.36, 0.95, 0.95, "inout"), (0.52, 1.03, 1.03, "inout"), (0.68, 1, 1, None)),
            "translate": translate((0, 0, 0, None), (0.12, 0, 0, "out"), (0.2, 0, 6, "inout"), (0.4, 0, 0, None)),
        },
        "fx": {"scale": scale((0, 0.6, 0.6, None), (0.12, 0.6, 0.6, "out"), (0.7, 1.25, 1.25, None)),
               "rotate": rotate((0, 0, None), (0.12, 0, "out"), (0.9, 24, None))},
        "shine": {"translate": translate((0, -200, 0, None), (0.22, -200, 0, "inout"), (0.62, 200, 0, None))},
    }
    slots = {
        "face": {"attachment": attach((0, "face_laugh"), (0.55, None))},
        "fx_rays": {"rgba": rgba((0, "ffb8e800", None), (0.11, "ffb8e800", "out"), (0.16, "ffb8e8cc", "soft"), (0.75, "ffb8e800", None))},
        "frame_flash": {"rgba": rgba((0, "ffb0e000", None), (0.11, "ffb0e000", "out"), (0.14, "ffb0e070", "soft"), (0.42, "ffb0e000", None))},
        "medal_glow": {"rgba": rgba((0, "ffffff00", None), (0.12, "ffffff00", "out"), (0.18, "ffffffe6", "soft"), (0.6, "ffffff00", None))},
        "front_glow": {"rgba": rgba((0, "ffa8e000", None), (0.11, "ffa8e000", "out"), (0.14, "ffa8e040", "soft"), (0.36, "ffa8e000", None))},
        "banner_shine": {"rgba": rgba((0, "fff3c400", None), (0.22, "fff3c400", "soft"), (0.32, "fff3c4e0", "linear"), (0.5, "fff3c4e0", "in"), (0.62, "fff3c400", None))},
    }
    slots.update(splash_slot)
    for idx, t0, color in ((4, 0.13, PINK), (5, 0.15, PINK), (6, 0.14, GOLD), (7, 0.16, GOLD), (2, 0.2, PINK), (3, 0.19, PINK)):
        s, b = twinkle(color, t0, 0.55, peak=1.0, spin=120, grow=1.0)
        slots[f"sparkle{idx}"] = {"rgba": s}
        bones[f"spk{idx}"] = b
    return {"bones": bones, "slots": slots, "events": [{"time": 0.12, "name": "impact"}, {"time": 0.8, "name": "settled"}]}


def anim_connect():
    D = 1.9
    # giggle: quick small bounces while the eyes are closed
    giggle_y = [(0, 0, 0, "inout"), (0.15, 0, -4, "out"), (0.34, 0, 7, "inout")]
    giggle_r = [(0, 0, "inout"), (0.15, 1.5, "out"), (0.34, -3, "inout")]
    t, flip = 0.34, 1
    while t + 0.11 <= 1.2:
        t += 0.11
        giggle_y.append((t, 0, 7 + 3.5 * flip, "inout"))
        giggle_r.append((t, -3 + 1.8 * flip, "inout"))
        flip = -flip
    giggle_y += [(1.45, 0, -2, "inout"), (1.65, 0, 1, "inout"), (D, 0, 0, None)]
    giggle_r += [(1.45, 1.2, "inout"), (1.65, -0.4, "inout"), (D, 0, None)]

    splash1_slot, splash1_bone = splash_burst("splash_1", 0.36, 0.62, 34, grow=1.15)
    splash2_slot, splash2_bone = splash_burst("splash_2", 0.78, 0.55, 26, grow=1.0)
    bones = {
        "symbol": {
            "scale": scale((0, 1, 1, "inout"), (0.15, 1.04, 0.95, "out"), (0.34, 1.1, 1.1, "inout"), (0.55, 1.06, 1.06, "inout"),
                           (0.95, 1.08, 1.08, "inout"), (1.3, 1.06, 1.06, "inout"), (1.55, 0.98, 0.98, "inout"), (1.72, 1.01, 1.01, "inout"), (D, 1, 1, None)),
            "translate": translate((0, 0, 0, "inout"), (0.15, 0, -4, "out"), (0.34, 0, 9, "inout"), (1.3, 0, 6, "inout"), (1.58, 0, -2, "inout"), (D, 0, 0, None)),
        },
        "body": {"translate": translate(*giggle_y), "rotate": rotate(*giggle_r)},
        # "Cheers!": dip, then thrust the goblet toward the viewer (scale + tilt) with a toast wobble.
        # Lift stays small: the forearm is cut off below the wrist and must stay behind the banner.
        "goblet": {
            "translate": translate((0, 0, 0, "inout"), (0.15, 3, -6, "out"), (0.36, 10, 12, "inout"), (0.7, 9, 9, "inout"), (1.0, 10, 11, "inout"),
                                   (1.3, 9, 9, "inout"), (1.62, -1, -2, "inout"), (D, 0, 0, None)),
            "scale": scale((0, 1, 1, "inout"), (0.15, 0.96, 0.96, "out"), (0.36, 1.2, 1.2, "inout"), (0.7, 1.12, 1.12, "inout"), (1.0, 1.16, 1.16, "inout"),
                           (1.3, 1.12, 1.12, "inout"), (1.62, 0.99, 0.99, "inout"), (D, 1, 1, None)),
            "rotate": rotate((0, 0, "inout"), (0.15, 9, "out"), (0.36, -16, "inout"), (0.52, -6, "inout"), (0.68, -13, "inout"), (0.86, -7, "inout"),
                             (1.05, -12, "inout"), (1.3, -8, "inout"), (1.62, 3, "inout"), (D, 0, None)),
        },
        "splash": splash1_bone,
        "splash2": splash2_bone,
        "laurel_l": {"rotate": rotate((0, 0, "inout"), (0.15, -3, "out"), (0.36, 14, "inout"), (0.64, 6, "inout"), (0.92, 12, "inout"), (1.2, 6, "inout"), (1.55, -2, "inout"), (D, 0, None))},
        "laurel_r": {"rotate": rotate((0, 0, "inout"), (0.15, 3, "out"), (0.36, -14, "inout"), (0.64, -6, "inout"), (0.92, -12, "inout"), (1.2, -6, "inout"), (1.55, 2, "inout"), (D, 0, None))},
        "banner": {
            "scale": scale((0, 1, 1, "inout"), (0.17, 0.94, 0.94, "out"), (0.38, 1.16, 1.16, "inout"), (0.58, 1.06, 1.06, "inout"),
                           (0.9, 1.1, 1.1, "inout"), (1.2, 1.06, 1.06, "inout"), (1.55, 0.98, 0.98, "inout"), (D, 1, 1, None)),
            "translate": translate((0, 0, 0, "inout"), (0.38, 0, 4, "inout"), (1.55, 0, 0, None)),
        },
        "fx": {"rotate": rotate((0, 0, "linear"), (D, 60, None)), "scale": scale((0, 0.7, 0.7, "out"), (0.4, 1.15, 1.15, "inout"), (1.2, 1.05, 1.05, "inout"), (D, 1.25, 1.25, None))},
        "swirl_orbit": {"rotate": rotate((0, 60, None), (0.24, 60, "out"), (1.3, -250, None))},
        "shine": {"translate": translate((0, -200, 0, None), (0.38, -200, 0, "inout"), (0.82, 200, 0, None), (1.02, -200, 0, "inout"), (1.46, 200, 0, None))},
    }
    slots = {
        "face": {"attachment": attach((0, None), (0.16, "face_laugh"), (1.22, "face_wink"), (1.5, None))},
        "fx_rays": {"rgba": rgba((0, "ffb8e800", "out"), (0.34, "ffb8e8e0", "inout"), (1.2, "ffb8e899", "inout"), (D, "ffb8e800", None))},
        "frame_flash": {"rgba": rgba((0, "ffb0e000", None), (0.32, "ffb0e000", "out"), (0.36, "ffb0e060", "soft"), (0.72, "ffb0e000", None))},
        "medal_glow": {"rgba": rgba((0, "ffffff00", "out"), (0.36, "fffffff0", "inout"), (0.82, "ffffff55", "inout"), (1.12, "ffffffb0", "inout"), (D, "ffffff00", None))},
        "front_glow": {"rgba": rgba((0, "ffa8e000", None), (0.32, "ffa8e000", "out"), (0.36, "ffa8e03c", "soft"), (0.62, "ffa8e000", None))},
        "back_glow": {"rgba": rgba((0, "ff8ad840", "out"), (0.38, "ffa0e0e0", "inout"), (1.3, "ffa0e099", "inout"), (D, "ff8ad840", None))},
        "swirl_a": {"rgba": rgba((0, "ffffff00", None), (0.24, "ffffff00", "out"), (0.42, "ffffffd8", "inout"), (0.92, "ffffff90", "in"), (1.3, "ffffff00", None))},
        "swirl_b": {"rgba": rgba((0, "ffffff00", None), (0.28, "ffffff00", "out"), (0.46, "ffffffd8", "inout"), (0.97, "ffffff90", "in"), (1.3, "ffffff00", None))},
        "banner_shine": {"rgba": rgba((0, "fff3c400", None), (0.38, "fff3c400", "soft"), (0.48, "fff3c4f0", "linear"), (0.7, "fff3c4f0", "in"), (0.82, "fff3c400", "stepped"),
                                      (1.02, "fff3c400", "soft"), (1.12, "fff3c4f0", "linear"), (1.34, "fff3c4f0", "in"), (1.46, "fff3c400", None))},
    }
    slots.update(splash1_slot)
    slots.update(splash2_slot)
    pops = [(1, 0.36, 1.2, GOLD), (2, 0.44, 1.0, PINK), (3, 0.52, 1.0, PINK), (4, 0.64, 1.1, PINK), (5, 0.72, 1.1, GOLD),
            (6, 0.86, 0.9, PINK), (7, 0.94, 0.9, PINK), (8, 1.08, 0.8, GOLD)]
    for idx, t0, grow, color in pops:
        s, b = twinkle(color, t0, 0.5, peak=1.0, spin=140, grow=grow)
        slots[f"sparkle{idx}"] = {"rgba": s}
        bones[f"spk{idx}"] = b
    return {"bones": bones, "slots": slots, "events": [{"time": 0.36, "name": "cheer"}]}


if __name__ == "__main__":
    build()
