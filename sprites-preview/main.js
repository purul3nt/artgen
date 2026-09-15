// PixiJS 8 player for the Odysseus sprite sheets.
// Loads both 10x7 RGBA sheets (sip + cheers), slices them into 70 frames,
// and drives an AnimatedSprite at 14 fps with seamless looping.

const SPRITE_BASE = "../sprites";
const COLS = 10;
const ROWS = 7;
const FRAME_W = 240;
const FRAME_H = 240;
const BASE_FPS = 14;

const SHEETS = {
  sip:    `${SPRITE_BASE}/odysseus_sip_loop_sheet_10x7.png`,
  cheers: `${SPRITE_BASE}/odysseus_cheers_loop_sheet_10x7.png`,
};

const checkerTexture = (() => {
  // 16x16 checker so the transparent BG is visible behind the sprite.
  const size = 16;
  const c = document.createElement("canvas");
  c.width = c.height = size * 2;
  const g = c.getContext("2d");
  g.fillStyle = "#2a1a14"; g.fillRect(0, 0, size * 2, size * 2);
  g.fillStyle = "#1a0e08"; g.fillRect(0, 0, size, size); g.fillRect(size, size, size, size);
  return PIXI.Texture.from(c);
})();

async function sliceSheet(url) {
  const source = await PIXI.Assets.load(url);
  const tex = source instanceof PIXI.Texture ? source : PIXI.Texture.from(source);
  const frames = [];
  for (let r = 0; r < ROWS; r++) {
    for (let c = 0; c < COLS; c++) {
      const rect = new PIXI.Rectangle(c * FRAME_W, r * FRAME_H, FRAME_W, FRAME_H);
      frames.push(new PIXI.Texture({ source: tex.source, frame: rect }));
    }
  }
  return frames;
}

async function main() {
  const host = document.getElementById("pixi-host");
  const app = new PIXI.Application();
  await app.init({
    backgroundAlpha: 0,
    resizeTo: host,
    antialias: true,
    autoDensity: true,
    resolution: Math.min(window.devicePixelRatio || 1, 2),
  });
  host.appendChild(app.canvas);

  const checker = new PIXI.TilingSprite({
    texture: checkerTexture,
    width: app.screen.width,
    height: app.screen.height,
  });
  app.stage.addChild(checker);

  const sets = {
    sip:    await sliceSheet(SHEETS.sip),
    cheers: await sliceSheet(SHEETS.cheers),
  };

  const sprite = new PIXI.AnimatedSprite(sets.sip);
  sprite.anchor.set(0.5);
  sprite.x = app.screen.width / 2;
  sprite.y = app.screen.height / 2;
  // Fit the 200px frame into the larger stage.
  const targetSize = Math.min(app.screen.width, app.screen.height) * 0.78;
  sprite.scale.set(targetSize / FRAME_W);
  sprite.animationSpeed = BASE_FPS / 60;
  sprite.loop = true;
  sprite.play();
  app.stage.addChild(sprite);

  // Keep the sprite and checker sized to the stage.
  const onResize = () => {
    checker.width = app.screen.width;
    checker.height = app.screen.height;
    sprite.x = app.screen.width / 2;
    sprite.y = app.screen.height / 2;
    const t = Math.min(app.screen.width, app.screen.height) * 0.78;
    sprite.scale.set(t / FRAME_W);
  };
  window.addEventListener("resize", onResize);

  // Loop picker.
  const loopLabel = document.getElementById("loopLabel");
  const buttons = document.querySelectorAll(".loop-button");
  buttons.forEach((btn) => {
    btn.addEventListener("click", () => {
      const key = btn.dataset.loop;
      if (!sets[key]) return;
      buttons.forEach((b) => b.classList.toggle("is-active", b === btn));
      sprite.textures = sets[key];
      loopLabel.textContent = `${key} · 14 fps`;
      sprite.gotoAndPlay(0);
    });
  });

  // Speed slider.
  const speed = document.getElementById("speed");
  const speedLabel = document.getElementById("speedLabel");
  speed.addEventListener("input", () => {
    const v = parseFloat(speed.value);
    sprite.animationSpeed = (BASE_FPS / 60) * v;
    speedLabel.textContent = `${v.toFixed(2)}×`;
  });

  // Pause toggle.
  document.getElementById("paused").addEventListener("change", (e) => {
    sprite[e.target.checked ? "stop" : "play"]();
  });

  // Checker bg toggle.
  document.getElementById("checker").addEventListener("change", (e) => {
    checker.visible = e.target.checked;
  });

  // Frame readout.
  const frameReadout = document.getElementById("frameReadout");
  app.ticker.add(() => {
    const idx = sprite.currentFrame;
    frameReadout.textContent = `frame ${String(idx).padStart(3, "0")} / ${String(sprite.totalFrames - 1).padStart(3, "0")}`;
  });
}

main().catch((err) => {
  console.error(err);
  document.getElementById("pixi-host").innerHTML =
    `<pre style="color:#f88;padding:16px;">${err.message}</pre>`;
});
