"""Extract the ODYSSEUS TAVERN logo with a clean transparent background.

Strategy:
1. Crop tight to just the gold "ODYSSEUS" text + wooden "TAVERN" sign.
   Empirically (from per-row gold/wood analysis) this is x=510..1340, y=0..200
   in the 1672x941 source. The gold frame border + slot symbols sit just
   below y=200, so we cut above them.
2. Skip rembg (it grouped cape + frame + slot symbols as foreground).
3. Strict color filter:
   - KEEP: bright gold (R high, G mid, B low, sat < 0.8) and warm wood
     (warm tone, sat < 0.65).
   - DROP: red cape (R high, G and B low, sat > 0.35), very dark pixels,
     and any bright non-gold accents (cool blues, purples).
4. Morphology: erode then dilate to kill stray cape specks.
5. Tight crop to the alpha bounding box, save PNG.
"""

import sys
from pathlib import Path
from PIL import Image
import numpy as np

ROOT = Path(r"C:\Users\hanna\Documents\GitHub\artgen")
SRC = Path(
    r"C:\Users\hanna\.minimax\v2\assets\2026\09\15\10-07-07-174-"
    r"asset_20260915-100707-174_bc0c594245f1_e3e35102-ChatGPT Image Sep 13, "
    r"2026, 10_40_31 AM.png"
)
OUT = ROOT / "odysseus_tavern_logo.png"
DEBUG = ROOT / "_debug_crops"
DEBUG.mkdir(exist_ok=True)


def crop_logo(img: Image.Image) -> Image.Image:
    """Tight crop: ODYSSEUS gold text + TAVERN wooden sign, nothing else."""
    return img.crop((510, 0, 1340, 200))


def strict_logo_mask(arr: np.ndarray) -> np.ndarray:
    """Return a boolean mask selecting gold + warm-wood pixels only.

    arr is H x W x 3 float32 in 0..255.
    """
    r, g, b = arr[..., 0], arr[..., 1], arr[..., 2]
    mx = np.maximum(np.maximum(r, g), b)
    mn = np.minimum(np.minimum(r, g), b)
    sat = np.where(mx > 0, (mx - mn) / np.maximum(mx, 1), 0)

    # Bright gold: high V, R >= G >= B, hue around 35-55 deg (yellow-orange).
    # r > 150, g > 90, b < 180, r-g < 100 (else red), r-b > 40, V > 160
    gold = (r > 150) & (g > 90) & (g < 240) & (b < 200) & (r >= g - 15) & (r - g < 110) & (r - b > 30) & (mx > 150) & (sat < 0.88)

    # Warm wood: mid-tone, R > B but not bright, low saturation.
    # r in [80,220], g in [40,200], b < 150, r >= g - 15, g >= b - 15, sat < 0.7
    wood = (r >= 70) & (r < 235) & (g >= 35) & (g < 210) & (b < 160) & (r >= g - 20) & (g >= b - 25) & (sat < 0.78)

    # Drop saturated red (cape) and very dark / blue accents.
    red = (r > g + 40) & (r > b + 60) & (sat > 0.35)
    dark = mx < 35
    blue_accent = (b > r + 30) & (b > 130)

    keep = (gold | wood) & ~red & ~dark & ~blue_accent
    return keep


def clean_mask(mask: np.ndarray) -> np.ndarray:
    """Erode then dilate to drop isolated cape specks and bridge tiny gaps."""
    # Manual 3x3 erosion then dilation via numpy, keeps things dependency-free.
    def erode(m: np.ndarray) -> np.ndarray:
        from scipy.ndimage import binary_erosion  # type: ignore
        return binary_erosion(m, iterations=1)

    def dilate(m: np.ndarray) -> np.ndarray:
        from scipy.ndimage import binary_dilation  # type: ignore
        return binary_dilation(m, iterations=2)

    try:
        mask = erode(mask)
        mask = dilate(mask)
    except Exception:
        # scipy not available: do nothing (mask already strict enough).
        pass
    return mask


def trim_to_content(rgba: Image.Image, pad: int = 8) -> Image.Image:
    arr = np.array(rgba)
    alpha = arr[..., 3]
    ys, xs = np.where(alpha > 8)
    if ys.size == 0:
        return rgba
    y0 = max(int(ys.min()) - pad, 0)
    y1 = min(int(ys.max()) + pad + 1, rgba.height)
    x0 = max(int(xs.min()) - pad, 0)
    x1 = min(int(xs.max()) + pad + 1, rgba.width)
    return rgba.crop((x0, y0, x1, y1))


def main() -> int:
    img = Image.open(SRC).convert("RGB")
    cropped = crop_logo(img)
    print(f"Cropped: {cropped.size}")
    cropped.save(DEBUG / "01_cropped.png")

    arr = np.array(cropped).astype(np.float32)
    keep = strict_logo_mask(arr)
    print(f"Strict mask coverage: {keep.mean()*100:.1f}%")
    Image.fromarray((keep * 255).astype(np.uint8)).save(DEBUG / "02_mask.png")

    keep = clean_mask(keep)
    print(f"After clean: {keep.mean()*100:.1f}%")
    Image.fromarray((keep * 255).astype(np.uint8)).save(DEBUG / "03_mask_clean.png")

    rgba_arr = np.dstack([arr.astype(np.uint8), (keep.astype(np.uint8) * 255)])
    rgba = Image.fromarray(rgba_arr, mode="RGBA")
    rgba.save(DEBUG / "04_rgba.png")

    trimmed = trim_to_content(rgba, pad=12)
    print(f"Trimmed: {trimmed.size}")
    trimmed.save(OUT, format="PNG")
    print(f"Saved: {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
