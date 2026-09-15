"""Shared template for reel symbols assembled from a part sheet.

A sheet holds the finished symbol (the reference), an empty frame and the loose
parts. A symbol script cuts the parts, fits each one onto the reference (cached
masked-SSD search, see spine_rig.fit_part), declares bones and draw order, and adds
symbol-specific motion. The kit supplies everything the symbols have in common:

  bones   root > symbol > {fx > spk1..8, frame, content, shine}
  slots   rays, frame, window-clipped back glow, <symbol layers>, clipped shine
          sweep, frame flash, front glow, 8 sparkles
  anims   idle (loop), land (drop + squash, fires impact/settled) and connect
          (pop + celebration, fires cheer). Symbol motion is merged on top,
          property by property.

Coordinates are ref pixels (y-down) measured on the finished symbol in the sheet.
"""
import hashlib
import json
import math
import os

import numpy as np
from PIL import Image

from spine_rig import (Rig, Sheet, attach, fit_part, gen, osc, osc2, render_setup, rgba, rot, rotate, scale, standard_fx,
                       translate, twinkle, with_alpha, write_outputs, write_skeleton)

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
SHEETS = os.path.join(REPO, "foranimation")
ASSETS = os.path.join(HERE, "..", "assets")
CACHE = os.path.join(HERE, "_cache")
DEBUG = os.path.join(HERE, "_debug")


class Fit:
    """A part placed in ref space: centre, uniform scale, CCW rotation, optional mirror."""

    def __init__(self, part, center, scale, rotation=0.0, flip=False, err=None):
        self.part, self.center, self.scale, self.rotation, self.flip, self.err = part, tuple(center), scale, rotation, flip, err
        self.w0, self.h0 = part.w, part.h

    def pt(self, u, v):
        """Ref point at normalised part coordinates (0,0 top-left .. 1,1 bottom-right)."""
        x, y = (u - 0.5) * self.w0 * self.scale, (v - 0.5) * self.h0 * self.scale
        if self.flip:
            x = -x
        x, y = rot(x, y, self.rotation)
        return (self.center[0] + x, self.center[1] + y)

    def moved(self, dx=0.0, dy=0.0, k=1.0, dr=0.0, flip=None):
        return Fit(self.part, (self.center[0] + dx, self.center[1] + dy), self.scale * k, self.rotation + dr,
                   self.flip if flip is None else flip, self.err)

    def att(self):
        return dict(part=self.part, center=self.center, scale=self.scale, rotation=self.rotation, flip=self.flip)


def circle(cx, cy, r, n=32):
    return [(cx + r * math.cos(2 * math.pi * i / n), cy + r * math.sin(2 * math.pi * i / n)) for i in range(n)]


def merge_anim(base, extra):
    out = {"bones": dict(base.get("bones", {})), "slots": dict(base.get("slots", {}))}
    for group in ("bones", "slots"):
        for name, props in extra.get(group, {}).items():
            out[group][name] = {**out[group].get(name, {}), **props}
    events = base.get("events", []) + extra.get("events", [])
    if events:
        out["events"] = sorted(events, key=lambda e: e["time"])
    return out


class Kit:
    def __init__(self, name, sheet, ref_box, shape="square", idle_T=3.2, connect_D=1.8):
        self.name, self.shape, self.T, self.D = name, shape, idle_T, connect_D
        self.sheet_file = f"ChatGPT Image Sep 14, 2026, {sheet}.png"
        self.S = Sheet(os.path.join(SHEETS, self.sheet_file))
        x, y, w, h = ref_box
        self.ref_box = ref_box
        self.ref = self.S.rgba[y:y + h, x:x + w]
        self.parts = {}
        self.part_keys = {}
        self.R = Rig()
        self.items = []  # draw order: ("slot", kwargs) or ("clip", kwargs)
        self.extra = {"idle": {}, "land": {}, "connect": {}}
        self.palette = dict(rays="ffd27a", back="ffc864", flash="ffe7a0", front="ffdc96", shine="fff6d0", sparks=("fff2c0",))
        self.cache_path = os.path.join(CACHE, f"{name}.json")
        self.cache = json.load(open(self.cache_path)) if os.path.exists(self.cache_path) else {}
        self.debug_dir = os.path.join(DEBUG, name)
        self.frame_fit = None
        self.appear_lock, self.appear_spin = 0.3, True  # appear: when the symbol is complete; spin up from nothing unless split()
        for n, p in standard_fx().items():
            self.parts[n] = p

    # ---------------------------------------------------------------- parts
    def part(self, name, box, **cut):
        self.parts[name] = self.S.cut(name, box, **cut)
        self.part_keys[name] = [list(box), sorted((k, str(v)) for k, v in cut.items())]
        return self.parts[name]

    def fit(self, part, scales, rots=(0,), flips=(False,), search=None, tag=None):
        p = self.parts[part]
        key_src = json.dumps([self.sheet_file, self.ref_box, self.part_keys.get(part), p.w, p.h, scales, list(rots), list(flips), search])
        key = f"{tag or part}:{hashlib.sha1(key_src.encode()).hexdigest()[:12]}"
        if key not in self.cache:
            self.cache[key] = fit_part(p, self.ref, scales, tuple(rots), tuple(flips), search)
            os.makedirs(CACHE, exist_ok=True)
            json.dump(self.cache, open(self.cache_path, "w"), indent=1)
        f = self.cache[key]
        print(f"  fit {tag or part:14s} s={f['scale']:.3f} r={f['rotation']:+4d} flip={int(f['flip'])} c=({f['center'][0]:.0f},{f['center'][1]:.0f}) err={f['err']:.3f}")
        return Fit(p, f["center"], f["scale"], f["rotation"], f["flip"], f["err"])

    def at(self, part, center, scale, rotation=0.0, flip=False):
        return Fit(self.parts[part], center, scale, rotation, flip)

    # ---------------------------------------------------------------- rig
    def frame(self, fit, window, outer=None):
        """Install the frame and the kit's base bones.

        `window` is the inner polygon (content area, clips the back glow); `outer` the
        polygon that clips the shine sweep (defaults to the frame rectangle / circle).
        """
        self.frame_fit = fit
        self.outer = outer
        cx, cy = fit.center
        self.origin = (cx, cy)
        fw, fh = fit.w0 * fit.scale, fit.h0 * fit.scale
        self.size = max(fw, fh)
        self.bounds = (cx - fw / 2, cy - fh / 2, cx + fw / 2, cy + fh / 2)
        self.window = window
        k = self.size / 380.0
        self.k = k
        R = self.R
        R.bone("root", None, self.origin)
        R.bone("symbol", "root", self.origin)
        R.bone("fx", "symbol", self.origin)
        R.bone("frame", "symbol", self.origin)
        R.bone("content", "symbol", self.origin)
        R.bone("shine", "symbol", self.origin)
        x0, y0, x1, y1 = self.bounds
        self.spots = [(cx, y0 + 8 * k), (x0 + 22 * k, y0 + 40 * k), (x1 - 22 * k, y0 + 34 * k), (x0 - 4 * k, cy + 40 * k),
                      (x1 + 4 * k, cy + 26 * k), (x0 + 60 * k, y1 - 4 * k), (x1 - 60 * k, y1 - 2 * k), (cx - 70 * k, cy - 60 * k)]
        for i, spot in enumerate(self.spots):
            R.bone(f"spk{i + 1}", "fx", spot)
        P = self.parts
        self._slot("fx_rays", "fx", {"rays": Fit(P["rays"], self.origin, 1.9 * k).att()}, "rays", color=self.palette["rays"] + "00", blend="additive")
        self._slot("frame", "frame", {"frame": fit.att()}, "frame")
        self.clip("glow_clip", window, "back_glow")
        self._slot("back_glow", "content", {"glow": Fit(P["glow"], self.origin, 3.0 * k).att()}, "glow", color=self.palette["back"] + "40", blend="additive")

    def bone(self, name, parent, at, length=0):
        self.R.bone(name, parent, tuple(at), length)

    def layer(self, slot, bone, fits, setup=None, color=None, blend=None):
        """fits: a Fit (attachment named after the part) or {attachment_name: Fit}."""
        if isinstance(fits, Fit):
            fits = {fits.part.name: fits}
        atts = {n: f.att() for n, f in fits.items()}
        self._slot(slot, bone, atts, setup or next(iter(atts)), color, blend)

    def clip(self, name, polygon, end, bone="symbol"):
        self.items.append(("slot", dict(name=name, bone=bone, attachments={name: dict(clip=[tuple(p) for p in polygon], end=end)}, setup=name, color=None, blend=None)))

    def _slot(self, name, bone, attachments, setup, color=None, blend=None):
        self.items.append(("slot", dict(name=name, bone=bone, attachments=attachments, setup=setup, color=color, blend=blend)))

    def physics(self, bone, **params):
        self.R.physics(bone, **params)

    def add(self, state, bones=None, slots=None, events=None):
        """Merge symbol motion into a state. idle/land/connect always exist; any other state (e.g. appear) is created on first use."""
        cur = self.extra.get(state, {})
        self.extra[state] = merge_anim(cur, {"bones": bones or {}, "slots": slots or {}, "events": events or []})

    # ---------------------------------------------------------------- template animations
    def _sparkle_color(self, i):
        s = self.palette["sparks"]
        return s[i % len(s)]

    def anim_idle(self):
        T, k, P = self.T, self.k, self.palette
        sweep = self.size * 0.75
        bones = {
            "content": {"scale": osc2(T, 0.006, 0.006, phase=-math.pi / 2, bx=1.006, by=1.006)},
            "shine": {"translate": translate((0, -sweep, 0, None), (T * 0.56, -sweep, 0, "inout"), (T * 0.78, sweep, 0, None))},
        }
        slots = {
            "back_glow": {"rgba": rgba((0, P["back"] + "30", "inout"), (T / 2, P["back"] + "60", "inout"), (T, P["back"] + "30", None))},
            "shine": {"rgba": rgba((0, P["shine"] + "00", None), (T * 0.56, P["shine"] + "00", "soft"), (T * 0.62, P["shine"] + "90", "linear"),
                                   (T * 0.72, P["shine"] + "90", "in"), (T * 0.78, P["shine"] + "00", None))},
        }
        for n, (idx, t0) in enumerate(((1, 0.3), (3, T * 0.38), (8, T * 0.7))):
            s, b = twinkle(self._sparkle_color(n), t0, 0.6, peak=0.9, grow=0.8)
            slots[f"sparkle{idx}"] = {"rgba": s}
            bones[f"spk{idx}"] = b
        return {"bones": bones, "slots": slots}

    def anim_land(self):
        k, P = self.k, self.palette
        sweep = self.size * 0.75
        bones = {
            "symbol": {
                "translate": translate((0, 0, 56 * k, "in"), (0.12, 0, -7 * k, "out"), (0.26, 0, 3 * k, "inout"), (0.42, 0, 0, None)),
                "scale": scale((0, 0.95, 1.07, "in"), (0.12, 1.09, 0.89, "out"), (0.25, 0.97, 1.04, "inout"), (0.4, 1.01, 0.99, "inout"), (0.56, 1, 1, None)),
            },
            "fx": {"scale": scale((0, 0.6, 0.6, None), (0.12, 0.6, 0.6, "out"), (0.7, 1.25, 1.25, None)),
                   "rotate": rotate((0, 0, None), (0.12, 0, "out"), (0.9, 24, None))},
            "shine": {"translate": translate((0, -sweep, 0, None), (0.2, -sweep, 0, "inout"), (0.6, sweep, 0, None))},
        }
        slots = {
            "fx_rays": {"rgba": rgba((0, P["rays"] + "00", None), (0.11, P["rays"] + "00", "out"), (0.16, P["rays"] + "c0", "soft"), (0.75, P["rays"] + "00", None))},
            "frame_flash": {"rgba": rgba((0, P["flash"] + "00", None), (0.11, P["flash"] + "00", "out"), (0.14, P["flash"] + "70", "soft"), (0.42, P["flash"] + "00", None))},
            "front_glow": {"rgba": rgba((0, P["front"] + "00", None), (0.11, P["front"] + "00", "out"), (0.14, P["front"] + "40", "soft"), (0.36, P["front"] + "00", None))},
            "shine": {"rgba": rgba((0, P["shine"] + "00", None), (0.2, P["shine"] + "00", "soft"), (0.3, P["shine"] + "c0", "linear"), (0.48, P["shine"] + "c0", "in"), (0.6, P["shine"] + "00", None))},
        }
        for n, (idx, t0) in enumerate(((4, 0.13), (5, 0.15), (6, 0.14), (7, 0.16), (2, 0.2), (3, 0.19))):
            s, b = twinkle(self._sparkle_color(n), t0, 0.55, peak=1.0, spin=120, grow=1.0)
            slots[f"sparkle{idx}"] = {"rgba": s}
            bones[f"spk{idx}"] = b
        return {"bones": bones, "slots": slots, "events": [{"time": 0.12, "name": "impact"}, {"time": 0.8, "name": "settled"}]}

    def anim_connect(self):
        D, k, P = self.D, self.k, self.palette
        sweep = self.size * 0.75
        bones = {
            "symbol": {
                "scale": scale((0, 1, 1, "inout"), (0.14, 1.04, 0.95, "out"), (0.32, 1.12, 1.12, "inout"), (0.5, 1.07, 1.07, "inout"),
                               (0.9, 1.09, 1.09, "inout"), (1.3, 1.07, 1.07, "inout"), (D - 0.28, 0.98, 0.98, "inout"), (D - 0.14, 1.01, 1.01, "inout"), (D, 1, 1, None)),
                "rotate": rotate((0, 0, "inout"), (0.32, -2.5, "inout"), (0.46, 2, "inout"), (0.6, -1.2, "inout"), (0.76, 0.6, "inout"), (0.95, 0, None)),
                "translate": translate((0, 0, 0, "inout"), (0.14, 0, -4 * k, "out"), (0.32, 0, 10 * k, "inout"), (1.3, 0, 7 * k, "inout"), (D - 0.25, 0, -2 * k, "inout"), (D, 0, 0, None)),
            },
            "fx": {"rotate": rotate((0, 0, "linear"), (D, 60, None)), "scale": scale((0, 0.7, 0.7, "out"), (0.4, 1.15, 1.15, "inout"), (1.2, 1.05, 1.05, "inout"), (D, 1.25, 1.25, None))},
            "shine": {"translate": translate((0, -sweep, 0, None), (0.34, -sweep, 0, "inout"), (0.78, sweep, 0, None), (0.98, -sweep, 0, "inout"), (1.42, sweep, 0, None))},
        }
        slots = {
            "fx_rays": {"rgba": rgba((0, P["rays"] + "00", "out"), (0.32, P["rays"] + "e0", "inout"), (1.2, P["rays"] + "99", "inout"), (D, P["rays"] + "00", None))},
            "frame_flash": {"rgba": rgba((0, P["flash"] + "00", None), (0.3, P["flash"] + "00", "out"), (0.34, P["flash"] + "60", "soft"), (0.7, P["flash"] + "00", None))},
            "front_glow": {"rgba": rgba((0, P["front"] + "00", None), (0.3, P["front"] + "00", "out"), (0.34, P["front"] + "3c", "soft"), (0.6, P["front"] + "00", None))},
            "back_glow": {"rgba": rgba((0, P["back"] + "30", "out"), (0.36, P["back"] + "c0", "inout"), (1.3, P["back"] + "80", "inout"), (D, P["back"] + "30", None))},
            "shine": {"rgba": rgba((0, P["shine"] + "00", None), (0.34, P["shine"] + "00", "soft"), (0.44, P["shine"] + "d0", "linear"), (0.66, P["shine"] + "d0", "in"), (0.78, P["shine"] + "00", "stepped"),
                                   (0.98, P["shine"] + "00", "soft"), (1.08, P["shine"] + "d0", "linear"), (1.3, P["shine"] + "d0", "in"), (1.42, P["shine"] + "00", None))},
        }
        pops = [(1, 0.34, 1.2), (2, 0.42, 1.0), (3, 0.5, 1.0), (4, 0.62, 1.1), (5, 0.7, 1.1), (6, 0.84, 0.9), (7, 0.92, 0.9), (8, 1.06, 0.8)]
        for n, (idx, t0, grow) in enumerate(pops):
            s, b = twinkle(self._sparkle_color(n), t0, 0.5, peak=1.0, spin=140, grow=grow)
            slots[f"sparkle{idx}"] = {"rgba": s}
            bones[f"spk{idx}"] = b
        return {"bones": bones, "slots": slots, "events": [{"time": 0.32, "name": "cheer"}]}

    def anim_appear(self):
        """Symbol arrives on the reel. It spins up from nothing, unless split() made it slide in as two halves.

        Flash, rays and sparkles fire at `appear_lock`, the moment the symbol is complete.
        """
        k, P, L = self.k, self.palette, self.appear_lock
        sweep = self.size * 0.75
        bones = {
            "fx": {"scale": scale((0, 0.5, 0.5, None), (L - 0.02, 0.5, 0.5, "out"), (L + 0.7, 1.25, 1.25, None)), "rotate": rotate((0, 0, None), (L - 0.02, 0, "out"), (L + 1.0, 40, None))},
            "shine": {"translate": translate((0, -sweep, 0, None), (L + 0.3, -sweep, 0, "inout"), (L + 0.7, sweep, 0, None))},
        }
        if self.appear_spin:
            bones["symbol"] = {"scale": scale((0, 0, 0, "back"), (L, 1.08, 1.08, "inout"), (L + 0.16, 0.97, 0.97, "inout"), (L + 0.32, 1, 1, None)),
                               "rotate": rotate((0, -24, "out"), (L + 0.06, 3, "inout"), (L + 0.26, 0, None))}
        slots = {
            "fx_rays": {"rgba": rgba((0, P["rays"] + "00", None), (L - 0.04, P["rays"] + "00", "out"), (L + 0.04, P["rays"] + "e0", "soft"), (L + 0.8, P["rays"] + "00", None))},
            "frame_flash": {"rgba": rgba((0, P["flash"] + "00", None), (L - 0.02, P["flash"] + "00", "out"), (L + 0.02, P["flash"] + "90", "soft"), (L + 0.4, P["flash"] + "00", None))},
            "front_glow": {"rgba": rgba((0, P["front"] + "00", None), (L - 0.02, P["front"] + "00", "out"), (L + 0.01, P["front"] + "60", "soft"), (L + 0.3, P["front"] + "00", None))},
            "shine": {"rgba": rgba((0, P["shine"] + "00", None), (L + 0.3, P["shine"] + "00", "soft"), (L + 0.4, P["shine"] + "d0", "linear"), (L + 0.6, P["shine"] + "d0", "in"), (L + 0.7, P["shine"] + "00", None))},
        }
        for n, (idx, dt) in enumerate(((1, 0), (4, 0.04), (5, 0.06), (2, 0.12), (3, 0.16), (6, 0.22), (7, 0.26), (8, 0.32))):
            s, b = twinkle(self._sparkle_color(n), L + dt, 0.5, peak=1.0, spin=140, grow=1.1)
            slots[f"sparkle{idx}"] = {"rgba": s}
            bones[f"spk{idx}"] = b
        return {"bones": bones, "slots": slots, "events": [{"time": L, "name": "appear"}, {"time": max(1.2, L + 0.84), "name": "settled"}]}

    def split(self, p0, p1, bone_a="half_a", bone_b="half_b", distance=0.25):
        """Appear for split medallions: the frame is cut along the line p0-p1 (the slash) into two halves.

        The halves slide together along that line and lock at `appear_lock`. `bone_a` carries the upper-left half,
        arriving from the lower-left; `bone_b` the lower-right half, arriving from the upper-right. Parent each
        half's parts to its bone. The cut frames only exist during appear: at rest the whole frame is shown.
        """
        (x0, y0), (x1, y1) = p0, p1
        dx, dy = x1 - x0, y1 - y0
        length = math.hypot(dx, dy)
        dx, dy = dx / length, dy / length
        if dy > 0:  # travel direction points up-right (ref y is down)
            dx, dy = -dx, -dy
        nx, ny = dy, -dx  # normal towards the upper-left side
        far = self.size * 2
        mx, my = (x0 + x1) / 2, (y0 + y1) / 2
        a0, a1 = (mx - dx * far, my - dy * far), (mx + dx * far, my + dy * far)
        poly_a = [a0, a1, (a1[0] + nx * far, a1[1] + ny * far), (a0[0] + nx * far, a0[1] + ny * far)]
        poly_b = [a0, a1, (a1[0] - nx * far, a1[1] - ny * far), (a0[0] - nx * far, a0[1] - ny * far)]
        idx = next(i for i, (_, kw) in enumerate(self.items) if kw["name"] == "frame") + 1
        half = lambda name, bone, atts: ("slot", dict(name=name, bone=bone, attachments=atts, setup=None, color=None, blend=None))
        self.items[idx:idx] = [
            half("clip_a", bone_a, {"clip_a": dict(clip=poly_a, end="frame_a")}), half("frame_a", bone_a, {"frame": self.frame_fit.att()}),
            half("clip_b", bone_b, {"clip_b": dict(clip=poly_b, end="frame_b")}), half("frame_b", bone_b, {"frame": self.frame_fit.att()}),
        ]
        self.appear_spin = False
        L, D = self.appear_lock, self.size * distance
        over = 0.04 * D

        def slide(sign):  # sign -1: start lower-left and travel up-right; +1: the opposite. Spine y is up.
            sx, sy = sign * dx * D, sign * dy * D
            ox, oy = -sign * dx * over, -sign * dy * over
            return translate((0, sx, -sy, "in"), (L, ox, -oy, "out"), (L + 0.14, 0, 0, None))

        swap = L + 0.14
        self.add("appear", bones={bone_a: {"translate": slide(-1)}, bone_b: {"translate": slide(+1)}}, slots={
            "frame": {"attachment": attach((0, None), (swap, "frame"))},
            "frame_a": {"attachment": attach((0, "frame"), (swap, None))}, "frame_b": {"attachment": attach((0, "frame"), (swap, None))},
            "clip_a": {"attachment": attach((0, "clip_a"), (swap, None))}, "clip_b": {"attachment": attach((0, "clip_b"), (swap, None))},
        })

    # ---------------------------------------------------------------- build
    def _finish_slots(self):
        k, P = self.k, self.parts
        x0, y0, x1, y1 = self.bounds
        if self.outer is not None:
            outer = self.outer
        elif self.shape == "round":
            outer = circle(self.origin[0], self.origin[1], min(x1 - x0, y1 - y0) / 2 - 2 * k)
        else:
            outer = [(x0 + 4 * k, y0 + 4 * k), (x1 - 4 * k, y0 + 4 * k), (x1 - 4 * k, y1 - 4 * k), (x0 + 4 * k, y1 - 4 * k)]
        self.clip("shine_clip", outer, "shine")
        self._slot("shine", "shine", {"shine": Fit(P["shine"], self.origin, 2.4 * k, rotation=-28).att()}, "shine", color=self.palette["shine"] + "00", blend="additive")
        self._slot("frame_flash", "frame", {"frame": self.frame_fit.att()}, "frame", color=self.palette["flash"] + "00", blend="additive")
        self._slot("front_glow", "fx", {"glow": Fit(P["glow"], self.origin, 4.6 * k).att()}, "glow", color=self.palette["front"] + "00", blend="additive")
        for i, spot in enumerate(self.spots):
            self._slot(f"sparkle{i + 1}", f"spk{i + 1}", {"sparkle": Fit(P["sparkle"], spot, 0.55 * k).att()}, "sparkle", color=self._sparkle_color(i) + "00", blend="additive")
        for _, kw in self.items:
            self.R.slot(**kw)

    def _shrink_textures(self):
        """Parts drawn well below 1:1 are resampled so the atlas carries only the pixels on screen (+headroom)."""
        uses = {}
        for s in self.R.slots:
            for a in s["attachments"].values():
                if "part" in a:
                    uses.setdefault(a["part"].name, []).append(a)
        for name, atts in uses.items():
            p = self.parts[name]
            need = max(abs(a["scale"]) for a in atts) * 1.3
            if need >= 0.9 or name in ("glow", "rays", "sparkle", "shine"):
                continue
            nw, nh = max(8, round(p.w * need)), max(8, round(p.h * need))
            f = nw / p.w
            p.rgba = np.asarray(Image.fromarray(p.rgba).resize((nw, nh), Image.LANCZOS))
            for a in atts:
                a["scale"] = a["scale"] / f

    def build(self):
        os.makedirs(self.debug_dir, exist_ok=True)
        self._finish_slots()
        x, y, w, h = self.ref_box
        render_setup(self.R, os.path.join(self.debug_dir, "setup.png"), self.ref, off=(70, 70), size=(w + 140, h + 140))
        self._shrink_textures()
        k = self.k
        events = ("impact", "cheer", "settled") + (("appear",) if "appear" in self.extra else ())
        skeleton = write_skeleton(self.R, f"odysseus-{self.name}-v1", events, bounds=(-260 * k, -250 * k, 520 * k, 500 * k))
        skeleton["animations"] = {
            "idle": merge_anim(self.anim_idle(), self.extra["idle"]),
            "land": merge_anim(self.anim_land(), self.extra["land"]),
            "connect": merge_anim(self.anim_connect(), self.extra["connect"]),
        }
        for state, extra in self.extra.items():
            if state not in skeleton["animations"]:
                base = self.anim_appear() if state == "appear" else {}
                skeleton["animations"][state] = merge_anim(base, extra)
        used = {a["part"].name for s in self.R.slots for a in s["attachments"].values() if "part" in a}
        write_outputs(f"odysseus_{self.name}", ASSETS, [p for n, p in self.parts.items() if n in used], skeleton)
