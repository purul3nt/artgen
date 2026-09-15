// Preview harness for the Odysseus Taverna Spine symbols.
// Game integration only needs the asset files plus the snippet in README.md.
(async () => {
  const { Application, Assets, Container } = PIXI;
  const { Spine, SpineDebugRenderer } = spine;

  const SYMBOLS = {
    wild: { label: "Wild", special: true, notes: { idle: "breathing, head bob, banner glint · loop", land: "drop, squash, roar, settle → idle", connect: "belly laugh, gold swirl, sparkles" } },
    bonus: { label: "Bonus", special: true, notes: { idle: "breathing, goblet swirl, twinkles · loop", land: "drop, squash, giggle, wine splash → idle", connect: "“Cheers!” toast, double splash, pink swirls" } },
    dz_helmet: { label: "DZ Helmet", special: true, notes: { idle: "medal shimmer, slash glow, helmet tilt · loop", land: "medal stamp, wreath clamp, ribbons flutter", connect: "coin spin, slash flash, helmet nod", appear: "halves slide together along the slash, medal flips in" } },
    dz_ship: { label: "DZ Ship", special: true, notes: { idle: "ship rocks, sail billows, vase sways · loop", land: "medal stamp, ship dips", connect: "coin spin, ship surges, vase hops", appear: "halves slide together along the slash, medal flips in" } },
    dz_chalice: { label: "DZ Chalice", special: true, notes: { idle: "wine slosh, grapes bob · loop", land: "medal stamp, wine splash", connect: "coin spin, toast tilt, grapes and drops pop", appear: "halves slide together along the slash, medal flips in" } },
    dz_trident: { label: "DZ Trident", special: true, notes: { idle: "trident float, leaves flutter · loop", land: "medal stamp, olives squash", connect: "coin spin, trident thrust, olives pop", appear: "halves slide together along the slash, medal flips in" } },
    helmet: { label: "Helmet", notes: { idle: "gentle tilt, gleams · loop", land: "clang and squash", connect: "battle nod, glints" } },
    laurel: { label: "Laurel", notes: { idle: "U of branches, tip glints · loop", land: "branches pulse", connect: "branches grow, leaves fly off" } },
    ship: { label: "Ship", notes: { idle: "rocking on the waves, sail billows · loop", land: "splash-down, bow and stern spray", connect: "surges forward, sail fills, big spray" } },
    amphora: { label: "Amphora", notes: { idle: "gentle sway · loop", land: "thud, squash, handles jiggle", connect: "hop and spin wobble, gold swooshes" } },
    chalice: { label: "Chalice", notes: { idle: "wine slosh, gem glow · loop", land: "clunk, wine slosh, drops", connect: "toast tilt, wine erupts, drops fly" } },
    grapes: { label: "Grapes", notes: { idle: "bunch bobs, leaves flutter · loop", land: "squash and bounce", connect: "jiggle, grapes and juice pop out" } },
    trident: { label: "Trident", notes: { idle: "float, tip glints · loop", land: "slam, prongs vibrate", connect: "thrust, prongs spread, glints" } },
    olive: { label: "Olive", notes: { idle: "gentle branch sway · loop", land: "olives squash, leaves spring", connect: "olives pop, a leaf flies off" } },
  };

  const stageEl = document.querySelector("#stage");
  const hudSymbol = document.querySelector("#hudSymbol");
  const hudState = document.querySelector("#hudState");
  const hudTime = document.querySelector("#hudTime");
  const logEl = document.querySelector("#log");
  const symbolList = document.querySelector("#symbolList");
  const stateButtons = [...document.querySelectorAll("[data-state]")];
  const appearButton = document.querySelector('[data-state="appear"]');
  const speed = document.querySelector("#speed");
  const loopConnect = document.querySelector("#loopConnect");
  const debugToggle = document.querySelector("#debug");
  const gridToggle = document.querySelector("#grid");

  const symbolButtons = Object.entries(SYMBOLS).map(([key, meta]) => {
    const b = document.createElement("button");
    b.type = "button";
    b.className = `symbol${meta.special ? " special" : ""}`;
    b.dataset.symbol = key;
    b.textContent = meta.label;
    b.setAttribute("aria-pressed", "false");
    symbolList.appendChild(b);
    return b;
  });

  const app = new Application();
  await app.init({ resizeTo: stageEl, backgroundAlpha: 0, antialias: true, autoDensity: true, resolution: Math.min(window.devicePixelRatio || 1, 2) });
  stageEl.appendChild(app.canvas);

  const loaded = new Set();
  async function ensureLoaded(key) {
    if (loaded.has(key)) return;
    Assets.add({ alias: `${key}Skeleton`, src: `./assets/odysseus_${key}.json` });
    Assets.add({ alias: `${key}Atlas`, src: `./assets/odysseus_${key}.atlas` });
    await Assets.load([`${key}Skeleton`, `${key}Atlas`]);
    loaded.add(key);
  }

  let hero = null;
  let cells = [];
  let loadToken = 0;
  const grid = new Container();

  const log = (text) => {
    const li = document.createElement("li");
    li.innerHTML = `<b>${(performance.now() / 1000).toFixed(2)}s</b> ${text}`;
    logEl.prepend(li);
    while (logEl.children.length > 40) logEl.lastChild.remove();
  };

  const makeSpine = (key) => {
    const s = Spine.from({ skeleton: `${key}Skeleton`, atlas: `${key}Atlas` });
    const mixes = s.state.data;
    mixes.defaultMix = 0.12;
    mixes.setMix("land", "idle", 0.25);
    mixes.setMix("connect", "idle", 0.3);
    mixes.setMix("idle", "land", 0);
    if (s.skeleton.data.findAnimation("appear")) {
      mixes.setMix("appear", "idle", 0.2);
      mixes.setMix("idle", "appear", 0);
    }
    s.state.timeScale = Number(speed.value);
    s.state.setAnimation(0, "idle", true);
    return s;
  };

  const activeState = () => stateButtons.find((b) => b.getAttribute("aria-pressed") === "true").dataset.state;
  const pressState = (name) => stateButtons.forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.state === name)));

  function play(s, name) {
    const { state } = s;
    if (name === "idle") {
      state.setAnimation(0, "idle", true);
    } else if (name === "land" || name === "appear") {
      state.setAnimation(0, name, false);
      state.addAnimation(0, "idle", true, 0);
    } else {
      const loop = loopConnect.checked;
      state.setAnimation(0, "connect", loop);
      if (!loop) state.addAnimation(0, "idle", true, 0);
    }
  }

  function select(name) {
    pressState(name);
    if (!hero) return;
    if (gridToggle.checked) cells.forEach((cell) => play(cell, name));
    else play(hero, name);
  }

  function layout() {
    if (!hero) return;
    const { width: w, height: h } = app.screen;
    const size = hero.skeleton.data.width || 520; // skeleton bounds include room for effects
    hero.scale.set(Math.min(w, h) / (size * 1.12));
    hero.position.set(w / 2, h / 2 - 6);
    const cell = Math.min(w, h - 30) / 3;
    cells.forEach((s, i) => {
      s.scale.set(cell / (size * 0.86));
      s.position.set(w / 2 + ((i % 3) - 1) * cell, h / 2 - 10 + (Math.floor(i / 3) - 1) * cell);
    });
  }

  function applyDebug() {
    if (!hero) return;
    if (debugToggle.checked) {
      const renderer = new SpineDebugRenderer();
      renderer.drawMeshHull = false;
      renderer.drawMeshTriangles = false;
      renderer.drawBoundingBoxes = false;
      renderer.drawRegionAttachments = false;
      renderer.drawClipping = true;
      hero.debug = renderer;
    } else {
      hero.debug = undefined;
    }
  }

  async function loadSymbol(key) {
    const token = ++loadToken;
    history.replaceState(null, "", `#${key}`);
    symbolButtons.forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.symbol === key)));
    document.querySelectorAll("[data-note]").forEach((el) => { el.textContent = SYMBOLS[key].notes[el.dataset.note] ?? ""; });
    hudSymbol.textContent = SYMBOLS[key].label.toLowerCase();
    await ensureLoaded(key);
    if (token !== loadToken) return; // a newer selection won

    if (hero) hero.destroy();
    cells.forEach((c) => c.destroy());
    hero = makeSpine(key);
    cells = Array.from({ length: 9 }, () => grid.addChild(makeSpine(key)));
    app.stage.addChildAt(hero, 0);
    hero.state.addListener({
      start: (entry) => log(`${key} start <b>${entry.animation.name}</b>`),
      complete: (entry) => { if (!entry.loop) log(`${key} complete ${entry.animation.name}`); },
      event: (_entry, event) => log(`${key} event <b>${event.data.name}</b>`),
    });
    applyDebug();
    hero.visible = !gridToggle.checked;
    grid.visible = gridToggle.checked;
    layout();
    // only the DZ medallions have an appear animation
    const hasAppear = !!hero.skeleton.data.findAnimation("appear");
    appearButton.hidden = !hasAppear;
    select(!hasAppear && activeState() === "appear" ? "idle" : activeState());
  }

  const timers = [];
  function demo() {
    if (!hero) return;
    timers.splice(0).forEach(clearTimeout);
    const inGrid = gridToggle.checked;
    const targets = inGrid ? cells : [hero];
    pressState("land");
    targets.forEach((s, i) => timers.push(setTimeout(() => play(s, "land"), (inGrid ? i % 3 : 0) * 180)));
    timers.push(setTimeout(() => {
      pressState("connect");
      const winners = inGrid ? cells.filter((_, i) => Math.floor(i / 3) === 1) : [hero];
      winners.forEach((s) => play(s, "connect"));
    }, inGrid ? 1500 : 1100));
  }

  app.stage.addChild(grid);
  stateButtons.forEach((b) => b.addEventListener("click", () => select(b.dataset.state)));
  symbolButtons.forEach((b) => b.addEventListener("click", () => loadSymbol(b.dataset.symbol)));
  speed.addEventListener("input", () => [hero, ...cells].forEach((s) => { if (s) s.state.timeScale = Number(speed.value); }));
  debugToggle.addEventListener("change", applyDebug);
  gridToggle.addEventListener("change", () => {
    if (!hero) return;
    hero.visible = !gridToggle.checked;
    grid.visible = gridToggle.checked;
    select(activeState());
  });
  document.querySelector("#demo").addEventListener("click", demo);
  window.addEventListener("keydown", (e) => {
    const name = { 1: "idle", 2: "land", 3: "connect", 4: "appear" }[e.key];
    if (name && !(name === "appear" && appearButton.hidden)) select(name);
  });

  app.ticker.add(() => {
    if (!hero) return;
    const entry = (grid.visible ? cells[4] : hero).state.getTrack(0);
    if (entry) {
      hudState.textContent = entry.animation.name;
      hudTime.textContent = `${entry.getAnimationTime().toFixed(2)}s / ${entry.animation.duration.toFixed(2)}s`;
    }
  });
  app.renderer.on("resize", layout);

  const initial = location.hash.slice(1) in SYMBOLS ? location.hash.slice(1) : "wild";
  await loadSymbol(initial);
  Object.defineProperty(window, "wild", { get: () => hero }); // handy for poking at the current rig from devtools
})().catch((error) => {
  console.error(error);
  const el = document.createElement("div");
  el.className = "error";
  el.textContent = `Could not start the preview: ${error.message}. Serve this folder over http (see README).`;
  document.querySelector(".stage-wrap").appendChild(el);
});
