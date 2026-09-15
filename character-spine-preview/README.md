# Wine Reveler — Spine animation preview

This folder contains a Spine 4.3 JSON rig and a PixiJS 8 review surface built
from `ChatGPT Image Sep 15, 2026, 09_13_25 AM.png`.

## Preview

Serve this directory over HTTP and open it in a browser:

```powershell
node server.mjs
```

Then open <http://localhost:4190>.

The preview exposes `idle`, `cheers`, and `sip`; keys 1–3 switch between them
and Space pauses. All clips start and end on the same neutral pose, and the
transition-mix slider controls Spine's cross-fade duration.

## Rebuild the rig

Run the repository's builder with Python, Pillow, NumPy, and SciPy available:

```powershell
python ../odysseus-wild-spine/tools/build_reveler.py
```

Generated runtime files are written to `assets/wine_reveler.{json,atlas,png}`.
