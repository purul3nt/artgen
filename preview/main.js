import { OdysseusWildSymbol } from "./odysseus-wild-symbol.js";

const canvas = document.querySelector("#pixi-canvas");
const stage = document.querySelector(".stage-frame");
const stateReadout = document.querySelector("#stateReadout");
const phaseReadout = document.querySelector("#phaseReadout");
const replayButton = document.querySelector("#replayButton");
const autoCycle = document.querySelector("#autoCycle");
const toast = document.querySelector("#toast");
const cards = [...document.querySelectorAll("[data-state]")];

let activeState = "idle";
let cycleTimer = null;

function showToast(message) {
  toast.textContent = message;
  toast.classList.add("is-visible");
  window.clearTimeout(showToast.timer);
  showToast.timer = window.setTimeout(() => toast.classList.remove("is-visible"), 1600);
}

function setActiveCard(state) {
  activeState = state;
  stateReadout.textContent = state.toUpperCase();
  cards.forEach((card) => {
    const selected = card.dataset.state === state;
    card.classList.toggle("is-active", selected);
    card.setAttribute("aria-selected", String(selected));
  });
}

async function boot() {
  if (!window.PIXI) throw new Error("PixiJS did not load");

  const app = new window.PIXI.Application();
  await app.init({
    canvas,
    backgroundAlpha: 0,
    antialias: true,
    autoDensity: true,
    resolution: Math.min(window.devicePixelRatio || 1, 2),
    resizeTo: stage,
  });

  const atlas = await window.PIXI.Assets.load("./assets/wild-atlas.png");
  const symbol = new OdysseusWildSymbol(window.PIXI, atlas);
  app.stage.addChild(symbol.root);

  const layout = () => symbol.layout(stage.clientWidth, stage.clientHeight);
  layout();
  window.addEventListener("resize", layout);

  const play = (state, announce = true) => {
    setActiveCard(state);
    symbol.play(state);
    if (announce) showToast(`${state[0].toUpperCase()}${state.slice(1)} animation playing`);
  };

  cards.forEach((card) => card.addEventListener("click", () => play(card.dataset.state)));
  replayButton.addEventListener("click", () => play(activeState));
  autoCycle.addEventListener("change", () => {
    window.clearInterval(cycleTimer);
    cycleTimer = autoCycle.checked ? window.setInterval(() => {
      const next = { idle: "land", land: "connect", connect: "idle" }[activeState];
      play(next, false);
    }, 2400) : null;
    if (autoCycle.checked) showToast("Auto-cycle enabled");
  });
  window.addEventListener("keydown", (event) => {
    if (event.key === "1") play("idle");
    if (event.key === "2") play("land");
    if (event.key === "3") play("connect");
    if (event.code === "Space") { event.preventDefault(); play(activeState); }
  });

  app.ticker.add((ticker) => {
    symbol.update(ticker.deltaMS);
    phaseReadout.textContent = symbol.phaseLabel;
  });
}

boot().catch((error) => {
  console.error(error);
  phaseReadout.textContent = "runtime unavailable";
  showToast("PixiJS could not load — check the connection");
});
