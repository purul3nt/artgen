"""Finalize v3 logo: knock out the white background to alpha."""

from pathlib import Path
from PIL import Image
import numpy as np

ROOT = Path(r"C:\Users\hanna\Documents\GitHub\artgen")
SRC = ROOT / "_v3_raw.jpg"
OUT = ROOT / "odysseus_tavern_logo.png"


def main() -> None:
    img = Image.open(SRC).convert("RGB")
    arr = np.array(img).astype(np.float32)
    r, g, b = arr[..., 0], arr[..., 1], arr[..., 2]
    chroma = np.maximum(np.maximum(r, g), b) - np.minimum(np.minimum(r, g), b)
    is_colorful = chroma > 25
    is_neutral_bright = (chroma <= 25) & (np.maximum(np.maximum(r, g), b) >= 60)
    alpha = np.clip(chroma * 1.5, 0, 255).astype(np.uint8)
    alpha[is_neutral_bright] = 0
    alpha[is_colorful] = 255
    rgba = np.dstack([arr.astype(np.uint8), alpha])
    Image.fromarray(rgba, mode="RGBA").save(OUT, format="PNG")
    print(f"Saved {OUT} ({OUT.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
