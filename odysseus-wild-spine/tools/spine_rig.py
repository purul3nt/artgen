"""Shared toolkit for building Spine 4.3 symbol rigs straight from AI sprite sheets.

No Spine editor needed: cut parts from a sheet, describe bones/slots in "ref"
pixel space (y-down, same units as the sheet), write animations with bezier
easing, then pack an atlas and emit Spine JSON that spine-pixi-v8 can play.

Conventions used by the build scripts:
  * ref coordinates are y-down pixels, the skeleton is written y-up
  * `place()` pins a sheet point of a part onto a ref point
  * rotations are counter-clockwise on screen, in degrees
"""
import json
import math
import os

import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage


# --------------------------------------------------------------------------
# Parts and cutting
# --------------------------------------------------------------------------
class Part:
    def __init__(self, name, rgba, origin):
        self.name = name
        self.rgba = rgba  # uint8 HxWx4
        self.ox, self.oy = origin  # sheet position of pixel (0, 0)

    @property
    def w(self):
        return self.rgba.shape[1]

    @property
    def h(self):
        return self.rgba.shape[0]

    @property
    def center_sheet(self):
        return (self.ox + self.w / 2.0, self.oy + self.h / 2.0)


def remap_alpha(alpha, floor):
    """Drop the faint glow halo left by background removal, keep AA edges."""
    if floor <= 0:
        return alpha
    a = (alpha.astype(np.float32) - floor) * (255.0 / (255.0 - floor))
    return np.clip(a, 0, 255).astype(np.uint8)


def trim(name, rgba, ox, oy, pad=2):
    ys, xs = np.nonzero(rgba[..., 3] > 0)
    y0, y1 = max(0, ys.min() - pad), min(rgba.shape[0], ys.max() + 1 + pad)
    x0, x1 = max(0, xs.min() - pad), min(rgba.shape[1], xs.max() + 1 + pad)
    return Part(name, rgba[y0:y1, x0:x1].copy(), (ox + x0, oy + y0))


class Sheet:
    def __init__(self, path):
        self.rgba = np.array(Image.open(path).convert("RGBA"))
        self.h, self.w = self.rgba.shape[:2]
        self.lab, _ = ndimage.label(self.rgba[..., 3] >= 160)
        self.lab_total = np.bincount(self.lab.ravel())

    def cut(self, name, box, floor=28, grow=5, margin=28, min_inside=0.6, seeds=None, clip=False):
        """Cut the connected components that mostly live inside `box`.

        Neighbouring parts that poke into the box are masked out, so tight sheet
        layouts don't leak stray hair or leaves into a region.

        For items fused with a neighbour on the sheet, pass `seeds` (sheet points
        on the wanted item) to pick components explicitly, and `clip=True` to drop
        everything outside `box`.
        """
        x, y, w, h = box
        X0, Y0 = max(0, x - margin), max(0, y - margin)
        X1, Y1 = min(self.w, x + w + margin), min(self.h, y + h + margin)
        sub = self.lab[Y0:Y1, X0:X1]
        region = self.lab[y:y + h, x:x + w]
        if seeds:
            ids = sorted({int(self.lab[sy, sx]) for sx, sy in seeds} - {0})
        else:
            inside = np.bincount(region.ravel(), minlength=len(self.lab_total))
            ids = [i for i in np.unique(region) if i and self.lab_total[i] >= 12 and inside[i] / self.lab_total[i] >= min_inside]
        sel = np.isin(sub, ids)
        others = (sub > 0) & ~sel
        mask = ndimage.binary_dilation(sel, iterations=grow) & ~ndimage.binary_dilation(others, iterations=2)
        if clip:
            keep = np.zeros_like(mask)
            keep[y - Y0:y - Y0 + h, x - X0:x - X0 + w] = True
            mask &= keep
        rgba = self.rgba[Y0:Y1, X0:X1].copy()
        rgba[..., 3] = np.where(mask, remap_alpha(rgba[..., 3], floor), 0)
        return trim(name, rgba, X0, Y0)

    def cut_box(self, name, box, floor=0):
        x, y, w, h = box
        rgba = self.rgba[y:y + h, x:x + w].copy()
        rgba[..., 3] = remap_alpha(rgba[..., 3], floor)
        return trim(name, rgba, x, y)


# --------------------------------------------------------------------------
# Registration: find where (scale / rotation / flip) a cut part sits in the finished symbol
# --------------------------------------------------------------------------
def _ref_rgb(ref_rgba, ds, pad, blur):
    a = ref_rgba.astype(np.float32) / 255.0
    al = a[..., 3:4]
    rgb = a[..., :3] * al + np.array([1.0, 0.0, 1.0], np.float32) * (1 - al)
    if ds != 1:
        im = Image.fromarray((rgb * 255).astype(np.uint8)).resize((rgb.shape[1] // ds, rgb.shape[0] // ds), Image.BILINEAR)
        rgb = np.asarray(im, np.float32) / 255.0
    if blur:
        rgb = ndimage.gaussian_filter(rgb, (blur, blur, 0))
    p = pad // ds
    return np.pad(rgb, ((p, p), (p, p), (0, 0)), constant_values=0.5)


def _template(part, s, r, flip, ds, blur):
    img = Image.fromarray(part.rgba)
    if flip:
        img = img.transpose(Image.FLIP_LEFT_RIGHT)
    img = img.resize((max(4, round(part.w * s / ds)), max(4, round(part.h * s / ds))), Image.LANCZOS)
    if r:
        img = img.rotate(r, resample=Image.BICUBIC, expand=True)
    t = np.asarray(img, np.float32) / 255.0
    m = ndimage.binary_erosion(t[..., 3] > 0.9, iterations=1).astype(np.float32)
    rgb = t[..., :3]
    if blur:
        rgb = ndimage.gaussian_filter(rgb, (blur, blur, 0))
    return rgb, m


def _ssd_map(refp, T, m):
    from scipy.signal import fftconvolve
    if T.shape[0] >= refp.shape[0] or T.shape[1] >= refp.shape[1] or m.sum() < 16:
        return None
    mk = m[::-1, ::-1]
    term1 = fftconvolve((refp ** 2).sum(-1), mk, mode="valid")
    term2 = sum(fftconvolve(refp[..., c], (m * T[..., c])[::-1, ::-1], mode="valid") for c in range(3))
    term3 = (m[..., None] * T ** 2).sum()
    return (term1 - 2 * term2 + term3) / m.sum()


def fit_part(part, ref_rgba, scales, rots=(0,), flips=(False,), search=None, pad=None):
    """Masked-SSD search for the part inside the reference render.

    `scales` is (lo, hi), `rots` degrees CCW, `search` limits the part centre to a
    ref-space box (x0, y0, x1, y1). Returns scale, rotation, flip, centre (ref px), err.
    """
    lo, hi = scales
    pad = pad if pad is not None else int(max(part.w, part.h) * hi * 0.6) + 8
    coarse = []
    refp = _ref_rgb(ref_rgba, 2, pad, 1)
    for flip in flips:
        for r in rots:
            for s in np.arange(lo, hi + 1e-6, 0.035):
                T, m = _template(part, s, r, flip, 2, 1)
                ssd = _ssd_map(refp, T, m)
                if ssd is None:
                    continue
                if search is not None:
                    yy, xx = np.mgrid[0:ssd.shape[0], 0:ssd.shape[1]]
                    cx = xx * 2 - pad + T.shape[1]
                    cy = yy * 2 - pad + T.shape[0]
                    x0, y0, x1, y1 = search
                    ssd = np.where((cx < x0) | (cx > x1) | (cy < y0) | (cy > y1), 1e9, ssd)
                iy, ix = np.unravel_index(np.argmin(ssd), ssd.shape)
                coarse.append((float(ssd[iy, ix]), float(s), r, flip, ix * 2 - pad, iy * 2 - pad))
    coarse.sort(key=lambda c: c[0])
    refp1 = _ref_rgb(ref_rgba, 1, pad, 0)
    best = None
    for _, s0, r0, flip, tx, ty in coarse[:4]:
        rr = [r0] if len(rots) == 1 else range(int(r0) - 2, int(r0) + 3)
        for s in np.arange(s0 - 0.025, s0 + 0.0251, 0.0125):
            for r in rr:
                T, m = _template(part, s, r, flip, 1, 0)
                # coarse template was made at half size: re-centre on the same middle point
                T2, _ = _template(part, s0, r0, flip, 2, 0)
                mx, my = tx + T2.shape[1] - T.shape[1] / 2, ty + T2.shape[0] - T.shape[0] / 2
                x0, y0 = int(mx) - 8 + pad, int(my) - 8 + pad
                crop = refp1[max(0, y0):y0 + T.shape[0] + 16, max(0, x0):x0 + T.shape[1] + 16]
                ssd = _ssd_map(crop, T, m)
                if ssd is None:
                    continue
                iy, ix = np.unravel_index(np.argmin(ssd), ssd.shape)
                err = float(ssd[iy, ix])
                if best is None or err < best[0]:
                    left, top = max(0, x0) + ix - pad, max(0, y0) + iy - pad
                    best = (err, float(s), r, flip, left + T.shape[1] / 2, top + T.shape[0] / 2)
    err, s, r, flip, cx, cy = best
    return dict(scale=round(s, 4), rotation=r, flip=flip, center=[round(cx, 2), round(cy, 2)], err=round(err, 5))


def smoothstep(e0, e1, v):
    t = np.clip((v - e0) / (e1 - e0), 0, 1)
    return t * t * (3 - 2 * t)


def feather_bottom(part, x_from, x_to, depth=18):
    """Soften a hard bottom cut (e.g. a neck) so it melts into what's underneath."""
    a = part.rgba[..., 3].astype(np.float32)
    for sx in range(int(x_from), int(x_to)):
        cx = sx - part.ox
        if not 0 <= cx < part.w:
            continue
        rows = np.nonzero(a[:, cx] > 8)[0]
        if len(rows) == 0:
            continue
        b = rows.max()
        r = np.arange(max(0, b - depth), b + 1)
        a[r, cx] *= smoothstep(0, depth, (b - r).astype(np.float32))
    part.rgba[..., 3] = a.astype(np.uint8)


def skin_mask(rgb):
    r, g, b = [rgb[..., i].astype(np.float32) + 1 for i in range(3)]
    gr, br = g / r, b / r
    m = (r > 80) & (r > g) & (g > b) & (gr > 0.45) & (gr < 0.85) & (br > 0.3) & (br < 0.75)
    return ndimage.binary_opening(m, iterations=1)


def match_skin(part, part_box, ref_rgba):
    """Recolour a part's skin toward a reference skin sample (parts painted apart drift in tone)."""
    x, y, w, h = part_box
    src = part.rgba[y - part.oy:y - part.oy + h, x - part.ox:x - part.ox + w, :3]
    src_m = skin_mask(src) & (part.rgba[y - part.oy:y - part.oy + h, x - part.ox:x - part.ox + w, 3] > 200)
    ref_m = skin_mask(ref_rgba[..., :3]) & (ref_rgba[..., 3] > 200)
    s = src[src_m].astype(np.float32)
    t = ref_rgba[..., :3][ref_m].astype(np.float32)
    mu_s, sd_s = s.mean(0), s.std(0) + 1e-3
    mu_t, sd_t = t.mean(0), t.std(0) + 1e-3
    rgb = part.rgba[..., :3].astype(np.float32)
    full_m = ndimage.gaussian_filter(skin_mask(part.rgba[..., :3]).astype(np.float32), 1.2)
    moved = (rgb - mu_s) * (0.5 + 0.5 * sd_t / sd_s) + mu_t
    out = rgb * (1 - full_m[..., None]) + moved * full_m[..., None]
    part.rgba[..., :3] = np.clip(out, 0, 255).astype(np.uint8)
    print(f"  skin match {part.name}: src mean {mu_s.round()} -> ref mean {mu_t.round()}")


def keep_largest(rgba_float, threshold=40, grow=3):
    """Zero the alpha of pixels not connected to the largest opaque island."""
    lab, n = ndimage.label(rgba_float[..., 3] > threshold)
    if n > 1:
        keep = np.argmax(np.bincount(lab.ravel())[1:]) + 1
        rgba_float[..., 3] *= ndimage.binary_dilation(lab == keep, iterations=grow)
    return rgba_float


# --------------------------------------------------------------------------
# Generated effect sprites (white, tinted via slot colour)
# --------------------------------------------------------------------------
def gen(name, size, fn):
    h, w = size
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    u = (xx + 0.5) / w * 2 - 1
    v = (yy + 0.5) / h * 2 - 1
    a = np.clip(fn(u, v), 0, 1)
    rgba = np.zeros((h, w, 4), np.uint8)
    rgba[..., :3] = 255
    rgba[..., 3] = (a * 255).astype(np.uint8)
    return Part(name, rgba, (0, 0))


def gen_glow(u, v):
    d = np.sqrt(u * u + v * v)
    return np.clip(1 - d, 0, 1) ** 2.2


def gen_rays(u, v):
    d = np.sqrt(u * u + v * v)
    th = np.arctan2(v, u)
    rays = (0.5 + 0.5 * np.cos(th * 14)) ** 5 * 0.85 + (0.5 + 0.5 * np.cos(th * 7 + 0.4)) ** 9 * 0.5
    return rays * np.clip(1 - d, 0, 1) ** 1.4 * smoothstep(0.05, 0.3, d) + 0.35 * np.clip(1 - d * 1.6, 0, 1) ** 2


def gen_sparkle(u, v):
    au, av = np.abs(u), np.abs(v)
    arm = np.exp(-au / 0.045) * np.clip(1 - av, 0, 1) ** 2.5 + np.exp(-av / 0.045) * np.clip(1 - au, 0, 1) ** 2.5
    ru, rv = (u + v) / 1.414, (u - v) / 1.414
    diag = 0.35 * (np.exp(-np.abs(ru) / 0.03) * np.clip(1 - np.abs(rv) * 1.8, 0, 1) ** 3 + np.exp(-np.abs(rv) / 0.03) * np.clip(1 - np.abs(ru) * 1.8, 0, 1) ** 3)
    core = np.exp(-(u * u + v * v) / 0.02)
    return arm + diag + core


def gen_shine(u, v):
    return np.exp(-(u / 0.42) ** 2) * 0.9


def standard_fx():
    return {"glow": gen("glow", (128, 128), gen_glow), "rays": gen("rays", (320, 320), gen_rays),
            "sparkle": gen("sparkle", (96, 96), gen_sparkle), "shine": gen("shine", (220, 56), gen_shine)}


# --------------------------------------------------------------------------
# Atlas packing
# --------------------------------------------------------------------------
def bleed(rgba):
    """Extrude edge colours into transparent texels to avoid dark filtering fringes."""
    out = rgba.copy()
    empty = rgba[..., 3] == 0
    if empty.any() and (~empty).any():
        _, (iy, ix) = ndimage.distance_transform_edt(empty, return_indices=True)
        out[..., :3] = rgba[iy, ix, :3]
    return out


def pack(parts, name, page_w=2048, pad=2):
    order = sorted(parts, key=lambda p: -p.h)
    x = y = pad
    shelf = 0
    places = {}
    for p in order:
        if x + p.w + pad > page_w:
            x = pad
            y += shelf + pad
            shelf = 0
        places[p.name] = (x, y)
        x += p.w + pad
        shelf = max(shelf, p.h)
    page_h = y + shelf + pad
    page_h = 1 << (page_h - 1).bit_length()
    page = np.zeros((page_h, page_w, 4), np.uint8)
    for p in parts:
        px, py = places[p.name]
        page[py:py + p.h, px:px + p.w] = bleed(p.rgba)
    lines = [f"{name}.png", f"size:{page_w},{page_h}", "filter:Linear,Linear", "pma:false"]
    for p in parts:
        px, py = places[p.name]
        lines += [p.name, f"bounds:{px},{py},{p.w},{p.h}"]
    return page, "\n".join(lines) + "\n"


def write_outputs(name, assets_dir, parts, skeleton):
    os.makedirs(assets_dir, exist_ok=True)
    page, atlas = pack(parts, name)
    Image.fromarray(page).save(os.path.join(assets_dir, f"{name}.png"), optimize=True)
    with open(os.path.join(assets_dir, f"{name}.atlas"), "w", newline="\n") as fh:
        fh.write(atlas)
    with open(os.path.join(assets_dir, f"{name}.json"), "w", newline="\n") as fh:
        json.dump(skeleton, fh, indent=1)
    print(f"atlas page {page.shape[1]}x{page.shape[0]}, {len(parts)} regions -> {os.path.abspath(assets_dir)}")


# --------------------------------------------------------------------------
# Rig description
# --------------------------------------------------------------------------
def rot(vx, vy, deg):
    """Rotate a y-down vector counter-clockwise on screen by `deg`."""
    t = math.radians(deg)
    return vx * math.cos(t) + vy * math.sin(t), -vx * math.sin(t) + vy * math.cos(t)


class Rig:
    def __init__(self):
        self.bones = []  # dicts with world ref positions
        self.world = {}
        self.slots = []
        self.constraints = []

    def bone(self, name, parent, at, length=0, **extra):
        self.world[name] = at
        self.bones.append(dict(name=name, parent=parent, at=at, length=length, **extra))

    def slot(self, name, bone, attachments, setup=None, color=None, blend=None):
        self.slots.append(dict(name=name, bone=bone, attachments=attachments, setup=setup, color=color, blend=blend))

    def physics(self, bone, **params):
        self.constraints.append(dict(name=f"{bone}_physics", type="physics", bone=bone, **params))


def place(part, anchor_sheet, at, scale, rotation=0.0, flip=False):
    """Attachment whose sheet point `anchor_sheet` lands on ref point `at`."""
    cx, cy = part.center_sheet
    vx, vy = (cx - anchor_sheet[0]) * scale, (cy - anchor_sheet[1]) * scale
    if flip:
        vx = -vx
    vx, vy = rot(vx, vy, rotation)
    return dict(part=part, center=(at[0] + vx, at[1] + vy), scale=scale, rotation=rotation, flip=flip)


def centered(part, at, scale, rotation=0.0):
    return dict(part=part, center=at, scale=scale, rotation=rotation, flip=False)


# --------------------------------------------------------------------------
# JSON writing (ref y-down -> Spine y-up)
# --------------------------------------------------------------------------
def r2(v):
    return round(float(v), 2)


def bone_frames(R):
    """World rotation (Spine degrees) per bone, so locals can be expressed in each parent's frame."""
    return {b["name"]: b.get("rotation", 0.0) for b in R.bones}


def to_local(R, world_rot, bone, point):
    bx, by = R.world[bone]
    dx, dy = point[0] - bx, -(point[1] - by)  # y-up
    t = math.radians(-world_rot[bone])
    return dx * math.cos(t) - dy * math.sin(t), dx * math.sin(t) + dy * math.cos(t)


def write_skeleton(R, hash_, events, bounds=(-260, -250, 520, 500)):
    world_rot = bone_frames(R)
    bones = []
    for b in R.bones:
        d = {"name": b["name"]}
        if b["parent"]:
            d["parent"] = b["parent"]
            lx, ly = to_local(R, world_rot, b["parent"], b["at"])
            if abs(lx) > 1e-3:
                d["x"] = r2(lx)
            if abs(ly) > 1e-3:
                d["y"] = r2(ly)
            rel = world_rot[b["name"]] - world_rot[b["parent"]]
            if abs(rel) > 1e-3:
                d["rotation"] = r2(rel)
        if b["length"]:
            d["length"] = b["length"]
        bones.append(d)
    slots, skin = [], {}
    for s in R.slots:
        d = {"name": s["name"], "bone": s["bone"]}
        if s["color"]:
            d["color"] = s["color"]
        if s["setup"]:
            d["attachment"] = s["setup"]
        if s["blend"]:
            d["blend"] = s["blend"]
        slots.append(d)
        entries = {}
        for att_name, a in s["attachments"].items():
            if "clip" in a:
                verts = []
                for p in a["clip"]:
                    verts += [r2(v) for v in to_local(R, world_rot, s["bone"], p)]
                entries[att_name] = {"type": "clipping", "end": a["end"], "vertexCount": len(a["clip"]), "vertices": verts}
                continue
            lx, ly = to_local(R, world_rot, s["bone"], a["center"])
            e = {"x": r2(lx), "y": r2(ly)}
            if a["part"].name != att_name:
                e["path"] = a["part"].name
            e["scaleX"] = r2(-a["scale"] if a["flip"] else a["scale"])
            e["scaleY"] = r2(a["scale"])
            rotation = a["rotation"] - world_rot[s["bone"]]
            if abs(rotation) > 1e-3:
                e["rotation"] = r2(rotation)
            e["width"], e["height"] = a["part"].w, a["part"].h
            entries[att_name] = e
        skin[s["name"]] = entries
    x, y, w, h = bounds
    return {
        "skeleton": {"hash": hash_, "spine": "4.3.00", "x": x, "y": y, "width": w, "height": h, "fps": 30},
        "bones": bones,
        "slots": slots,
        "constraints": R.constraints,
        "skins": [{"name": "default", "attachments": skin}],
        "events": {e: {} for e in events},
    }


# --------------------------------------------------------------------------
# Animation helpers
# --------------------------------------------------------------------------
EASE = {
    "inout": (0.42, 0.0, 0.58, 1.0),
    "out": (0.2, 0.9, 0.35, 1.0),
    "in": (0.55, 0.0, 0.85, 0.35),
    "back": (0.3, 1.6, 0.6, 1.0),
    "soft": (0.3, 0.6, 0.45, 1.0),
}


def _curve(t1, t2, vals1, vals2, ease):
    x1, y1, x2, y2 = EASE[ease]
    c = []
    for a, b in zip(vals1, vals2):
        c += [round(t1 + x1 * (t2 - t1), 4), round(a + y1 * (b - a), 4), round(t1 + x2 * (t2 - t1), 4), round(a + y2 * (b - a), 4)]
    return c


def tl(fields, keys):
    """keys: (time, values..., ease) where ease applies to the segment after the key."""
    out = []
    for i, k in enumerate(keys):
        t, vals, ease = k[0], list(k[1:-1]), k[-1]
        d = {"time": round(t, 4)}
        for f, v in zip(fields, vals):
            d[f] = round(v, 4)
        if i + 1 < len(keys) and ease not in (None, "linear"):
            if ease == "stepped":
                d["curve"] = "stepped"
            else:
                nxt = keys[i + 1]
                d["curve"] = _curve(t, nxt[0], vals, list(nxt[1:-1]), ease)
        out.append(d)
    return out


def rotate(*keys):
    return tl(["value"], keys)


def translate(*keys):
    return tl(["x", "y"], keys)


def scale(*keys):
    return tl(["x", "y"], keys)


def osc(period, amp, phase=0.0, base=0.0, steps=4, cycles=1):
    """Loop-perfect sine as Hermite-derived bezier keys."""
    total = period * cycles
    n = steps * cycles
    out = []
    w = 2 * math.pi / period
    for i in range(n + 1):
        t = total * i / n
        v = base + amp * math.sin(w * t + phase)
        k = {"time": round(t, 4), "value": round(v, 4)}
        if i < n:
            t2 = total * (i + 1) / n
            v2 = base + amp * math.sin(w * t2 + phase)
            m1 = amp * w * math.cos(w * t + phase)
            m2 = amp * w * math.cos(w * t2 + phase)
            dt = t2 - t
            k["curve"] = [round(t + dt / 3, 4), round(v + m1 * dt / 3, 4), round(t2 - dt / 3, 4), round(v2 - m2 * dt / 3, 4)]
        out.append(k)
    return out


def osc2(period, ax, ay, phase=0.0, bx=0.0, by=0.0, steps=4):
    xs = osc(period, ax, phase, bx, steps)
    ys = osc(period, ay, phase, by, steps)
    out = []
    for kx, ky in zip(xs, ys):
        k = {"time": kx["time"], "x": kx["value"], "y": ky["value"]}
        if "curve" in kx:
            k["curve"] = kx["curve"] + ky["curve"]
        out.append(k)
    return out


def hexc(c):
    return [int(c[i:i + 2], 16) / 255.0 for i in (0, 2, 4, 6)]


def rgba(*keys):
    out = []
    for i, (t, c, ease) in enumerate(keys):
        d = {"time": round(t, 4), "color": c}
        if i + 1 < len(keys) and ease not in (None, "linear"):
            d["curve"] = "stepped" if ease == "stepped" else _curve(t, keys[i + 1][0], hexc(c), hexc(keys[i + 1][1]), ease)
        out.append(d)
    return out


def attach(*keys):
    return [{"time": round(t, 4), "name": n} for t, n in keys]


def with_alpha(color, a):
    return color[:6] + f"{max(0, min(255, int(round(a * 255)))):02x}"


def twinkle(slot_color, t0, dur, peak=1.0, spin=90, grow=1.0):
    """Sparkle pop: scale 0 -> grow -> 0 with a spin and matching alpha."""
    mid = t0 + dur * 0.4
    end = t0 + dur
    slot = rgba((0, with_alpha(slot_color, 0), None) if t0 > 0 else (0, with_alpha(slot_color, 0), "stepped"),
                (t0, with_alpha(slot_color, 0), "out"), (mid, with_alpha(slot_color, peak), "in"), (end, with_alpha(slot_color, 0), None))
    if t0 == 0:
        slot = slot[1:]
    bone = {"scale": scale((0, 0, 0, None), (t0, 0, 0, "back"), (mid, grow, grow, "in"), (end, 0, 0, None)) if t0 > 0 else
            scale((0, 0, 0, "back"), (mid, grow, grow, "in"), (end, 0, 0, None)),
            "rotate": rotate((0, 0, None), (t0, 0, "linear"), (end, spin, None)) if t0 > 0 else rotate((0, 0, "linear"), (end, spin, None))}
    return slot, bone


# --------------------------------------------------------------------------
# Debug renders (setup pose, straight PIL compositing)
# --------------------------------------------------------------------------
def draw_attachment(canvas, a, off):
    p = a["part"]
    img = Image.fromarray(p.rgba)
    w, h = max(1, int(round(p.w * a["scale"]))), max(1, int(round(p.h * a["scale"])))
    img = img.resize((w, h), Image.LANCZOS)
    if a["flip"]:
        img = img.transpose(Image.FLIP_LEFT_RIGHT)
    if a["rotation"]:
        img = img.rotate(a["rotation"], resample=Image.BICUBIC, expand=True)
    cx, cy = a["center"]
    layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    layer.paste(img, (int(round(cx + off[0] - img.width / 2)), int(round(cy + off[1] - img.height / 2))))
    return Image.alpha_composite(canvas, layer)


def render_setup(R, path, ref_rgba, use_clip=True, skip=(), reveal=(), off=(90, 70), size=(560, 540)):
    """Setup pose (left) next to the finished reference symbol from the sheet (right).

    Slots named in `reveal` are drawn even if hidden or additive, to check effect placement.
    """
    canvas = Image.new("RGBA", size, (32, 22, 44, 255))
    clip = None
    clip_layer = None
    for s in R.slots:
        att = s["attachments"].get(s["setup"]) if s["setup"] and s["name"] not in skip else None
        if att is not None and "clip" in att:
            if use_clip:
                clip = att
                clip_layer = Image.new("RGBA", size, (0, 0, 0, 0))
            continue
        visible = att is not None and (s["name"] in reveal or (not (s["color"] and s["color"].endswith("00")) and s["blend"] is None))
        if visible:
            if clip is not None:
                clip_layer = draw_attachment(clip_layer, att, off)
            else:
                canvas = draw_attachment(canvas, att, off)
        if clip is not None and s["name"] == clip["end"]:
            mask = Image.new("L", size, 0)
            ImageDraw.Draw(mask).polygon([(x + off[0], y + off[1]) for x, y in clip["clip"]], fill=255)
            clip_layer.putalpha(Image.fromarray((np.asarray(clip_layer)[..., 3].astype(np.uint16) * np.asarray(mask) // 255).astype(np.uint8)))
            canvas = Image.alpha_composite(canvas, clip_layer)
            clip = None
    ref_bg = Image.new("RGBA", size, (32, 22, 44, 255))
    ref_bg.alpha_composite(Image.fromarray(ref_rgba), (int(off[0]), int(off[1])))
    both = Image.new("RGB", (size[0] * 2, size[1]))
    both.paste(canvas.convert("RGB"), (0, 0))
    both.paste(ref_bg.convert("RGB"), (size[0], 0))
    both.save(path)


def render_onion(attachments, order, path, off=(60, 60), size=(380, 400)):
    """Each swap attachment alone, then 50% blends of the first against the others."""
    tiles = []
    for name in order:
        c = Image.new("RGBA", size, (40, 40, 40, 255))
        tiles.append(draw_attachment(c, attachments[name], off))
    blends = [Image.blend(tiles[0], t, 0.5) for t in tiles[1:]]
    out = Image.new("RGB", (size[0] * (len(tiles) + len(blends)), size[1]))
    for i, t in enumerate(tiles + blends):
        out.paste(t.convert("RGB"), (i * size[0], 0))
    out.save(path)


def zoom(path, box, factor, out):
    """Upscaled crop of a debug render, handy for inspecting seams."""
    im = Image.open(path).crop(box)
    im.resize((im.width * factor, im.height * factor), Image.LANCZOS).save(out)
