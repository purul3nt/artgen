const clamp = (value, min = 0, max = 1) => Math.min(max, Math.max(min, value));
const easeOut = (value) => 1 - (1 - value) ** 3;
const easeInOut = (value) => value < 0.5 ? 4 * value ** 3 : 1 - ((-2 * value + 2) ** 3) / 2;
const lerp = (a, b, t) => a + (b - a) * t;

const ATLAS = {
  frame: [381, 7, 359, 380],
  torso: [11, 390, 450, 216],
  capeLeft: [6, 615, 319, 134],
  capeRight: [214, 654, 208, 146],
  capeLower: [136, 792, 377, 127],
  laurelLeft: [442, 398, 180, 280],
  laurelRight: [657, 408, 175, 271],
  medallion: [569, 528, 116, 117],
  banner: [413, 683, 473, 127],
  headLand: [732, 11, 246, 274],
  headConnect: [979, 18, 240, 265],
  headIdle: [1200, 17, 247, 268],
  hairBack: [737, 279, 315, 278],
  goldFlare: [8, 880, 442, 190],
  redFlare: [815, 845, 620, 225],
};

export class OdysseusWildSymbol {
  constructor(PIXI, atlas) {
    this.state = "idle";
    this.elapsed = 0;
    this.clock = 0;
    this.phaseLabel = "layered breathing loop";

    this.root = new PIXI.Container();
    this.rig = new PIXI.Container();
    this.root.addChild(this.rig);

    const texture = (name) => {
      const [x, y, width, height] = ATLAS[name];
      return new PIXI.Texture({ source: atlas.source, frame: new PIXI.Rectangle(x, y, width, height) });
    };
    const sprite = (name, parent, x, y, scale = 1) => {
      const view = new PIXI.Sprite(texture(name));
      view.anchor.set(0.5);
      view.position.set(x, y);
      view.scale.set(scale);
      parent.addChild(view);
      return view;
    };

    this.aura = new PIXI.Graphics();
    this.aura.circle(0, 2, 214).fill({ color: 0x9f3fca, alpha: 0.085 });
    this.aura.circle(0, 2, 165).fill({ color: 0xd9486b, alpha: 0.06 });
    this.rig.addChild(this.aura);

    this.shadow = new PIXI.Graphics();
    this.shadow.ellipse(0, 192, 138, 22).fill({ color: 0x07030e, alpha: 0.52 });
    this.rig.addChild(this.shadow);

    this.goldFlare = sprite("goldFlare", this.rig, -6, 111, 0.84);
    this.goldFlare.alpha = 0;
    this.redFlare = sprite("redFlare", this.rig, 8, 108, 0.62);
    this.redFlare.alpha = 0;

    this.frame = sprite("frame", this.rig, 0, 0, 1);

    this.content = new PIXI.Container();
    this.rig.addChild(this.content);
    this.contentMask = new PIXI.Graphics();
    this.contentMask.roundRect(-144, -142, 288, 286, 8).fill(0xffffff);
    this.rig.addChild(this.contentMask);
    this.content.mask = this.contentMask;

    this.capeGroup = new PIXI.Container();
    this.content.addChild(this.capeGroup);
    this.capeLower = sprite("capeLower", this.capeGroup, 0, 82, 0.8);
    this.capeLeft = sprite("capeLeft", this.capeGroup, -40, 38, 0.86);
    this.capeLeft.rotation = -0.035;
    this.capeRight = sprite("capeRight", this.capeGroup, 69, 51, 0.86);
    this.capeRight.rotation = 0.035;

    this.hairBack = sprite("hairBack", this.content, 35, -48, 0.79);
    this.hairBack.alpha = 0.88;
    this.torso = sprite("torso", this.content, -2, 73, 0.74);

    this.headGroup = new PIXI.Container();
    this.headGroup.position.set(40, -48);
    this.content.addChild(this.headGroup);
    this.heads = {
      idle: sprite("headIdle", this.headGroup, 0, 0, 0.9),
      land: sprite("headLand", this.headGroup, 0, 0, 0.9),
      connect: sprite("headConnect", this.headGroup, 0, 0, 0.9),
    };
    this.heads.idle.alpha = 1;
    this.heads.land.alpha = 0;
    this.heads.connect.alpha = 0;

    this.ornaments = new PIXI.Container();
    this.rig.addChild(this.ornaments);
    this.laurels = new PIXI.Container();
    this.laurels.position.set(0, 82);
    this.ornaments.addChild(this.laurels);
    this.laurelLeft = sprite("laurelLeft", this.laurels, -124, 0, 0.66);
    this.laurelRight = sprite("laurelRight", this.laurels, 125, 1, 0.66);
    this.medallion = sprite("medallion", this.ornaments, 0, 111, 0.62);
    this.banner = sprite("banner", this.ornaments, 0, 144, 0.77);

    this.shimmer = new PIXI.Graphics();
    this.shimmer.moveTo(-172, -224).lineTo(164, 132).stroke({ width: 5, color: 0xfff2bc, alpha: 0.72 });
    this.rig.addChild(this.shimmer);

    this.impact = new PIXI.Graphics();
    this.rig.addChild(this.impact);
    this.particles = Array.from({ length: 18 }, (_, index) => {
      const particle = new PIXI.Graphics();
      particle.circle(0, 0, index % 3 === 0 ? 4 : 2.5).fill({ color: index % 2 ? 0xf4bf63 : 0xe84e6e, alpha: 0.95 });
      particle.visible = false;
      this.rig.addChild(particle);
      return { view: particle, angle: (Math.PI * 2 * index) / 18, distance: 92 + (index % 4) * 18, speed: 0.78 + (index % 5) * 0.1 };
    });
  }

  layout(width, height) {
    const scale = Math.min(width / 530, height / 530);
    this.root.position.set(width * 0.5, height * 0.49);
    this.root.scale.set(scale);
  }

  play(state) {
    this.state = state;
    this.elapsed = 0;
    this.phaseLabel = state === "idle" ? "layered breathing loop" : state === "land" ? "impact + expression swap" : "celebration flourish";
    this.impact.alpha = 0;
    this.goldFlare.alpha = 0;
    this.redFlare.alpha = 0;
    this.particles.forEach(({ view }) => { view.visible = false; });
  }

  update(deltaMs) {
    const dt = Math.min(deltaMs / 1000, 0.05);
    this.clock += dt;
    this.elapsed += dt;
    this.shimmer.alpha = 0.16 + Math.sin(this.clock * 1.7) * 0.09;
    this.shimmer.position.x = Math.sin(this.clock * 0.75) * 22;
    this.crossfadeHeads(this.state);

    if (this.state === "idle") this.updateIdle();
    if (this.state === "land") this.updateLand();
    if (this.state === "connect") this.updateConnect();
  }

  crossfadeHeads(target) {
    Object.entries(this.heads).forEach(([name, head]) => {
      head.alpha += ((name === target ? 1 : 0) - head.alpha) * 0.22;
      head.visible = head.alpha > 0.015;
    });
  }

  updateIdle() {
    const breath = Math.sin(this.clock * 2.15);
    const capeWave = Math.sin(this.clock * 1.35);
    this.rig.position.y = breath * 3;
    this.rig.rotation = breath * 0.008;
    this.content.position.y = breath * 2;
    this.content.rotation = 0;
    this.content.scale.set(1);
    this.torso.scale.set(0.74 + breath * 0.008, 0.74 - breath * 0.006);
    this.headGroup.position.y = -48 + breath * 1.8;
    this.headGroup.rotation = breath * 0.012;
    this.capeLeft.rotation = -0.035 + capeWave * 0.025;
    this.capeRight.rotation = 0.035 - capeWave * 0.02;
    this.capeLeft.position.x = -54 - capeWave * 3;
    this.capeRight.position.x = 69 + capeWave * 3;
    this.capeLower.rotation = capeWave * 0.012;
    this.hairBack.rotation = -capeWave * 0.014;
    this.laurels.position.y = 82;
    this.laurels.rotation = 0;
    this.laurels.scale.set(1 + breath * 0.006);
    this.medallion.position.y = 111 + breath * 0.8;
    this.medallion.scale.set(0.62);
    this.banner.scale.set(0.77);
    this.banner.position.y = 144 + breath * 1.2;
    this.aura.alpha = 0.76 + breath * 0.11;
    this.shadow.scale.set(1 - breath * 0.02, 1);
  }

  updateLand() {
    const duration = 1.08;
    const t = clamp(this.elapsed / duration);
    const hit = easeOut(clamp(this.elapsed / 0.3));
    const settle = easeInOut(clamp((this.elapsed - 0.3) / 0.78));
    this.phaseLabel = t < 0.28 ? "impact + shout" : t < 1 ? "layer settle" : "landed";

    if (this.elapsed < 0.3) {
      this.content.position.y = lerp(-76, 14, hit);
      this.content.scale.set(lerp(0.92, 1.045, hit), lerp(1.04, 0.92, hit));
      this.headGroup.rotation = lerp(-0.05, 0.035, hit);
      this.banner.position.y = lerp(128, 153, hit);
      this.banner.scale.set(lerp(0.72, 0.83, hit), lerp(0.84, 0.69, hit));
      this.laurels.position.y = lerp(72, 88, hit);
      this.capeLeft.rotation = -0.1;
      this.capeRight.rotation = 0.11;
      this.impact.alpha = 0.88;
      this.drawImpact(0.64 + hit * 0.3);
      this.shadow.scale.set(0.72 + hit * 0.42, 1);
    } else {
      this.content.position.y = lerp(14, 0, settle);
      this.content.scale.set(lerp(1.045, 1, settle), lerp(0.92, 1, settle));
      this.headGroup.rotation = lerp(0.035, 0, settle);
      this.banner.position.y = lerp(153, 144, settle);
      this.banner.scale.set(lerp(0.83, 0.77, settle), lerp(0.69, 0.77, settle));
      this.laurels.position.y = lerp(88, 82, settle);
      this.capeLeft.rotation = lerp(-0.1, -0.035, settle);
      this.capeRight.rotation = lerp(0.11, 0.035, settle);
      this.impact.alpha = Math.max(0, 0.88 - settle * 1.25);
      this.drawImpact(0.94 + settle * 0.25);
      this.shadow.scale.set(1.14 - settle * 0.14, 1);
    }
    this.aura.alpha = 0.92;
  }

  updateConnect() {
    const duration = 1.45;
    const t = clamp(this.elapsed / duration);
    const surge = Math.sin(t * Math.PI);
    const pop = easeOut(clamp(this.elapsed / 0.36));
    this.phaseLabel = t < 0.24 ? "expression swap" : t < 0.82 ? "connected + laughing" : "flourish cooldown";

    this.content.position.y = -surge * 6;
    this.content.rotation = Math.sin(this.elapsed * 11) * surge * 0.012;
    this.headGroup.position.y = -48 - surge * 7;
    this.headGroup.rotation = Math.sin(this.elapsed * 8) * surge * 0.025;
    this.torso.scale.set(0.74 + surge * 0.026, 0.74 + surge * 0.018);
    this.capeLeft.rotation = -0.035 - surge * 0.14;
    this.capeRight.rotation = 0.035 + surge * 0.13;
    this.capeLeft.position.x = -54 - surge * 13;
    this.capeRight.position.x = 67 + surge * 12;
    this.capeLower.rotation = Math.sin(this.elapsed * 4) * surge * 0.035;
    this.hairBack.rotation = Math.sin(this.elapsed * 5) * surge * 0.035;
    this.laurels.scale.set(1 + surge * 0.045);
    this.laurels.rotation = Math.sin(this.elapsed * 9) * surge * 0.01;
    this.medallion.scale.set(0.62 + surge * 0.04);
    this.banner.scale.set(0.77 + surge * 0.065, 0.77 + surge * 0.04);
    this.banner.position.y = 144 - surge * 5;
    this.aura.alpha = 0.84 + surge * 0.78;
    this.goldFlare.alpha = surge * 0.42;
    this.goldFlare.scale.set(0.44 + pop * 0.12);
    this.redFlare.alpha = surge * 0.35;
    this.redFlare.scale.set(0.42 + surge * 0.1);
    this.redFlare.rotation = -0.06 + Math.sin(this.clock * 2) * 0.025;
    this.impact.alpha = surge * 0.82;
    this.drawImpact(0.74 + surge * 0.72, 0xffd985);
    this.shadow.scale.set(1 + surge * 0.11, 1);

    this.particles.forEach((particle) => {
      const progress = clamp((this.elapsed - 0.08) / 1.08);
      particle.view.visible = progress > 0 && progress < 1;
      const radius = particle.distance * easeOut(progress) * particle.speed;
      particle.view.position.set(Math.cos(particle.angle) * radius, Math.sin(particle.angle) * radius);
      particle.view.alpha = Math.sin(progress * Math.PI);
    });
  }

  drawImpact(scale, color = 0xffa84a) {
    this.impact.clear();
    this.impact.circle(0, 0, 128).stroke({ width: 3, color, alpha: 0.82 });
    for (let i = 0; i < 8; i += 1) {
      const angle = (Math.PI * 2 * i) / 8;
      const inner = 134;
      const outer = i % 2 ? 158 : 181;
      this.impact.moveTo(Math.cos(angle) * inner, Math.sin(angle) * inner).lineTo(Math.cos(angle) * outer, Math.sin(angle) * outer).stroke({ width: i % 2 ? 3 : 5, color, alpha: 0.74 });
    }
    this.impact.scale.set(scale);
  }
}
