# Odysseus WILD symbol preview

This is a browser-only PixiJS preview for the WILD symbol in `ChatGPT Image Sep 14, 2026, 04_50_17 PM.png`.

## Run locally

From the repository root:

```powershell
python -m http.server 4173
```

Open `http://localhost:4173/`.

## Pixi integration

`odysseus-wild-symbol.js` exports `OdysseusWildSymbol`. It receives the Pixi namespace and a loaded atlas texture, then exposes:

```js
const symbol = new OdysseusWildSymbol(PIXI, atlasTexture);
app.stage.addChild(symbol.root);
symbol.play("idle"); // "land" or "connect"
app.ticker.add((ticker) => symbol.update(ticker.deltaMS));
```

The three states are implemented as a lightweight layered `Container` rig, so no Spine or DragonBones runtime is needed. Pixi slices the supplied atlas at runtime into the empty frame, torso, two cape pieces, back hair, three facial expressions, laurels, WILD banner, and two effect textures. Idle, Land, and Connect animate and swap those layers independently.
