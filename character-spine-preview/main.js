(async () => {
  const { Application, Assets } = PIXI;
  const { Spine, SpineDebugRenderer } = spine;
  const stageEl = document.querySelector("#stage");
  const buttons = [...document.querySelectorAll("[data-animation]")];
  const timecode = document.querySelector("#timecode");
  const progress = document.querySelector("#progress");
  const nowPlaying = document.querySelector("#nowPlaying");
  const playState = document.querySelector("#playState");
  const playPause = document.querySelector("#playPause");
  const speed = document.querySelector("#speed");
  const mix = document.querySelector("#mix");
  const autoCycle = document.querySelector("#autoCycle");
  const debug = document.querySelector("#debug");
  const logEl = document.querySelector("#eventLog");

  const app = new Application();
  await app.init({ resizeTo: stageEl, backgroundAlpha: 0, antialias: true, autoDensity: true, resolution: Math.min(devicePixelRatio || 1, 2) });
  stageEl.appendChild(app.canvas);

  Assets.add({ alias: "revelerSkeleton", src: "./assets/wine_reveler.json" });
  Assets.add({ alias: "revelerAtlas", src: "./assets/wine_reveler.atlas" });
  await Assets.load(["revelerSkeleton", "revelerAtlas"]);

  const hero = Spine.from({ skeleton: "revelerSkeleton", atlas: "revelerAtlas" });
  app.stage.addChild(hero);
  let current = "idle";
  let paused = false;
  let cycling = false;
  const order = ["idle", "cheers", "sip"];

  const fmt = (seconds) => {
    const mins = Math.floor(seconds / 60).toString().padStart(2, "0");
    const secs = Math.floor(seconds % 60).toString().padStart(2, "0");
    const ms = Math.floor((seconds % 1) * 1000).toString().padStart(3, "0");
    return `${mins}:${secs}.${ms}`;
  };

  const log = (label, name = "") => {
    const item = document.createElement("li");
    item.innerHTML = `<b>${fmt(performance.now() / 1000)}</b> ${label}${name ? ` · ${name}` : ""}`;
    logEl.prepend(item);
    while (logEl.children.length > 24) logEl.lastChild.remove();
  };

  const applyMix = () => {
    const amount = Number(mix.value);
    hero.state.data.defaultMix = amount;
    for (const from of order) for (const to of order) if (from !== to) hero.state.data.setMix(from, to, amount);
    document.querySelector("#mixValue").value = `${amount.toFixed(2)}s`;
  };

  function play(name, source = "control") {
    current = name;
    buttons.forEach((button) => button.classList.toggle("active", button.dataset.animation === name));
    nowPlaying.textContent = name.toUpperCase();
    hero.state.setAnimation(0, name, true);
    if (source !== "cycle") log(source === "keyboard" ? "Key switch" : "Selected", name);
  }

  function layout() {
    const w = app.screen.width;
    const h = app.screen.height;
    const scale = Math.min((w - 32) / 1100, (h - 92) / 1500);
    hero.scale.set(scale);
    hero.position.set(w / 2, h / 2 - 15);
  }

  hero.state.addListener({
    event: (_entry, event) => log("Event", event.data.name),
    complete: (entry) => {
      if (!autoCycle.checked || cycling || entry.animation.name !== current) return;
      cycling = true;
      const next = order[(order.indexOf(current) + 1) % order.length];
      play(next, "cycle");
      log("Auto cycle", next);
      cycling = false;
    },
  });

  buttons.forEach((button) => button.addEventListener("click", () => play(button.dataset.animation)));
  document.querySelector("#restart").addEventListener("click", () => play(current));
  document.querySelector("#clearLog").addEventListener("click", () => { logEl.replaceChildren(); });
  playPause.addEventListener("click", () => {
    paused = !paused;
    hero.state.timeScale = paused ? 0 : Number(speed.value);
    playPause.textContent = paused ? "▶" : "Ⅱ";
    playPause.setAttribute("aria-label", paused ? "Play animation" : "Pause animation");
    playState.textContent = paused ? "PAUSED" : "PLAYING";
    log(paused ? "Paused" : "Resumed", current);
  });
  const scrub = document.querySelector('#scrub');
  scrub.addEventListener('input', () => {
    if (!paused) playPause.click();
    hero.state.clearTracks();
    hero.skeleton.setToSetupPose();
    const entry = hero.state.setAnimation(0, current, false);
    entry.mixDuration = 0;
    entry.trackTime = Number(scrub.value) / 100 * entry.animation.duration;
    hero.update(0);
  });
  speed.addEventListener("input", () => {
    const value = Number(speed.value);
    document.querySelector("#speedValue").value = `${value.toFixed(2)}×`;
    if (!paused) hero.state.timeScale = value;
  });
  mix.addEventListener("input", applyMix);
  debug.addEventListener("change", () => {
    if (debug.checked) {
      const renderer = new SpineDebugRenderer();
      renderer.drawMeshHull = false;
      renderer.drawMeshTriangles = false;
      renderer.drawBoundingBoxes = false;
      renderer.drawRegionAttachments = false;
      hero.debug = renderer;
    } else hero.debug = undefined;
  });
  window.addEventListener("keydown", (event) => {
    if (["INPUT", "TEXTAREA"].includes(document.activeElement?.tagName)) return;
    const name = order[Number(event.key) - 1];
    if (name) play(name, "keyboard");
    if (event.code === "Space") { event.preventDefault(); playPause.click(); }
  });

  app.ticker.add(() => {
    const entry = hero.state.getTrack(0);
    if (!entry) return;
    const t = entry.getAnimationTime();
    const d = entry.animation.duration || 1;
    timecode.textContent = `${fmt(t)} / ${fmt(d)}`;
    progress.style.width = `${Math.min(100, t / d * 100)}%`;
    if (!paused) scrub.value = t / d * 100;
  });
  app.renderer.on("resize", layout);
  applyMix();
  layout();
  play("idle", "startup");
  log("Rig loaded", "idle");
  Object.defineProperty(window, "reveler", { get: () => hero });
})().catch((error) => {
  console.error(error);
  const el = document.querySelector("#error");
  el.hidden = false;
  el.textContent = `Preview could not load: ${error.message}`;
});
