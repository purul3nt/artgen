#!/usr/bin/env python3
"""The twelve regular reel symbols, built on symbol_kit.

Eight square symbols (sheets 02_31_21 PM 1-8) and four round DZ medallions
(sheets 02_48_33 PM 1-4). Each function cuts its parts, fits them onto the
finished symbol drawn on the same sheet, sets pivots and draw order, and adds its
own motion on top of the kit's shared idle / land / connect.

Usage:  python build_symbols.py [name ...]      (no names = all twelve)
"""
import math
import sys

import numpy as np

from spine_rig import keep_largest, osc, osc2, remap_alpha, rgba, rotate, scale, translate, trim, twinkle
from symbol_kit import Fit, Kit, circle

SQ = "02_31_21 PM ({})"
DZ = "02_48_33 PM ({})"
HIDDEN = "ffffff00"


def rng(a, b, step):
    return tuple(range(a, b + 1, step))


def near(cx, cy, r=70):
    return (cx - r, cy - r, cx + r, cy + r)


def center(k, r=40):
    """Frames sit centred on their finished symbol; without this the search can slide them off-canvas."""
    return near(k.ref.shape[1] / 2, k.ref.shape[0] / 2, r)


def square_window(f, inset=0.085):
    cx, cy = f.center
    w, h = f.w0 * f.scale, f.h0 * f.scale
    ix, iy = w * inset, h * inset
    return [(cx - w / 2 + ix, cy - h / 2 + iy), (cx + w / 2 - ix, cy - h / 2 + iy), (cx + w / 2 - ix, cy + h / 2 - iy), (cx - w / 2 + ix, cy + h / 2 - iy)]


def mirror(keys):
    """Negate rotate keys (time, value, ease) for the opposite side."""
    return tuple((t, -v, e) for t, v, e in keys)


def spring(amp, t0=0.12, decay=(1.0, -0.5, 0.2, 0)):
    """Rotation that is kicked at t0 and rings out."""
    keys = [(0, 0, None), (t0, 0, "out")]
    t = t0
    for i, f in enumerate(decay):
        t += 0.1 + 0.04 * i
        keys.append((t, amp * f, "inout" if f else None))
    return tuple(keys)


def combine(*pairs):
    bones, slots = {}, {}
    for b, s in pairs:
        for n, props in b.items():
            bones.setdefault(n, {}).update(props)
        for n, props in s.items():
            slots.setdefault(n, {}).update(props)
    return bones, slots


def burst(name, t0, dur, dx=0.0, dy=30.0, s0=0.3, s1=1.0, spin=0, color="ffffff"):
    """A splash / flash sprite pops out of its bone: grow, drift, fade. Slot and bone share `name`."""
    bones = {name: {"scale": scale((0, s0, s0, None), (t0, s0, s0, "out"), (t0 + dur * 0.5, s1, s1, "soft"), (t0 + dur, s1 * 1.08, s1 * 1.08, None)),
                    "translate": translate((0, 0, 0, None), (t0, 0, 0, "out"), (t0 + dur, dx, dy, None))}}
    if spin:
        bones[name]["rotate"] = rotate((0, 0, None), (t0, 0, "linear"), (t0 + dur, spin, None))
    slots = {name: {"rgba": rgba((0, color + "00", None), (t0, color + "00", "out"), (t0 + 0.06, color + "ff", "linear"),
                                 (t0 + dur * 0.55, color + "ff", "in"), (t0 + dur, color + "00", None))}}
    return bones, slots


def throw(name, t0, dur, dx, up, fall, spin=200, color="ffffff"):
    """Something flies out of its bone on an arc (up, then falls), spinning, fading at the end."""
    bones = {name: {"translate": translate((0, 0, 0, None), (t0, 0, 0, "out"), (t0 + dur * 0.4, dx * 0.55, up, "in"), (t0 + dur, dx, fall, None)),
                    "rotate": rotate((0, 0, None), (t0, 0, "linear"), (t0 + dur, spin, None)),
                    "scale": scale((0, 0.6, 0.6, None), (t0, 0.6, 0.6, "out"), (t0 + 0.14, 1, 1, None))}}
    slots = {name: {"rgba": rgba((0, color + "00", None), (t0, color + "00", "stepped"), (t0 + 0.01, color + "ff", "linear"),
                                 (t0 + dur * 0.7, color + "ff", "in"), (t0 + dur, color + "00", None))}}
    return bones, slots


def glints(k, parent, points, color="ffffff", size=0.5):
    """Extra sparkle sprites pinned to a moving part (tips, rims, gems)."""
    names = []
    for i, p in enumerate(points):
        n = f"glint{i + 1}"
        k.bone(n, parent, p)
        k.layer(n, n, k.at("sparkle", p, size * k.k), color=color + "00", blend="additive")
        names.append(n)
    return names


def glint_keys(names, times, color="ffffff", dur=0.55, grow=1.0):
    bones, slots = {}, {}
    for n, t in zip(names, times):
        s, b = twinkle(color, t, dur, peak=1.0, spin=90, grow=grow)
        slots[n] = {"rgba": s}
        bones[n] = b
    return bones, slots


def squash(t0=0.12, amt=0.08):
    return scale((0, 1, 1, None), (t0, 1, 1, "out"), (t0 + 0.08, 1 + amt, 1 - amt * 1.3, "inout"), (t0 + 0.24, 1 - amt * 0.5, 1 + amt * 0.6, "inout"), (t0 + 0.42, 1, 1, None))


def pulse(t0=0.12, amt=0.06):
    """Uniform grow-and-settle: keeps a shape's silhouette (no rotation, no squash)."""
    return scale((0, 1, 1, None), (t0, 1, 1, "out"), (t0 + 0.1, 1 + amt, 1 + amt, "inout"), (t0 + 0.28, 1 - amt * 0.3, 1 - amt * 0.3, "inout"), (t0 + 0.46, 1, 1, None))


def anchored(part, uv, target, s, rotation=0.0, flip=False):
    """Placement whose normalised part point `uv` lands on ref point `target`."""
    px, py = Fit(part, (0, 0), s, rotation, flip).pt(*uv)
    return Fit(part, (target[0] - px, target[1] - py), s, rotation, flip)


# ==========================================================================
# Square symbols
# ==========================================================================
def helmet():
    k = Kit("helmet", SQ.format(1), (51, 53, 428, 419))
    k.palette.update(rays="ffcf6a", back="ff9a4a", flash="ffe29a", front="ffd890", sparks=("fff2c0", "ffd27a"))
    k.part("frame", (523, 53, 417, 418))
    k.part("crest", (966, 171, 453, 495))
    k.part("helmet", (23, 506, 519, 553))
    ff = k.fit("frame", (0.95, 1.05), search=center(k))
    k.frame(ff, square_window(ff))
    fh = k.fit("helmet", (0.35, 0.9), rots=(-8, -4, 0, 4, 8))
    fc = k.fit("crest", (0.6, 0.8), rots=rng(-12, 30, 6), search=near(196, 180, 60))
    k.bone("helmet", "content", fh.pt(0.5, 0.9))
    k.bone("crest", "helmet", fc.pt(0.4, 0.5))
    k.layer("crest", "crest", fc)
    k.layer("helmet", "helmet", fh)
    g = glints(k, "helmet", [fh.pt(0.3, 0.2), fh.pt(0.62, 0.55)], "fff6d0", 0.6)
    T, D, s = k.T, k.D, k.k
    b, sl = glint_keys(g, (T * 0.2, T * 0.62), "fff6d0")
    # the crest is part of the helmet: it only ever moves with it
    k.add("idle", bones={"helmet": {"rotate": osc(T, 1.2)}, **b}, slots=sl)
    k.add("land", bones={
        "helmet": {"rotate": rotate((0, 6, "in"), (0.12, -5, "out"), (0.3, 3, "inout"), (0.5, -1, "inout"), (0.7, 0, None)), "scale": squash()}})
    b, sl = glint_keys(g, (0.34, 0.5), "fff6d0", grow=1.3)
    k.add("connect", bones={
        "helmet": {"rotate": rotate((0, 0, "inout"), (0.14, 5, "out"), (0.34, -10, "inout"), (0.56, 6, "inout"), (0.78, -6, "inout"), (1.0, 3, "inout"), (1.3, -2, "inout"), (1.6, 0, None)),
                   "translate": translate((0, 0, 0, "inout"), (0.14, 0, -6 * s, "out"), (0.34, 0, 14 * s, "inout"), (1.3, 0, 10 * s, "inout"), (1.6, 0, 0, None)),
                   "scale": scale((0, 1, 1, "inout"), (0.34, 1.06, 1.06, "inout"), (1.3, 1.04, 1.04, "inout"), (1.6, 1, 1, None))},
        **b}, slots=sl)
    return k


def laurel():
    k = Kit("laurel", SQ.format(2), (33, 36, 425, 409))
    k.palette.update(rays="ffe08a", back="ffd060", flash="fff0b0", front="ffe6a0", sparks=("fff6c8", "ffe08a"))
    k.part("frame", (488, 36, 421, 409))
    k.part("branch", (741, 422, 375, 388))
    k.part("leaf_pair", (214, 874, 273, 180))
    k.part("leaf", (567, 901, 267, 109))
    k.part("sprig", (1216, 128, 200, 298))
    ff = k.fit("frame", (0.95, 1.05), search=center(k))
    k.frame(ff, square_window(ff))
    # a U: two mirrored branches rise from the bottom centre, one up each side. They never wave, only pulse.
    fb = anchored(k.parts["branch"], (0.05, 0.95), (226, 352), 0.55, rotation=14)
    fa = anchored(k.parts["branch"], (0.05, 0.95), (200, 352), 0.55, rotation=-14, flip=True)
    k.bone("branch_b", "content", fb.pt(0.05, 0.95))
    k.bone("branch_a", "content", fa.pt(0.05, 0.95))
    fly = [("fly1", "leaf", fa.pt(0.75, 0.2)), ("fly2", "leaf_pair", fb.pt(0.8, 0.3)), ("fly3", "sprig", fa.pt(0.45, 0.45))]
    for n, _, p in fly:
        k.bone(n, "content", p)
    k.layer("branch_b", "branch_b", {"branch": fb})
    k.layer("branch_a", "branch_a", {"branch": fa})
    for n, part, p in fly:
        k.layer(n, n, k.at(part, p, fa.scale * 0.8, rotation=20), color=HIDDEN)
    g = glints(k, "content", [fa.pt(0.9, 0.1), fb.pt(0.9, 0.1), fa.pt(0.55, 0.45), fb.pt(0.55, 0.45)], "fff6d0", 0.55)
    T, D, s = k.T, k.D, k.k
    # idle keeps the U (no waving): the branches breathe in turn, bob gently and catch rolling glints
    b, sl = glint_keys(g, (T * 0.1, T * 0.33, T * 0.55, T * 0.78), "fff6d0")  # last glint ends before the loop point
    k.add("idle", bones={
        "branch_a": {"scale": osc2(T, 0.035, 0.035, phase=-math.pi / 2, bx=1.02, by=1.02)},
        "branch_b": {"scale": osc2(T, 0.035, 0.035, phase=math.pi / 2, bx=1.02, by=1.02)},
        "content": {"translate": osc2(T, 0, 3.5 * s, phase=0.0)}, **b}, slots=sl)
    k.add("land", bones={"branch_a": {"scale": pulse(0.12, 0.05)}, "branch_b": {"scale": pulse(0.12, 0.05)}, "content": {"scale": squash()}})
    grow = scale((0, 1, 1, "inout"), (0.36, 1.07, 1.07, "inout"), (1.2, 1.04, 1.04, "inout"), (D, 1, 1, None))
    b, sl = combine(throw("fly1", 0.36, 1.0, -80 * s, 60 * s, -50 * s), throw("fly2", 0.5, 1.05, 90 * s, 70 * s, -40 * s, spin=-240),
                    throw("fly3", 0.66, 1.0, 40 * s, 90 * s, -20 * s, spin=160), glint_keys(g, (0.36, 0.46), "fff6d0", grow=1.3))
    k.add("connect", bones={"branch_a": {"scale": grow}, "branch_b": {"scale": grow}, **b}, slots=sl)
    return k


def ship():
    k = Kit("ship", SQ.format(3), (30, 42, 429, 429))
    k.palette.update(rays="cfeeff", back="7cc8ff", flash="d8f0ff", front="c8e8ff", sparks=("ffffff", "fff2c0"))
    k.part("frame", (484, 42, 421, 429))
    k.part("mast", (933, 71, 118, 584))
    k.part("sail", (974, 104, 450, 472))
    k.part("hull", (35, 483, 748, 429))
    k.part("wave", (671, 853, 630, 193), floor=10)
    k.part("splash_a", (778, 677, 369, 156), floor=10)
    k.part("splash_b", (1157, 634, 272, 165), floor=10)
    ff = k.fit("frame", (0.95, 1.05), search=center(k))
    win = square_window(ff)
    k.frame(ff, win)
    fhull = k.fit("hull", (0.4, 0.55), rots=rng(-10, 10, 5), search=near(213, 258, 50))
    fsail = k.fit("sail", (0.5, 0.72), rots=rng(-10, 10, 5), search=near(186, 150, 50))
    fmast = k.fit("mast", (0.36, 0.5), rots=rng(-8, 8, 4), search=near(166, 168, 50))
    fwave = k.fit("wave", (0.4, 0.7), search=near(296, 360, 60))
    k.bone("boat", "content", fhull.pt(0.5, 0.85))
    k.bone("mast", "boat", fmast.pt(0.5, 0.9))
    k.bone("sail", "boat", fsail.pt(0.35, 0.1))
    k.bone("wave", "content", fwave.center)
    bow, stern = fhull.pt(0.85, 0.7), fhull.pt(0.2, 0.75)
    k.bone("splash_a", "content", bow)
    k.bone("splash_b", "content", stern)
    k.clip("ship_clip", win, "splash_b")
    k.layer("mast", "mast", fmast)
    k.layer("sail", "sail", fsail)
    k.layer("hull", "boat", fhull)
    k.layer("wave", "wave", fwave)
    k.layer("splash_a", "splash_a", k.at("splash_a", bow, fwave.scale * 0.8), color=HIDDEN)
    k.layer("splash_b", "splash_b", k.at("splash_b", stern, fwave.scale * 0.8), color=HIDDEN)
    T, D, s = k.T, k.D, k.k
    k.add("idle", bones={"boat": {"rotate": osc(T, 2.2), "translate": osc2(T, 0, 3 * s, phase=0.8)},
                         "sail": {"scale": osc2(T, 0.035, 0.01, phase=0.4, bx=1, by=1)},
                         "wave": {"translate": osc2(T, 7 * s, 2 * s, phase=math.pi)}})
    b, sl = combine(burst("splash_a", 0.13, 0.6, dy=22 * s, s1=1.0), burst("splash_b", 0.16, 0.55, dy=16 * s, s1=0.8))
    k.add("land", bones={"boat": {"translate": translate((0, 0, 18 * s, "in"), (0.14, 0, -8 * s, "out"), (0.34, 0, 3 * s, "inout"), (0.56, 0, 0, None)),
                                  "rotate": rotate((0, -4, "in"), (0.14, 5, "out"), (0.34, -3, "inout"), (0.6, 1, "inout"), (0.8, 0, None))}, **b}, slots=sl)
    b, sl = combine(burst("splash_a", 0.38, 0.62, dy=34 * s, s1=1.2), burst("splash_b", 0.9, 0.6, dx=-10 * s, dy=26 * s, s1=1.0))
    k.add("connect", bones={
        "boat": {"translate": translate((0, 0, 0, "inout"), (0.14, -6 * s, -4 * s, "out"), (0.4, 12 * s, 8 * s, "inout"), (0.7, 10 * s, 4 * s, "inout"), (1.0, 12 * s, 8 * s, "inout"),
                                        (1.3, 9 * s, 4 * s, "inout"), (D - 0.25, -2 * s, -2 * s, "inout"), (D, 0, 0, None)),
                 "rotate": rotate((0, 0, "inout"), (0.14, -3, "out"), (0.4, 7, "inout"), (0.7, 2, "inout"), (1.0, 6, "inout"), (1.3, 1, "inout"), (D - 0.25, -1.5, "inout"), (D, 0, None))},
        "sail": {"scale": scale((0, 1, 1, "inout"), (0.4, 1.14, 1.02, "inout"), (0.7, 1.06, 1, "inout"), (1.0, 1.12, 1.02, "inout"), (D, 1, 1, None))},
        "wave": {"translate": translate((0, 0, 0, "inout"), (0.4, -14 * s, 4 * s, "inout"), (1.2, -8 * s, 2 * s, "inout"), (D, 0, 0, None))},
        **b}, slots=sl)
    return k


def amphora():
    k = Kit("amphora", SQ.format(4), (63, 53, 435, 418))
    k.palette.update(rays="ffd27a", back="6aa8ff", flash="c8dcff", front="a8c8ff", sparks=("fff2c0", "d8e6ff"))
    k.part("frame", (536, 52, 427, 419))
    k.part("handle_l", (131, 588, 177, 241))
    k.part("neck", (348, 495, 318, 124))
    k.part("handle_r", (712, 588, 174, 242))
    k.part("body", (304, 628, 410, 326))
    k.part("base", (349, 958, 313, 91))
    k.part("swoosh_a", (993, 902, 271, 115), floor=0, grow=10)
    k.part("swoosh_b", (1150, 363, 235, 84), floor=0, grow=10)
    ff = k.fit("frame", (0.95, 1.05), search=center(k))
    k.frame(ff, square_window(ff))
    fb = k.fit("body", (0.3, 0.8), rots=(-4, 0, 4), search=(150, 180, 270, 310))
    fn = k.fit("neck", (0.3, 0.8), rots=(-4, 0, 4), search=(160, 40, 260, 130))
    fbase = k.fit("base", (0.3, 0.8), rots=(-4, 0, 4), search=(160, 310, 260, 400))
    fhl = k.fit("handle_l", (0.3, 0.8), rots=rng(-12, 12, 4), search=(60, 90, 160, 230))
    fhr = k.fit("handle_r", (0.3, 0.8), rots=rng(-12, 12, 4), search=(260, 90, 360, 230))
    cx, cy = fb.center
    k.bone("vase", "content", fbase.pt(0.5, 0.9))
    k.bone("body", "vase", fb.center)
    k.bone("neck", "body", fn.pt(0.5, 1.0))
    k.bone("handle_l", "body", fhl.pt(0.8, 0.2))
    k.bone("handle_r", "body", fhr.pt(0.2, 0.2))
    k.bone("orbit", "content", (cx, cy))
    k.bone("swoosh_a", "orbit", (cx - 120 * k.k, cy))
    k.bone("swoosh_b", "orbit", (cx + 120 * k.k, cy - 20 * k.k))
    k.layer("handle_l", "handle_l", fhl)
    k.layer("handle_r", "handle_r", fhr)
    k.layer("base", "vase", fbase)
    k.layer("neck", "neck", fn)
    k.layer("body", "body", fb)
    k.layer("swoosh_a", "swoosh_a", k.at("swoosh_a", (cx - 120 * k.k, cy), 0.55 * k.k, rotation=80), color=HIDDEN, blend="additive")
    k.layer("swoosh_b", "swoosh_b", k.at("swoosh_b", (cx + 120 * k.k, cy - 20 * k.k), 0.6 * k.k, rotation=-100), color=HIDDEN, blend="additive")
    T, D, s = k.T, k.D, k.k
    # The vase is several pieces (base, body, neck, handles): they only ever move together through the
    # "vase" bone (pivot at the foot), otherwise gaps open between them and it looks broken.
    g = glints(k, "vase", [fn.pt(0.3, 0.3), fb.pt(0.3, 0.35), fhr.pt(0.5, 0.2)], "fff6d0", 0.55)
    b, sl = glint_keys(g, (T * 0.2, T * 0.5, T * 0.8), "fff6d0")
    k.add("idle", bones={"vase": {"rotate": osc(T, 1.2), "scale": osc2(T, 0.006, 0.012, phase=-math.pi / 2, bx=1.006, by=1.012)}, **b}, slots=sl)
    k.add("land", bones={"vase": {"rotate": rotate((0, 4, "in"), (0.12, -4, "out"), (0.3, 3, "inout"), (0.5, -1, "inout"), (0.7, 0, None)), "scale": squash(amt=0.07)}})
    fade = lambda t0: rgba((0, "ffffff00", None), (t0, "ffffff00", "out"), (t0 + 0.12, "ffffffff", "inout"), (t0 + 0.8, "ffffffc0", "in"), (t0 + 1.1, "ffffff00", None))
    b, sl = glint_keys(g, (0.36, 0.46, 0.56), "fff6d0", grow=1.3)
    k.add("connect", bones={
        "vase": {"translate": translate((0, 0, 0, "inout"), (0.14, 0, -4 * s, "out"), (0.36, 0, 22 * s, "inout"), (0.9, 0, 18 * s, "inout"), (1.3, 0, 20 * s, "inout"), (1.56, 0, -3 * s, "inout"), (D, 0, 0, None)),
                 "rotate": rotate((0, 0, "inout"), (0.36, -9, "inout"), (0.54, 8, "inout"), (0.72, -6, "inout"), (0.9, 4, "inout"), (1.1, -2, "inout"), (1.4, 0, None)),
                 "scale": scale((0, 1, 1, "inout"), (0.14, 1.06, 0.92, "out"), (0.36, 0.96, 1.06, "inout"), (0.6, 1, 1, "inout"), (1.56, 1.05, 0.94, "inout"), (D, 1, 1, None))},
        "orbit": {"rotate": rotate((0, 0, None), (0.3, 0, "linear"), (1.4, -320, None))}, **b},
        slots={"swoosh_a": {"rgba": fade(0.3)}, "swoosh_b": {"rgba": fade(0.38)}, **sl})
    return k


def chalice():
    k = Kit("chalice", SQ.format(5), (25, 43, 429, 424))
    k.palette.update(rays="ffb0c8", back="ff4f7a", flash="ffd0dc", front="ff9ab4", sparks=("fff2c0", "ffc0d0"))
    k.part("frame", (482, 43, 439, 423))
    k.part("bowl", (21, 502, 677, 399))
    k.part("stem", (574, 697, 360, 347))
    k.part("gem", (901, 748, 124, 120))
    k.part("splash_big", (935, 62, 488, 239))
    k.part("splash_arc", (948, 315, 476, 181))
    for i, box in enumerate([(1173, 680, 111, 137), (1300, 608, 118, 81), (1353, 706, 67, 135), (1099, 730, 72, 100)]):
        k.part(f"drop{i + 1}", box)
    ff = k.fit("frame", (0.95, 1.05), search=center(k))
    k.frame(ff, square_window(ff))
    fbowl = k.fit("bowl", (0.3, 0.8), rots=rng(-12, 12, 4), search=(160, 150, 290, 280))
    fstem = k.fit("stem", (0.25, 0.8), rots=rng(-8, 8, 4), search=(170, 280, 300, 400))
    fgem = k.fit("gem", (0.2, 0.8), search=(180, 290, 290, 390))
    fbig = k.fit("splash_big", (0.5, 0.8), rots=rng(-30, 30, 6), flips=(False, True), search=near(250, 90, 60))
    farc = k.fit("splash_arc", (0.45, 0.75), rots=rng(-40, 40, 10), flips=(False, True), search=near(75, 200, 60))
    k.bone("cup", "content", fstem.pt(0.5, 0.95))
    k.bone("bowl", "cup", fbowl.center)
    rim = fbowl.pt(0.55, 0.12)
    k.bone("wine", "bowl", rim)
    k.bone("gem", "cup", fgem.center)
    drops = [("drop1", rim, (-70, 70, -90)), ("drop2", rim, (80, 60, -80)), ("drop3", rim, (-30, 90, -60)), ("drop4", rim, (40, 100, -50))]
    for n, p, _ in drops:
        k.bone(n, "bowl", p)
    k.layer("stem", "cup", fstem)
    k.layer("gem_glow", "gem", fgem, color="ffffff00", blend="additive")
    k.layer("bowl", "bowl", fbowl)
    k.layer("splash_arc", "wine", farc)
    k.layer("splash_big", "wine", fbig)
    for n, p, _ in drops:
        k.layer(n, n, k.at(n, p, fbowl.scale * 0.9), color=HIDDEN)
    T, D, s = k.T, k.D, k.k
    gem_pulse = lambda *ts: rgba(*[item for t in ts for item in ((t, "ffffff00", "out"), (t + 0.15, "ffffffd0", "in"), (t + 0.5, "ffffff00", None))])
    k.add("idle", bones={"cup": {"rotate": osc(T, 1.2)}, "wine": {"scale": osc2(T, 0.025, 0.05, phase=0.5, bx=1, by=1)}},
          slots={"gem_glow": {"rgba": gem_pulse(T * 0.45)}})
    b, sl = combine(*[throw(n, 0.14 + 0.03 * i, 0.7, dx * s, up * s, fall * s) for i, (n, _, (dx, up, fall)) in enumerate(drops[:2])])
    k.add("land", bones={"cup": {"scale": squash(), "rotate": rotate((0, 3, "in"), (0.12, -3, "out"), (0.3, 2, "inout"), (0.5, 0, None))},
                         "wine": {"scale": scale((0, 1, 1, None), (0.12, 1, 1, "out"), (0.22, 1.08, 1.3, "inout"), (0.42, 0.97, 0.92, "inout"), (0.62, 1, 1, None))}, **b},
          slots={"gem_glow": {"rgba": gem_pulse(0.12)}, **sl})
    b, sl = combine(*[throw(n, 0.4 + 0.15 * i, 0.8, dx * s * 1.2, up * s * 1.2, fall * s) for i, (n, _, (dx, up, fall)) in enumerate(drops)])
    k.add("connect", bones={
        "cup": {"rotate": rotate((0, 0, "inout"), (0.14, 4, "out"), (0.36, -12, "inout"), (0.6, -8, "inout"), (0.9, -11, "inout"), (1.2, -8, "inout"), (1.55, 2, "inout"), (D, 0, None)),
                "translate": translate((0, 0, 0, "inout"), (0.14, 0, -5 * s, "out"), (0.36, 0, 14 * s, "inout"), (1.2, 0, 10 * s, "inout"), (1.55, 0, -2 * s, "inout"), (D, 0, 0, None))},
        "wine": {"scale": scale((0, 1, 1, "inout"), (0.34, 1.3, 1.5, "inout"), (0.6, 1.12, 1.2, "inout"), (0.9, 1.28, 1.4, "inout"), (1.3, 1.08, 1.1, "inout"), (D, 1, 1, None))}, **b},
        slots={"gem_glow": {"rgba": gem_pulse(0.34, 0.95)}, **sl})
    return k


def grapes():
    k = Kit("grapes", SQ.format(6), (58, 61, 425, 415))
    k.palette.update(rays="e0b0ff", back="b060ff", flash="ecd0ff", front="d8a8ff", sparks=("f4d8ff", "ffffff"))
    k.part("frame", (519, 61, 428, 415))
    k.part("vine", (1000, 90, 392, 338))
    k.part("leaf_small", (40, 586, 222, 225))
    k.part("leaf_big", (272, 500, 269, 317))
    k.part("bunch", (551, 525, 341, 369))
    k.part("grape", (482, 887, 145, 145))
    k.part("juice", (1122, 938, 82, 91))
    ff = k.fit("frame", (0.95, 1.05), search=center(k))
    k.frame(ff, square_window(ff))
    fbunch = k.fit("bunch", (0.4, 1.0), rots=rng(-16, 16, 8), search=(140, 180, 260, 320))
    fvine = k.fit("vine", (0.38, 0.6), rots=rng(-24, 24, 8), flips=(False, True), search=near(141, 110, 50))
    fbig = k.fit("leaf_big", (0.3, 0.9), rots=rng(-30, 30, 10), flips=(False, True), search=(230, 70, 360, 200))
    fsmall = k.fit("leaf_small", (0.38, 0.6), rots=rng(-30, 30, 10), flips=(False, True), search=near(101, 175, 50))
    top = fbunch.pt(0.5, 0.04)
    k.bone("stem", "content", top)
    k.bone("bunch", "stem", top)
    k.bone("vine", "stem", fvine.center)
    k.bone("leaf_big", "stem", fbig.center)
    k.bone("leaf_small", "stem", fsmall.center)
    pops = [("grape1", fbunch.pt(0.3, 0.5), (-80, 70, -70)), ("grape2", fbunch.pt(0.7, 0.45), (90, 60, -60)), ("grape3", fbunch.pt(0.5, 0.78), (30, 90, -80)),
            ("juice1", fbunch.pt(0.4, 0.3), (-40, 80, -40)), ("juice2", fbunch.pt(0.62, 0.35), (50, 90, -50))]
    for n, p, _ in pops:
        k.bone(n, "bunch", p)
    k.layer("leaf_big", "leaf_big", fbig)
    k.layer("leaf_small", "leaf_small", fsmall)
    k.layer("bunch", "bunch", fbunch)
    k.layer("vine", "vine", fvine)
    for n, p, _ in pops:
        part = "juice" if n.startswith("juice") else "grape"
        k.layer(n, n, k.at(part, p, fbunch.scale * (0.9 if part == "juice" else 0.55)), color=HIDDEN)
    T, D, s = k.T, k.D, k.k
    # no pendulum swing from the stem (reads like a bell): the bunch bobs and squashes instead
    k.add("idle", bones={"bunch": {"translate": osc2(T, 0, 2.5 * s, phase=0.4)}, "leaf_big": {"rotate": osc(T, 2.0, phase=1.0)}, "leaf_small": {"rotate": osc(T, 2.0, phase=2.2)},
                         "vine": {"rotate": osc(T, 1.0, phase=0.5)}})
    k.add("land", bones={"bunch": {"scale": squash(amt=0.09)},
                         "leaf_big": {"rotate": rotate(*spring(8))}, "leaf_small": {"rotate": rotate(*spring(-8))}})
    jig = [(0, 1, 1, "inout"), (0.14, 1.06, 0.92, "out")]
    t, flip = 0.14, 1
    while t + 0.12 <= 1.3:
        t += 0.12
        jig.append((t, 1 - 0.04 * flip, 1 + 0.06 * flip, "inout"))
        flip = -flip
    jig += [(1.6, 1, 1, None)]
    b, sl = combine(*[throw(n, 0.36 + 0.14 * i, 0.9, dx * s, up * s, fall * s) for i, (n, _, (dx, up, fall)) in enumerate(pops)])
    k.add("connect", bones={"bunch": {"scale": scale(*jig), "translate": translate((0, 0, 0, "inout"), (0.14, 0, -4 * s, "out"), (0.36, 0, 8 * s, "inout"), (1.3, 0, 5 * s, "inout"), (1.6, 0, 0, None))},
                            "leaf_big": {"rotate": rotate(*spring(10, t0=0.3))}, "leaf_small": {"rotate": rotate(*spring(-10, t0=0.34))}, **b}, slots=sl)
    return k


def trident():
    k = Kit("trident", SQ.format(7), (35, 49, 456, 449))
    k.palette.update(rays="ffe08a", back="40f0a0", flash="d0ffe8", front="a8ffd0", sparks=("fff2c0", "c8ffe4"))
    k.part("frame", (517, 49, 459, 449))
    k.part("spear", (1067, 25, 298, 673))
    k.part("prong_l", (98, 556, 235, 438))
    k.part("prong_r", (582, 552, 240, 441))
    k.part("handle", (390, 772, 174, 282))
    ff = k.fit("frame", (0.95, 1.05), search=center(k))
    k.frame(ff, square_window(ff))
    fsp = k.fit("spear", (0.3, 0.8), rots=(-4, 0, 4), search=(170, 120, 280, 300))
    fpl = k.fit("prong_l", (0.3, 0.8), rots=rng(-15, 15, 5), search=(70, 120, 190, 280))
    fpr = k.fit("prong_r", (0.3, 0.8), rots=rng(-15, 15, 5), search=(260, 120, 380, 280))
    fha = k.fit("handle", (0.38, 0.56), rots=(-4, 0, 4), search=near(251, 395, 40))
    k.bone("trident", "content", fsp.pt(0.5, 0.85))
    k.bone("prong_l", "trident", fpl.pt(0.8, 0.9))
    k.bone("prong_r", "trident", fpr.pt(0.2, 0.9))
    k.layer("handle", "trident", fha)
    k.layer("prong_l", "prong_l", fpl)
    k.layer("prong_r", "prong_r", fpr)
    k.layer("spear", "trident", fsp)
    g = glints(k, "trident", [fsp.pt(0.5, 0.04), fpl.pt(0.45, 0.04), fpr.pt(0.55, 0.04)], "f4fff0", 0.6)
    T, D, s = k.T, k.D, k.k
    b, sl = glint_keys(g, (T * 0.15, T * 0.45, T * 0.8), "f4fff0")
    k.add("idle", bones={"trident": {"translate": osc2(T, 0, 3 * s, phase=0.5)}, "prong_l": {"rotate": osc(T, 1.0)}, "prong_r": {"rotate": osc(T, 1.0, phase=math.pi)}, **b}, slots=sl)
    vib = ((0, 0, None), (0.12, 0, "out"), (0.18, -6, "inout"), (0.26, 5, "inout"), (0.34, -3.5, "inout"), (0.42, 2.5, "inout"), (0.5, -1.5, "inout"), (0.6, 0.8, "inout"), (0.72, 0, None))
    b, sl = glint_keys(g, (0.13, 0.16, 0.19), "f4fff0", grow=1.2)
    k.add("land", bones={"trident": {"translate": translate((0, 0, 24 * s, "in"), (0.12, 0, -6 * s, "out"), (0.3, 0, 2 * s, "inout"), (0.5, 0, 0, None))},
                         "prong_l": {"rotate": rotate(*vib)}, "prong_r": {"rotate": rotate(*mirror(vib))}, **b}, slots=sl)
    spread = ((0, 0, "inout"), (0.16, -3, "out"), (0.34, 12, "inout"), (0.7, 9, "inout"), (1.0, 12, "inout"), (1.35, 8, "inout"), (1.6, -2, "inout"), (D, 0, None))
    b, sl = glint_keys(g, (0.36, 0.44, 0.52), "f4fff0", grow=1.4)
    k.add("connect", bones={
        "trident": {"translate": translate((0, 0, 0, "inout"), (0.14, 0, -10 * s, "out"), (0.34, 0, 26 * s, "inout"), (0.6, 0, 18 * s, "inout"), (1.0, 0, 22 * s, "inout"), (1.4, 0, 16 * s, "inout"), (D - 0.25, 0, -3 * s, "inout"), (D, 0, 0, None)),
                    "scale": scale((0, 1, 1, "inout"), (0.34, 1.06, 1.06, "inout"), (1.4, 1.04, 1.04, "inout"), (D, 1, 1, None))},
        "prong_l": {"rotate": rotate(*spread)}, "prong_r": {"rotate": rotate(*mirror(spread))}, **b}, slots=sl)
    return k


def olive():
    k = Kit("olive", SQ.format(8), (36, 48, 437, 435))
    k.palette.update(rays="f0f09a", back="c8e060", flash="f8ffc8", front="e8f0a0", sparks=("fff6c8", "f0ffb0"))
    k.part("frame", (504, 48, 434, 435))
    k.part("branch", (899, 69, 471, 521), min_inside=0.95)
    for n, box in [("olive1", (193, 572, 207, 212)), ("olive2", (439, 675, 196, 218)), ("olive3", (653, 626, 199, 224)),
                   ("leaf_a", (981, 558, 108, 307)), ("leaf_b", (1149, 337, 259, 124)), ("leaf_c", (1223, 710, 186, 241)), ("leaf_d", (1095, 467, 301, 226)),
                   ("leaf_e", (59, 652, 118, 199)), ("leaf_f", (867, 714, 108, 295)), ("leaf_g", (1122, 772, 112, 245))]:
        k.part(n, box)
    ff = k.fit("frame", (0.95, 1.05), search=center(k))
    k.frame(ff, square_window(ff))
    fbr = k.fit("branch", (0.35, 0.9), rots=rng(-20, 20, 5), flips=(False, True))
    leaf_rots = rng(-90, 90, 10)
    leaves = {n: k.fit(n, (0.42, 0.62), rots=leaf_rots, flips=(False, True), search=near(*c, 45)) for n, c in
              [("leaf_e", (78, 262)), ("leaf_f", (121, 208)), ("leaf_g", (266, 348)), ("leaf_a", (171, 135)), ("leaf_b", (296, 112)), ("leaf_c", (316, 160)), ("leaf_d", (331, 288))]}
    olives = {n: k.fit(n, (0.3, 0.8), rots=rng(-30, 30, 10), search=near(*c, 50)) for n, c in [("olive1", (254, 194)), ("olive2", (206, 258)), ("olive3", (166, 331))]}
    k.bone("branch", "content", fbr.pt(0.03, 0.97))
    for n, f in leaves.items():
        k.bone(n, "branch", f.center)
    k.bone("olives", "branch", olives["olive1"].pt(0.3, 0.05))
    for n, f in olives.items():
        k.bone(n, "olives", f.pt(0.35, 0.08))
    k.bone("fly", "branch", leaves["leaf_b"].center)
    for n in ("leaf_e", "leaf_f", "leaf_g"):
        k.layer(n, n, leaves[n])
    k.layer("branch", "branch", fbr)
    for n in ("leaf_a", "leaf_b", "leaf_c", "leaf_d"):
        k.layer(n, n, leaves[n])
    for n in ("olive3", "olive2", "olive1"):
        k.layer(n, n, olives[n])
    k.layer("fly", "fly", leaves["leaf_b"].moved(k=0.9), color=HIDDEN)
    T, D, s = k.T, k.D, k.k
    # olives never swing on their stems (reads like a bell): they squash and pop in place
    idle = {"branch": {"rotate": osc(T, 1.0)}}
    for i, n in enumerate(leaves):
        idle[n] = {"rotate": osc(T, 2.0, phase=0.7 * i)}
    k.add("idle", bones=idle)
    land = {"branch": {"rotate": rotate((0, -5, None), (0.12, -5, "out"), (0.26, 5, "inout"), (0.46, -2, "inout"), (0.7, 0, None))},
            "olive1": {"scale": squash(t0=0.12, amt=0.07)}, "olive2": {"scale": squash(t0=0.15, amt=0.07)}, "olive3": {"scale": squash(t0=0.18, amt=0.07)}}
    for i, n in enumerate(leaves):
        land[n] = {"rotate": rotate(*spring(6 if i % 2 else -6, t0=0.12 + 0.02 * i))}
    k.add("land", bones=land)
    pop = lambda t0: scale((0, 1, 1, None), (t0, 1, 1, "out"), (t0 + 0.12, 1.2, 1.2, "inout"), (t0 + 0.3, 0.96, 0.96, "inout"), (t0 + 0.45, 1, 1, None))
    conn = {"branch": {"rotate": rotate((0, 0, "inout"), (0.16, -3, "out"), (0.38, 6, "inout"), (0.62, -3, "inout"), (0.86, 4, "inout"), (1.2, -1.5, "inout"), (D, 0, None))},
            "olive1": {"scale": pop(0.36)}, "olive2": {"scale": pop(0.48)}, "olive3": {"scale": pop(0.6)}}
    for i, n in enumerate(leaves):
        conn[n] = {"rotate": rotate(*spring(9 if i % 2 else -9, t0=0.3 + 0.04 * i))}
    b, sl = throw("fly", 0.5, 1.1, 90 * s, 70 * s, -60 * s, spin=-260)
    k.add("connect", bones={**conn, **b}, slots=sl)
    return k


# ==========================================================================
# Round DZ medallions
# ==========================================================================
def dz_overlay(k, parts):
    """Slash, ribbons, wreath halves, DZ medal and gems: fitted, layered on top, animated the same on every medallion."""
    fits = {}
    for n, (box, hint) in parts.items():
        cut = hint.pop("cut", {})
        k.part(n, box, **cut)
        fits[n] = k.fit(n, **hint)
    f = fits
    k.bone("slash", "content", f["slash"].center)
    k.bone("ribbon_l", "symbol", f["ribbon_l"].pt(0.1, 0.25))
    k.bone("ribbon_r", "symbol", f["ribbon_r"].pt(0.9, 0.25))
    k.bone("wreath_l", "symbol", f["wreath_l"].pt(0.85, 0.95))
    k.bone("wreath_r", "symbol", f["wreath_r"].pt(0.15, 0.95))
    k.bone("medal", "symbol", f["medal"].center)
    gems = [n for n in f if n.startswith("gem")]
    for n in gems:
        k.bone(n, "symbol", f[n].center)
    k.layer("slash", "slash", f["slash"], color="ffffff70", blend="additive")
    for n in ("ribbon_l", "ribbon_r", "wreath_l", "wreath_r", "medal", *gems):
        k.layer(n, n, f[n])
    T, D = k.T, k.D
    idle = {"medal": {"scale": osc2(T, 0.012, 0.012, phase=-math.pi / 2, bx=1.012, by=1.012)},
            "ribbon_l": {"rotate": osc(T, 2.5)}, "ribbon_r": {"rotate": osc(T, 2.5, phase=math.pi)},
            "wreath_l": {"rotate": osc(T, 1.2, phase=0.5)}, "wreath_r": {"rotate": osc(T, 1.2, phase=0.5 + math.pi)}}
    for i, n in enumerate(gems):
        t = T * (0.3 + 0.45 * i)
        idle[n] = {"scale": scale((0, 1, 1, None), (t, 1, 1, "out"), (t + 0.08, 1.25, 1.25, "in"), (t + 0.25, 1, 1, None))}
    k.add("idle", bones=idle, slots={"slash": {"rgba": rgba((0, "ffffff50", "inout"), (T / 2, "ffffffb0", "inout"), (T, "ffffff50", None))}})
    flutter = ((0, 8, "in"), (0.14, -6, "out"), (0.34, 4, "inout"), (0.56, -1.5, "inout"), (0.8, 0, None))
    clamp = ((0, -18, "in"), (0.14, 5, "out"), (0.32, -2, "inout"), (0.5, 0, None))
    land = {"medal": {"scale": scale((0, 1.5, 1.5, "in"), (0.14, 0.88, 0.88, "out"), (0.3, 1.06, 1.06, "inout"), (0.46, 1, 1, None))},
            "ribbon_l": {"rotate": rotate(*flutter)}, "ribbon_r": {"rotate": rotate(*mirror(flutter))},
            "wreath_l": {"rotate": rotate(*clamp)}, "wreath_r": {"rotate": rotate(*mirror(clamp))},
            "slash": {"scale": scale((0, 1, 1, None), (0.12, 1, 1, "out"), (0.2, 1.15, 1.15, "inout"), (0.5, 1, 1, None))}}
    for i, n in enumerate(gems):
        land[n] = {"scale": scale((0, 1, 1, None), (0.14 + 0.04 * i, 1, 1, "out"), (0.22 + 0.04 * i, 1.35, 1.35, "in"), (0.42 + 0.04 * i, 1, 1, None))}
    k.add("land", bones=land, slots={"slash": {"rgba": rgba((0, "ffffff70", None), (0.12, "ffffff70", "out"), (0.16, "ffffffff", "in"), (0.6, "ffffff70", None))}})
    wave = ((0, 0, "inout"), (0.2, -7, "inout"), (0.4, 6, "inout"), (0.6, -5, "inout"), (0.8, 4, "inout"), (1.0, -3, "inout"), (1.25, 2, "inout"), (1.55, -1, "inout"), (D, 0, None))
    conn = {"medal": {"scale": scale((0, 1, 1, "inout"), (0.3, 1.12, 1.12, "in"), (0.42, 0.06, 1.12, "out"), (0.54, 1.12, 1.12, "in"), (0.66, 0.06, 1.12, "out"),
                                     (0.8, 1.15, 1.15, "inout"), (1.4, 1.08, 1.08, "inout"), (D, 1, 1, None))},
            "ribbon_l": {"rotate": rotate(*wave)}, "ribbon_r": {"rotate": rotate(*mirror(wave))},
            "wreath_l": {"scale": scale((0, 1, 1, "inout"), (0.36, 1.08, 1.08, "inout"), (1.3, 1.05, 1.05, "inout"), (D, 1, 1, None))},
            "wreath_r": {"scale": scale((0, 1, 1, "inout"), (0.36, 1.08, 1.08, "inout"), (1.3, 1.05, 1.05, "inout"), (D, 1, 1, None))},
            "slash": {"scale": scale((0, 1, 1, "inout"), (0.3, 0.6, 0.6, "out"), (0.5, 1.25, 1.25, "inout"), (0.9, 1, 1, None))}}
    for i, n in enumerate(gems):
        t = 0.34 + 0.16 * i
        conn[n] = {"scale": scale((0, 1, 1, None), (t, 1, 1, "out"), (t + 0.1, 1.4, 1.4, "in"), (t + 0.32, 1, 1, None)),
                   "rotate": rotate((0, 0, None), (t, 0, "out"), (t + 0.32, 360, None))}
    k.add("connect", bones=conn, slots={"slash": {"rgba": rgba((0, "ffffff70", "inout"), (0.3, "ffffff20", "out"), (0.44, "ffffffff", "inout"), (1.2, "ffffffb0", "inout"), (D, "ffffff70", None))}})

    # appear: the two halves slide together along the slash (Kit.split); as they lock the slash flashes,
    # the ribbons unfurl, the wreath halves swing shut, the medal coin-flips in and the gems spin in
    L = k.appear_lock
    pop_in = lambda t: scale((0, 0, 0, None), (t, 0, 0, "back"), (t + 0.22, 1, 1, None))
    appear = {
        "medal": {"scale": scale((0, 0, 0, None), (L + 0.02, 0, 0, "back"), (L + 0.2, 1.25, 1.25, "in"), (L + 0.3, 0.06, 1.2, "out"), (L + 0.42, 1.12, 1.12, "inout"), (L + 0.6, 1, 1, None))},
        "slash": {"scale": scale((0, 0, 0, None), (L - 0.04, 0, 0, "out"), (L + 0.12, 1.3, 1.3, "inout"), (L + 0.38, 1, 1, None))},
        "ribbon_l": {"scale": scale((0, 0, 1, None), (L + 0.04, 0, 1, "back"), (L + 0.28, 1, 1, None)),
                     "rotate": rotate((0, 0, None), (L + 0.28, 0, "inout"), (L + 0.46, -5, "inout"), (L + 0.64, 3, "inout"), (L + 0.84, 0, None))},
        "ribbon_r": {"scale": scale((0, 0, 1, None), (L + 0.04, 0, 1, "back"), (L + 0.28, 1, 1, None)),
                     "rotate": rotate((0, 0, None), (L + 0.28, 0, "inout"), (L + 0.46, 5, "inout"), (L + 0.64, -3, "inout"), (L + 0.84, 0, None))},
        "wreath_l": {"scale": pop_in(L + 0.08), "rotate": rotate((0, -40, None), (L + 0.1, -40, "back"), (L + 0.34, 0, None))},
        "wreath_r": {"scale": pop_in(L + 0.08), "rotate": rotate((0, 40, None), (L + 0.1, 40, "back"), (L + 0.34, 0, None))},
    }
    for i, n in enumerate(gems):
        t = L + 0.32 + 0.08 * i
        appear[n] = {"scale": pop_in(t), "rotate": rotate((0, 0, None), (t, 0, "out"), (t + 0.3, 360, None))}
    k.add("appear", bones=appear, slots={"slash": {"rgba": rgba((0, "ffffff00", None), (L - 0.04, "ffffff00", "out"), (L + 0.04, "ffffffff", "inout"), (L + 0.7, "ffffff70", None))}})
    return fits


def round_frame(k, ff, slash, inner=0.37, outer=0.46, distance=0.25):  # halves start close together
    """Round medallion frame. `slash` is the diagonal cut (two ref points, measured on the finished art):
    appear slides the two halves together along it. Parent each half's items to half_a (upper-left) / half_b."""
    cx, cy = ff.center
    m = min(ff.w0, ff.h0) * ff.scale
    k.frame(ff, circle(cx, cy, m * inner), outer=circle(cx, cy, m * outer))
    k.bone("half_a", "content", k.origin)
    k.bone("half_b", "content", k.origin)
    k.appear_lock = 0.42
    k.split(*slash, distance=distance)
    return circle(cx, cy, m * inner)


def dz_helmet():
    k = Kit("dz_helmet", DZ.format(1), (36, 15, 500, 499), shape="round")
    k.palette.update(rays="ffcf6a", back="ff6a4a", flash="ffe29a", front="ffd890", sparks=("fff2c0", "ffd27a"))
    # composite and empty frame touch on this sheet: cut the frame at the gap and rebuild its left knob from the right one
    S = k.S
    x0, y0, x1, y1 = 500, 0, 1040, 540
    reg = S.rgba[y0:y1, x0:x1].astype(np.float32)
    top_row = np.nonzero(reg[30, 120:440, 3] > 128)[0]
    cx = x0 + 120 + (top_row.min() + top_row.max()) / 2.0
    out = reg.copy()
    out[:, :541 - x0, 3] = 0
    cols = np.arange(x0, 566)
    src = np.clip(np.round(2 * cx - cols).astype(int) - x0, 0, x1 - x0 - 1)
    out[180:380, cols - x0] = reg[180:380, src]
    out = keep_largest(out)
    out[..., 3] = remap_alpha(out[..., 3].astype(np.uint8), 28)
    k.parts["frame"] = trim("frame", np.clip(out, 0, 255).astype(np.uint8), x0, y0)
    ff = k.fit("frame", (0.95, 1.05), search=center(k))
    round_frame(k, ff, slash=((254, 277), (405, 58)))
    k.part("crest", (1124, 24, 304, 307))
    k.part("helmet", (1020, 116, 254, 329))
    k.part("laurel", (42, 540, 263, 254))
    fh = k.fit("helmet", (0.6, 1.2), rots=rng(-12, 12, 4), flips=(False, True), search=near(174, 211))
    fc = k.fit("crest", (0.6, 1.2), rots=rng(-30, 30, 6), flips=(False, True), search=near(206, 106))
    fl = k.fit("laurel", (0.6, 1.2), rots=rng(-30, 30, 6), flips=(False, True), search=near(383, 259))
    k.bone("helmet", "half_a", fh.pt(0.5, 0.9))
    k.bone("crest", "helmet", fc.pt(0.3, 0.8))
    k.bone("laurel", "half_b", fl.pt(0.05, 0.95))
    k.layer("crest", "crest", fc)
    k.layer("helmet", "helmet", fh)
    k.layer("laurel", "laurel", fl)
    dz_overlay(k, {
        "slash": ((322, 489, 256, 337), dict(scales=(0.7, 1.3), rots=rng(-20, 20, 5), search=near(396, 187, 90), cut=dict(floor=0, grow=12))),
        "ribbon_l": ((558, 584, 289, 165), dict(scales=(0.7, 1.2), rots=rng(-10, 10, 5), search=near(61, 332))),
        "ribbon_r": ((904, 583, 294, 175), dict(scales=(0.7, 1.2), rots=rng(-10, 10, 5), search=near(448, 332))),
        "wreath_l": ((38, 845, 156, 191), dict(scales=(0.6, 1.2), rots=rng(-10, 10, 5), search=near(190, 388))),
        "wreath_r": ((275, 845, 155, 191), dict(scales=(0.6, 1.2), rots=rng(-10, 10, 5), search=near(319, 388))),
        "medal": ((1219, 573, 193, 187), dict(scales=(0.6, 1.2), search=near(254, 380))),
        "gem_top": ((669, 820, 89, 97), dict(scales=(0.5, 1.3), search=near(270, 17, 50))),
        "gem_bottom": ((494, 903, 82, 100), dict(scales=(0.5, 1.3), search=near(262, 469, 50))),
    })
    T, D, s = k.T, k.D, k.k
    # crest moves only with the helmet; the laurel branch never waves, it only pulses
    k.add("idle", bones={"helmet": {"rotate": osc(T, 1.2)}})
    k.add("land", bones={"helmet": {"rotate": rotate((0, 5, "in"), (0.12, -4, "out"), (0.3, 3, "inout"), (0.5, -1, "inout"), (0.7, 0, None))},
                         "laurel": {"scale": pulse(0.14, 0.05)}})
    k.add("connect", bones={
        "helmet": {"rotate": rotate((0, 0, "inout"), (0.14, 4, "out"), (0.34, -9, "inout"), (0.56, 5, "inout"), (0.78, -5, "inout"), (1.0, 2, "inout"), (1.4, 0, None)),
                   "translate": translate((0, 0, 0, "inout"), (0.34, 0, 10 * s, "inout"), (1.3, 0, 7 * s, "inout"), (1.6, 0, 0, None))},
        "laurel": {"scale": scale((0, 1, 1, "inout"), (0.36, 1.07, 1.07, "inout"), (1.2, 1.04, 1.04, "inout"), (D, 1, 1, None))}})
    return k


def dz_ship():
    k = Kit("dz_ship", DZ.format(2), (2, 3, 452, 439), shape="round")
    k.palette.update(rays="cfeeff", back="5aa8ff", flash="d8f0ff", front="c8e8ff", sparks=("ffffff", "fff2c0"))
    k.part("frame", (465, 4, 447, 438))
    ff = k.fit("frame", (0.95, 1.05), search=center(k))
    win = round_frame(k, ff, slash=((185, 292), (350, 73)))
    # the ship piece already carries its bow waves, and the sail its own mast top, as in the finished medallion
    k.part("sail", (915, 33, 303, 331))
    k.part("ship", (20, 469, 652, 364), min_inside=0.8)
    k.part("vase", (793, 420, 224, 288))
    k.part("olive", (993, 396, 290, 322))
    # masked search keeps shrinking this piece (its waves are ragged); placed by eye against the finished medallion
    fship = k.at("ship", (160, 262), 0.4)
    fsail = k.fit("sail", (0.55, 0.75), rots=rng(-12, 12, 4), flips=(False, True), search=near(155, 118, 50))
    fvase = k.fit("vase", (0.5, 1.2), rots=rng(-12, 12, 4), search=near(345, 271, 70))
    folive = k.fit("olive", (0.5, 0.72), rots=rng(-30, 30, 6), flips=(False, True), search=near(375, 190, 50))
    k.bone("boat", "half_a", fship.pt(0.5, 0.7))
    k.bone("sail", "boat", fsail.pt(0.5, 0.1))
    k.bone("olive", "half_b", folive.pt(0.1, 0.9))
    k.bone("vase", "half_b", fvase.pt(0.5, 0.95))
    k.layer("sail", "sail", fsail)
    k.clip("sea_clip", win, "ship", bone="half_a")
    k.layer("ship", "boat", fship)
    k.layer("olive", "olive", folive)
    k.layer("vase", "vase", fvase)
    dz_overlay(k, {
        "slash": ((1182, 371, 260, 374), dict(scales=(0.7, 1.3), rots=rng(-20, 20, 5), search=near(321, 191, 90), cut=dict(floor=0, grow=12))),
        "ribbon_l": ((19, 855, 208, 188), dict(scales=(0.7, 1.2), rots=rng(-10, 10, 5), search=near(46, 344))),
        "ribbon_r": ((624, 854, 205, 190), dict(scales=(0.7, 1.2), rots=rng(-10, 10, 5), search=near(409, 344))),
        "wreath_l": ((249, 873, 112, 181), dict(scales=(0.6, 1.2), rots=rng(-10, 10, 5), search=near(159, 400))),
        "wreath_r": ((508, 873, 112, 181), dict(scales=(0.6, 1.2), rots=rng(-10, 10, 5), search=near(288, 400))),
        "medal": ((347, 861, 176, 169), dict(scales=(0.6, 1.2), search=near(224, 392))),
        "gem_top": ((1071, 874, 80, 77), dict(scales=(0.5, 1.3), search=near(224, 13, 50))),
        "gem_bottom": ((1075, 978, 73, 72), dict(scales=(0.5, 1.3), search=near(224, 432, 50))),
    })
    T, D, s = k.T, k.D, k.k
    k.add("idle", bones={"boat": {"rotate": osc(T, 2.2), "translate": osc2(T, 0, 3 * s, phase=0.8)}, "sail": {"scale": osc2(T, 0.035, 0.01, phase=0.4, bx=1, by=1)},
                         "vase": {"rotate": osc(T, 1.4, phase=1.0)}, "olive": {"rotate": osc(T, 1.8, phase=2.0)}})
    k.add("land", bones={"boat": {"translate": translate((0, 0, 14 * s, "in"), (0.14, 0, -6 * s, "out"), (0.34, 0, 2 * s, "inout"), (0.56, 0, 0, None)),
                                  "rotate": rotate((0, -4, "in"), (0.14, 5, "out"), (0.34, -3, "inout"), (0.6, 1, "inout"), (0.8, 0, None))},
                         "vase": {"rotate": rotate(*spring(-6, t0=0.13)), "scale": squash(t0=0.13)}, "olive": {"rotate": rotate(*spring(7, t0=0.15))}})
    k.add("connect", bones={
        "boat": {"translate": translate((0, 0, 0, "inout"), (0.14, -5 * s, -3 * s, "out"), (0.4, 10 * s, 6 * s, "inout"), (1.0, 9 * s, 5 * s, "inout"), (D - 0.25, -2 * s, -1 * s, "inout"), (D, 0, 0, None)),
                 "rotate": rotate((0, 0, "inout"), (0.14, -3, "out"), (0.4, 6, "inout"), (0.7, 2, "inout"), (1.0, 5, "inout"), (1.35, 1, "inout"), (D, 0, None))},
        "sail": {"scale": scale((0, 1, 1, "inout"), (0.4, 1.14, 1.02, "inout"), (0.7, 1.06, 1, "inout"), (1.0, 1.12, 1.02, "inout"), (D, 1, 1, None))},
        "vase": {"translate": translate((0, 0, 0, "inout"), (0.16, 0, -3 * s, "out"), (0.4, 0, 16 * s, "inout"), (0.9, 0, 12 * s, "inout"), (1.3, 0, 14 * s, "inout"), (1.56, 0, -2 * s, "inout"), (D, 0, 0, None)),
                 "rotate": rotate((0, 0, "inout"), (0.4, 8, "inout"), (0.58, -7, "inout"), (0.76, 5, "inout"), (0.94, -3, "inout"), (1.2, 0, None))},
        "olive": {"rotate": rotate(*spring(9, t0=0.3))}})
    return k


def dz_chalice():
    k = Kit("dz_chalice", DZ.format(3), (31, 15, 470, 517), shape="round")
    k.palette.update(rays="ffb0d8", back="c040a0", flash="ffd0e8", front="ffa0cc", sparks=("fff2c0", "e8c0ff"))
    k.part("frame", (553, 10, 517, 525), seeds=[(785, 45)], clip=True)
    # the frame is fused with the finished symbol on this sheet: the box cut drags along a sliver of its ring
    fr = k.parts["frame"]
    k.parts["frame"] = trim("frame", np.clip(keep_largest(fr.rgba.astype(np.float32)), 0, 255).astype(np.uint8), fr.ox, fr.oy)
    ff = k.fit("frame", (0.95, 1.05), search=center(k))
    round_frame(k, ff, slash=((219, 346), (427, 73)))
    k.part("chalice", (40, 533, 400, 360), seeds=[(250, 640)], clip=True)
    k.part("splash", (1083, 17, 348, 232), floor=10)
    k.part("grapes", (502, 560, 261, 293))
    k.part("leaf", (785, 515, 283, 261))
    k.part("grape", (1099, 516, 116, 114))
    k.part("grape_small", (1330, 577, 82, 79))
    k.part("drop", (1250, 293, 84, 99))
    fch = k.fit("chalice", (0.5, 1.1), rots=rng(-40, 40, 8), flips=(False, True), search=near(163, 162, 80))
    fsp = k.fit("splash", (0.7, 1.0), rots=rng(-30, 30, 10), flips=(False, True), search=near(190, 80, 70))
    fgr = k.fit("grapes", (0.5, 1.2), rots=rng(-12, 12, 4), search=near(340, 259, 70))
    flf = k.fit("leaf", (0.5, 0.72), rots=rng(-30, 30, 10), flips=(False, True), search=near(420, 215, 50))
    k.bone("cup", "half_a", fch.pt(0.5, 0.95))
    k.bone("wine", "cup", fsp.pt(0.6, 0.9))
    k.bone("grapes", "half_b", fgr.pt(0.5, 0.03))
    k.bone("leaf", "grapes", flf.center)
    pops = [("grape1", fgr.pt(0.3, 0.5), "grape", (-40, 70, -60)), ("grape2", fgr.pt(0.7, 0.4), "grape_small", (70, 60, -50)), ("drop1", fsp.pt(0.4, 0.4), "drop", (-50, 60, -70)),
            ("drop2", fsp.pt(0.7, 0.3), "drop", (40, 80, -60))]
    for n, p, part, _ in pops:
        k.bone(n, "grapes" if n.startswith("grape") else "wine", p)
    k.layer("chalice", "cup", fch)
    k.layer("splash", "wine", fsp)
    k.layer("leaf", "leaf", flf)
    k.layer("grapes", "grapes", fgr)
    for n, p, part, _ in pops:
        k.layer(n, n, k.at(part, p, fgr.scale * 0.75), color=HIDDEN)
    dz_overlay(k, {
        "slash": ((940, 766, 221, 303), dict(scales=(0.7, 1.3), rots=rng(-20, 20, 5), search=near(281, 195, 90), cut=dict(floor=0, grow=12))),
        "ribbon_l": ((30, 820, 260, 232), dict(scales=(0.6, 1.2), rots=rng(-10, 10, 5), search=near(59, 320))),
        "ribbon_r": ((679, 820, 241, 232), dict(scales=(0.6, 1.2), rots=rng(-10, 10, 5), search=near(414, 320))),
        "wreath_l": ((313, 873, 129, 198), dict(scales=(0.6, 1.2), rots=rng(-10, 10, 5), search=near(164, 375))),
        "wreath_r": ((548, 873, 128, 198), dict(scales=(0.6, 1.2), rots=rng(-10, 10, 5), search=near(309, 375))),
        "medal": ((402, 868, 186, 185), dict(scales=(0.6, 1.2), search=near(234, 365))),
        "gem_top": ((891, 896, 93, 124), dict(scales=(0.5, 1.3), search=near(231, 25, 50))),
    })
    T, D, s = k.T, k.D, k.k
    k.add("idle", bones={"cup": {"rotate": osc(T, 1.4)}, "wine": {"scale": osc2(T, 0.03, 0.05, phase=0.5, bx=1, by=1)}, "grapes": {"translate": osc2(T, 0, 2 * s, phase=1.3)},
                         "leaf": {"rotate": osc(T, 2.0, phase=2.0)}})
    b, sl = throw("drop1", 0.14, 0.7, -50 * s, 50 * s, -70 * s)
    k.add("land", bones={"cup": {"rotate": rotate(*spring(-6, t0=0.12)), "scale": squash()},
                         "wine": {"scale": scale((0, 1, 1, None), (0.12, 1, 1, "out"), (0.22, 1.08, 1.3, "inout"), (0.42, 0.97, 0.92, "inout"), (0.62, 1, 1, None))},
                         "grapes": {"scale": squash(t0=0.13, amt=0.08)}, **b}, slots=sl)
    b, sl = combine(*[throw(n, 0.38 + 0.14 * i, 0.85, dx * s, up * s, fall * s) for i, (n, _, _, (dx, up, fall)) in enumerate(pops)])
    k.add("connect", bones={
        "cup": {"rotate": rotate((0, 0, "inout"), (0.14, 4, "out"), (0.36, -12, "inout"), (0.6, -8, "inout"), (0.9, -11, "inout"), (1.2, -7, "inout"), (1.55, 2, "inout"), (D, 0, None))},
        "wine": {"scale": scale((0, 1, 1, "inout"), (0.34, 1.25, 1.4, "inout"), (0.6, 1.1, 1.15, "inout"), (0.9, 1.22, 1.32, "inout"), (1.3, 1.06, 1.08, "inout"), (D, 1, 1, None))},
        "grapes": {"scale": scale((0, 1, 1, "inout"), (0.16, 1.05, 0.93, "out"), (0.38, 0.97, 1.06, "inout"), (0.6, 1.03, 0.97, "inout"), (0.84, 0.98, 1.03, "inout"), (1.1, 1, 1, None))},
        "leaf": {"rotate": rotate(*spring(8, t0=0.3))}, **b}, slots=sl)
    return k


def dz_trident():
    k = Kit("dz_trident", DZ.format(4), (10, 5, 470, 468), shape="round")
    k.palette.update(rays="ffe08a", back="30d890", flash="d0ffe8", front="a8ffd0", sparks=("fff2c0", "c8ffe4"))
    k.part("frame", (502, 4, 450, 450))
    ff = k.fit("frame", (0.95, 1.05), search=center(k))
    round_frame(k, ff, slash=((204, 296), (362, 73)))
    k.part("head", (999, 22, 274, 398))
    k.part("shaft", (1336, 18, 82, 400))
    k.part("twig", (1087, 492, 179, 224))
    for n, box in [("leaf_a", (29, 548, 181, 147)), ("leaf_b", (224, 520, 154, 164)), ("leaf_c", (391, 555, 156, 132)), ("leaf_d", (563, 526, 188, 157)),
                   ("olive_a", (797, 562, 115, 110)), ("olive_b", (958, 565, 98, 111))]:
        k.part(n, box)
    fhead = k.fit("head", (0.5, 1.2), rots=rng(-16, 16, 4), search=near(175, 140, 80))
    fshaft = k.fit("shaft", (0.5, 1.2), rots=rng(-24, 24, 4), search=near(175, 317, 80))
    ftwig = k.fit("twig", (0.7, 1.2), rots=rng(-40, 40, 10), flips=(False, True), search=near(345, 215, 70))
    leaf_rots = rng(-60, 60, 12)
    leaves = {n: k.fit(n, (0.55, 0.82), rots=leaf_rots, flips=(False, True), search=near(*c, r)) for n, c, r in
              [("leaf_a", (415, 145), 45), ("leaf_b", (305, 245), 45), ("leaf_c", (395, 260), 40), ("leaf_d", (265, 285), 40)]}
    olives = {n: k.fit(n, (0.5, 1.3), rots=rng(-20, 20, 10), search=near(*c, 45)) for n, c in [("olive_a", (321, 253)), ("olive_b", (353, 293))]}
    k.bone("trident", "half_a", fshaft.pt(0.5, 0.98))
    k.bone("head", "trident", fhead.pt(0.5, 0.95))
    k.bone("branch", "half_b", ftwig.pt(0.05, 0.95))
    for n, f in leaves.items():
        k.bone(n, "branch", f.center)
    for n, f in olives.items():
        k.bone(n, "branch", f.pt(0.5, 0.05))
    k.layer("shaft", "trident", fshaft)
    k.layer("head", "head", fhead)
    k.layer("twig", "branch", ftwig)
    for n, f in leaves.items():
        k.layer(n, n, f)
    for n, f in olives.items():
        k.layer(n, n, f)
    g = glints(k, "head", [fhead.pt(0.5, 0.04), fhead.pt(0.12, 0.2), fhead.pt(0.88, 0.2)], "f4fff0", 0.6)
    dz_overlay(k, {
        "slash": ((1268, 469, 156, 281), dict(scales=(0.7, 1.4), rots=rng(-20, 20, 5), search=near(313, 189, 90), cut=dict(floor=0, grow=12))),
        "ribbon_l": ((30, 734, 239, 180), dict(scales=(0.6, 1.2), rots=rng(-10, 10, 5), search=near(63, 350))),
        "ribbon_r": ((1198, 759, 230, 155), dict(scales=(0.6, 1.2), rots=rng(-10, 10, 5), search=near(425, 350))),
        "wreath_l": ((539, 734, 127, 178), dict(scales=(0.6, 1.2), rots=rng(-10, 10, 5), search=near(167, 390))),
        "wreath_r": ((736, 734, 131, 178), dict(scales=(0.6, 1.2), rots=rng(-10, 10, 5), search=near(296, 390))),
        "medal": ((313, 731, 199, 191), dict(scales=(0.6, 1.2), search=near(232, 382))),
        "gem_top": ((908, 811, 83, 90), dict(scales=(0.5, 1.3), search=near(232, 14, 50))),
        "gem_bottom": ((1058, 779, 91, 105), dict(scales=(0.5, 1.3), search=near(232, 447, 50))),
    })
    T, D, s = k.T, k.D, k.k
    idle = {"trident": {"translate": osc2(T, 0, 2.5 * s, phase=0.5)}, "branch": {"rotate": osc(T, 1.6, phase=1.0)}}
    for i, n in enumerate(leaves):  # olives don't swing on their stems
        idle[n] = {"rotate": osc(T, 1.6, phase=0.8 * i)}
    b, sl = glint_keys(g, (T * 0.15, T * 0.45, T * 0.8), "f4fff0")
    k.add("idle", bones={**idle, **b}, slots=sl)
    land = {"trident": {"translate": translate((0, 0, 20 * s, "in"), (0.12, 0, -5 * s, "out"), (0.3, 0, 2 * s, "inout"), (0.5, 0, 0, None))},
            "branch": {"rotate": rotate(*spring(-6, t0=0.13))}}
    for i, n in enumerate(leaves):
        land[n] = {"rotate": rotate(*spring(8 if i % 2 else -8, t0=0.13 + 0.02 * i))}
    for i, n in enumerate(olives):
        land[n] = {"scale": squash(t0=0.14 + 0.03 * i, amt=0.07)}
    b, sl = glint_keys(g, (0.13, 0.16, 0.19), "f4fff0", grow=1.2)
    k.add("land", bones={**land, **b}, slots=sl)
    conn = {"trident": {"translate": translate((0, 0, 0, "inout"), (0.14, 0, -8 * s, "out"), (0.34, 0, 18 * s, "inout"), (0.9, 0, 13 * s, "inout"), (1.3, 0, 16 * s, "inout"), (D - 0.25, 0, -2 * s, "inout"), (D, 0, 0, None)),
                        "rotate": rotate((0, 0, "inout"), (0.34, -4, "inout"), (0.6, 3, "inout"), (0.9, -2, "inout"), (1.3, 1, "inout"), (D, 0, None))},
            "branch": {"rotate": rotate((0, 0, "inout"), (0.2, 4, "out"), (0.44, -7, "inout"), (0.7, 5, "inout"), (0.96, -3, "inout"), (1.3, 1, "inout"), (D, 0, None))}}
    for i, n in enumerate(olives):
        t = 0.36 + 0.12 * i
        conn[n] = {"scale": scale((0, 1, 1, None), (t, 1, 1, "out"), (t + 0.12, 1.22, 1.22, "inout"), (t + 0.3, 0.96, 0.96, "inout"), (t + 0.45, 1, 1, None))}
    b, sl = glint_keys(g, (0.36, 0.44, 0.52), "f4fff0", grow=1.4)
    k.add("connect", bones={**conn, **b}, slots=sl)
    return k


SYMBOLS = {f.__name__: f for f in (helmet, laurel, ship, amphora, chalice, grapes, trident, olive, dz_helmet, dz_ship, dz_chalice, dz_trident)}

if __name__ == "__main__":
    names = sys.argv[1:] or list(SYMBOLS)
    for name in names:
        print(f"== {name}")
        SYMBOLS[name]().build()
