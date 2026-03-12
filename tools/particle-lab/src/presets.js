// ─────────────────────────────────────────────────────────
// Built-in particle presets for the Arena game
// ─────────────────────────────────────────────────────────

const PRESETS = [
  // ══════════════════════════════════════════════
  // COMBAT
  // ══════════════════════════════════════════════
  {
    name: 'melee-hit',
    version: 1,
    duration: 0.3,
    loop: false,
    tags: ['combat', 'impact'],
    emitter: {
      burstMode: true,
      burstCount: 18,
      spawnShape: 'point',
      angle: { min: 0, max: 360 },
      speed: { min: 60, max: 160 },
      gravity: { x: 0, y: 40 },
      friction: 0.02,
    },
    particle: {
      lifetime: { min: 0.15, max: 0.45 },
      shape: 'circle',
      size: { start: { min: 2, max: 5 }, end: { min: 0, max: 1 }, easing: 'easeOutQuad' },
      color: {
        gradient: [
          { stop: 0.0, color: '#ffffff' },
          { stop: 0.25, color: '#ffdd44' },
          { stop: 0.7, color: '#ff6600' },
          { stop: 1.0, color: '#441100' },
        ],
      },
      alpha: { start: 1, end: 0, easing: 'easeOutCubic' },
      blendMode: 'lighter',
    },
  },

  {
    name: 'ranged-hit',
    version: 1,
    duration: 0.25,
    loop: false,
    tags: ['combat', 'impact', 'ranged'],
    emitter: {
      burstMode: true,
      burstCount: 12,
      spawnShape: 'point',
      angle: { min: 160, max: 200 },
      speed: { min: 40, max: 100 },
      gravity: { x: 0, y: 20 },
    },
    particle: {
      lifetime: { min: 0.1, max: 0.35 },
      shape: 'circle',
      size: { start: { min: 1, max: 3 }, end: { min: 0, max: 0.5 }, easing: 'easeOutQuad' },
      color: {
        gradient: [
          { stop: 0.0, color: '#ffffff' },
          { stop: 0.3, color: '#aaddff' },
          { stop: 1.0, color: '#3366aa' },
        ],
      },
      alpha: { start: 1, end: 0, easing: 'easeOutCubic' },
      blendMode: 'lighter',
    },
  },

  {
    name: 'critical-hit',
    version: 1,
    duration: 0.4,
    loop: false,
    tags: ['combat', 'impact', 'critical'],
    emitter: {
      burstMode: true,
      burstCount: 30,
      spawnShape: 'point',
      angle: { min: 0, max: 360 },
      speed: { min: 80, max: 220 },
      gravity: { x: 0, y: 30 },
      friction: 0.01,
    },
    particle: {
      lifetime: { min: 0.25, max: 0.6 },
      shape: 'star',
      size: { start: { min: 3, max: 8 }, end: { min: 0, max: 1 }, easing: 'easeOutQuad' },
      color: {
        gradient: [
          { stop: 0.0, color: '#ffffff' },
          { stop: 0.2, color: '#ffee55' },
          { stop: 0.6, color: '#ffaa00' },
          { stop: 1.0, color: '#663300' },
        ],
      },
      alpha: { start: 1, end: 0, easing: 'easeOutCubic' },
      blendMode: 'lighter',
    },
  },

  {
    name: 'death-burst',
    version: 1,
    duration: 0.5,
    loop: false,
    tags: ['combat', 'death'],
    emitter: {
      burstMode: true,
      burstCount: 35,
      spawnShape: 'circle',
      spawnRadius: 5,
      angle: { min: 0, max: 360 },
      speed: { min: 30, max: 120 },
      gravity: { x: 0, y: 60 },
      friction: 0.03,
    },
    particle: {
      lifetime: { min: 0.4, max: 1.0 },
      shape: 'circle',
      size: { start: { min: 3, max: 7 }, end: { min: 1, max: 3 }, easing: 'easeOutCubic' },
      color: {
        gradient: [
          { stop: 0.0, color: '#ff3333' },
          { stop: 0.4, color: '#aa1111' },
          { stop: 0.7, color: '#552222' },
          { stop: 1.0, color: '#110000' },
        ],
      },
      alpha: { start: 0.9, end: 0, easing: 'easeOutCubic' },
      blendMode: 'lighter',
    },
  },

  {
    name: 'blood-splatter',
    version: 1,
    duration: 0.2,
    loop: false,
    tags: ['combat', 'gore'],
    emitter: {
      burstMode: true,
      burstCount: 10,
      spawnShape: 'point',
      angle: { min: 200, max: 340 },
      speed: { min: 30, max: 90 },
      gravity: { x: 0, y: 180 },
    },
    particle: {
      lifetime: { min: 0.3, max: 0.7 },
      shape: 'circle',
      size: { start: { min: 2, max: 4 }, end: { min: 1, max: 2 }, easing: 'linear' },
      color: {
        gradient: [
          { stop: 0.0, color: '#cc2222' },
          { stop: 0.5, color: '#882222' },
          { stop: 1.0, color: '#331111' },
        ],
      },
      alpha: { start: 0.9, end: 0.2, easing: 'easeOutCubic' },
      blendMode: 'source-over',
    },
  },

  {
    name: 'block',
    version: 1,
    duration: 0.2,
    loop: false,
    tags: ['combat', 'defense'],
    emitter: {
      burstMode: true,
      burstCount: 8,
      spawnShape: 'ring',
      spawnRadius: 8,
      angle: { min: 0, max: 360 },
      speed: { min: 20, max: 50 },
    },
    particle: {
      lifetime: { min: 0.15, max: 0.3 },
      shape: 'square',
      size: { start: { min: 3, max: 5 }, end: { min: 1, max: 2 }, easing: 'easeOutQuad' },
      color: {
        gradient: [
          { stop: 0.0, color: '#aaccff' },
          { stop: 0.5, color: '#6688bb' },
          { stop: 1.0, color: '#334466' },
        ],
      },
      alpha: { start: 0.8, end: 0, easing: 'easeOutCubic' },
      rotation: { speed: { min: -4, max: 4 } },
      blendMode: 'lighter',
    },
  },

  // ══════════════════════════════════════════════
  // MAGIC / SKILLS
  // ══════════════════════════════════════════════
  {
    name: 'heal-pulse',
    version: 1,
    duration: 0.8,
    loop: false,
    tags: ['magic', 'healing'],
    emitter: {
      burstMode: false,
      spawnRate: 40,
      spawnShape: 'circle',
      spawnRadius: 12,
      angle: { min: 250, max: 290 },
      speed: { min: 20, max: 60 },
      gravity: { x: 0, y: -30 },
    },
    particle: {
      lifetime: { min: 0.5, max: 1.0 },
      shape: 'circle',
      size: { start: { min: 2, max: 4 }, end: { min: 0, max: 1 }, easing: 'easeOutQuad' },
      color: {
        gradient: [
          { stop: 0.0, color: '#ffffff' },
          { stop: 0.3, color: '#66ff88' },
          { stop: 0.7, color: '#22cc55' },
          { stop: 1.0, color: '#115522' },
        ],
      },
      alpha: { start: 0.9, end: 0, easing: 'easeOutCubic' },
      blendMode: 'lighter',
    },
  },

  {
    name: 'fire-blast',
    version: 1,
    duration: 0.5,
    loop: false,
    tags: ['magic', 'fire', 'offensive'],
    emitter: {
      burstMode: true,
      burstCount: 40,
      spawnShape: 'circle',
      spawnRadius: 4,
      angle: { min: 0, max: 360 },
      speed: { min: 50, max: 150 },
      gravity: { x: 0, y: -20 },
      friction: 0.04,
    },
    particle: {
      lifetime: { min: 0.2, max: 0.7 },
      shape: 'circle',
      size: { start: { min: 3, max: 8 }, end: { min: 0, max: 2 }, easing: 'easeOutCubic' },
      color: {
        gradient: [
          { stop: 0.0, color: '#ffffff' },
          { stop: 0.15, color: '#ffff44' },
          { stop: 0.4, color: '#ff6600' },
          { stop: 0.7, color: '#cc2200' },
          { stop: 1.0, color: '#221100' },
        ],
      },
      alpha: { start: 1, end: 0, easing: 'easeOutCubic' },
      blendMode: 'lighter',
    },
  },

  {
    name: 'ice-shard',
    version: 1,
    duration: 0.4,
    loop: false,
    tags: ['magic', 'ice', 'offensive'],
    emitter: {
      burstMode: true,
      burstCount: 20,
      spawnShape: 'point',
      angle: { min: 0, max: 360 },
      speed: { min: 60, max: 140 },
      gravity: { x: 0, y: 40 },
      friction: 0.02,
    },
    particle: {
      lifetime: { min: 0.2, max: 0.5 },
      shape: 'triangle',
      size: { start: { min: 3, max: 6 }, end: { min: 0, max: 1 }, easing: 'easeOutQuad' },
      color: {
        gradient: [
          { stop: 0.0, color: '#ffffff' },
          { stop: 0.3, color: '#cceeff' },
          { stop: 0.7, color: '#4488cc' },
          { stop: 1.0, color: '#112244' },
        ],
      },
      alpha: { start: 1, end: 0, easing: 'easeOutCubic' },
      rotation: { speed: { min: -6, max: 6 } },
      blendMode: 'lighter',
    },
  },

  {
    name: 'poison-cloud',
    version: 1,
    duration: 1.5,
    loop: false,
    tags: ['magic', 'poison', 'dot'],
    emitter: {
      burstMode: false,
      spawnRate: 25,
      spawnShape: 'circle',
      spawnRadius: 15,
      angle: { min: 240, max: 300 },
      speed: { min: 8, max: 25 },
      gravity: { x: 0, y: -10 },
    },
    particle: {
      lifetime: { min: 0.6, max: 1.4 },
      shape: 'circle',
      size: { start: { min: 4, max: 10 }, end: { min: 6, max: 14 }, easing: 'easeOutCubic' },
      color: {
        gradient: [
          { stop: 0.0, color: '#88ff44' },
          { stop: 0.4, color: '#44aa22' },
          { stop: 1.0, color: '#114400' },
        ],
      },
      alpha: { start: 0.4, end: 0, easing: 'easeOutCubic' },
      blendMode: 'lighter',
    },
  },

  {
    name: 'dark-bolt',
    version: 1,
    duration: 0.3,
    loop: false,
    tags: ['magic', 'dark', 'offensive'],
    emitter: {
      burstMode: true,
      burstCount: 22,
      spawnShape: 'point',
      angle: { min: 170, max: 190 },
      speed: { min: 80, max: 180 },
      gravity: { x: 0, y: 0 },
      friction: 0.03,
    },
    particle: {
      lifetime: { min: 0.15, max: 0.4 },
      shape: 'circle',
      size: { start: { min: 2, max: 5 }, end: { min: 0, max: 1 }, easing: 'easeOutQuad' },
      color: {
        gradient: [
          { stop: 0.0, color: '#cc66ff' },
          { stop: 0.3, color: '#8833cc' },
          { stop: 0.7, color: '#441166' },
          { stop: 1.0, color: '#110022' },
        ],
      },
      alpha: { start: 1, end: 0, easing: 'easeOutCubic' },
      trail: { length: 6 },
      blendMode: 'lighter',
    },
  },

  {
    name: 'holy-smite',
    version: 1,
    duration: 0.5,
    loop: false,
    tags: ['magic', 'holy', 'offensive'],
    emitter: {
      burstMode: true,
      burstCount: 25,
      spawnShape: 'line',
      spawnWidth: 20,
      angle: { min: 260, max: 280 },
      speed: { min: 80, max: 200 },
      gravity: { x: 0, y: 0 },
    },
    particle: {
      lifetime: { min: 0.15, max: 0.4 },
      shape: 'line',
      size: { start: { min: 6, max: 14 }, end: { min: 1, max: 3 }, easing: 'easeOutQuad' },
      color: {
        gradient: [
          { stop: 0.0, color: '#ffffff' },
          { stop: 0.3, color: '#ffeeaa' },
          { stop: 0.7, color: '#ffcc44' },
          { stop: 1.0, color: '#664400' },
        ],
      },
      alpha: { start: 1, end: 0, easing: 'easeOutCubic' },
      blendMode: 'lighter',
    },
  },

  {
    name: 'buff-aura',
    version: 1,
    duration: 2.0,
    loop: true,
    tags: ['magic', 'buff', 'aura'],
    emitter: {
      burstMode: false,
      spawnRate: 12,
      spawnShape: 'ring',
      spawnRadius: 16,
      angle: { min: 250, max: 290 },
      speed: { min: 10, max: 30 },
      gravity: { x: 0, y: -15 },
    },
    particle: {
      lifetime: { min: 0.5, max: 1.0 },
      shape: 'circle',
      size: { start: { min: 1, max: 3 }, end: { min: 0, max: 0.5 }, easing: 'easeOutQuad' },
      color: {
        gradient: [
          { stop: 0.0, color: '#ffdd88' },
          { stop: 0.5, color: '#ffaa33' },
          { stop: 1.0, color: '#663300' },
        ],
      },
      alpha: { start: 0.7, end: 0, easing: 'easeOutCubic' },
      blendMode: 'lighter',
    },
  },

  // ══════════════════════════════════════════════
  // ENVIRONMENT
  // ══════════════════════════════════════════════
  {
    name: 'torch-flame',
    version: 1,
    duration: 3.0,
    loop: true,
    tags: ['environment', 'fire', 'ambient'],
    emitter: {
      burstMode: false,
      spawnRate: 20,
      spawnShape: 'line',
      spawnWidth: 6,
      angle: { min: 255, max: 285 },
      speed: { min: 15, max: 40 },
      gravity: { x: 0, y: -25 },
    },
    particle: {
      lifetime: { min: 0.3, max: 0.7 },
      shape: 'circle',
      size: { start: { min: 3, max: 5 }, end: { min: 0, max: 1 }, easing: 'easeOutQuad' },
      color: {
        gradient: [
          { stop: 0.0, color: '#ffffff' },
          { stop: 0.2, color: '#ffcc33' },
          { stop: 0.5, color: '#ff6600' },
          { stop: 0.8, color: '#cc2200' },
          { stop: 1.0, color: '#220000' },
        ],
      },
      alpha: { start: 0.8, end: 0, easing: 'easeOutCubic' },
      blendMode: 'lighter',
    },
  },

  {
    name: 'dust-motes',
    version: 1,
    duration: 5.0,
    loop: true,
    tags: ['environment', 'ambient'],
    emitter: {
      burstMode: false,
      spawnRate: 4,
      spawnShape: 'rect',
      spawnWidth: 200,
      spawnHeight: 200,
      angle: { min: 240, max: 300 },
      speed: { min: 3, max: 10 },
      gravity: { x: 0, y: -2 },
      wind: { x: 5 },
    },
    particle: {
      lifetime: { min: 2.0, max: 4.0 },
      shape: 'circle',
      size: { start: { min: 1, max: 2 }, end: { min: 0.5, max: 1 }, easing: 'linear' },
      color: {
        gradient: [
          { stop: 0.0, color: '#aaaaaa' },
          { stop: 1.0, color: '#666666' },
        ],
      },
      alpha: { start: 0.3, end: 0, easing: 'easeInOutQuad' },
      blendMode: 'lighter',
    },
  },

  // ══════════════════════════════════════════════
  // UI / FEEDBACK
  // ══════════════════════════════════════════════
  {
    name: 'level-up',
    version: 1,
    duration: 0.8,
    loop: false,
    tags: ['ui', 'feedback', 'celebration'],
    emitter: {
      burstMode: true,
      burstCount: 40,
      spawnShape: 'ring',
      spawnRadius: 5,
      angle: { min: 230, max: 310 },
      speed: { min: 60, max: 160 },
      gravity: { x: 0, y: 30 },
      friction: 0.02,
    },
    particle: {
      lifetime: { min: 0.4, max: 1.0 },
      shape: 'star',
      size: { start: { min: 3, max: 7 }, end: { min: 0, max: 1 }, easing: 'easeOutQuad' },
      color: {
        gradient: [
          { stop: 0.0, color: '#ffffff' },
          { stop: 0.2, color: '#ffee66' },
          { stop: 0.6, color: '#ffcc00' },
          { stop: 1.0, color: '#664400' },
        ],
      },
      alpha: { start: 1, end: 0, easing: 'easeOutCubic' },
      rotation: { speed: { min: -3, max: 3 } },
      blendMode: 'lighter',
    },
  },

  {
    name: 'loot-sparkle',
    version: 1,
    duration: 2.0,
    loop: true,
    tags: ['ui', 'loot', 'ambient'],
    emitter: {
      burstMode: false,
      spawnRate: 6,
      spawnShape: 'rect',
      spawnWidth: 20,
      spawnHeight: 20,
      angle: { min: 250, max: 290 },
      speed: { min: 5, max: 15 },
      gravity: { x: 0, y: -8 },
    },
    particle: {
      lifetime: { min: 0.3, max: 0.8 },
      shape: 'star',
      size: { start: { min: 1, max: 3 }, end: { min: 0, max: 0.5 }, easing: 'easeOutQuad' },
      color: {
        gradient: [
          { stop: 0.0, color: '#ffffff' },
          { stop: 0.5, color: '#ffee88' },
          { stop: 1.0, color: '#997700' },
        ],
      },
      alpha: { start: 0.8, end: 0, easing: 'easeOutCubic' },
      rotation: { speed: { min: -2, max: 2 } },
      blendMode: 'lighter',
    },
  },

  {
    name: 'portal-swirl',
    version: 1,
    duration: 3.0,
    loop: true,
    tags: ['ui', 'portal', 'ambient'],
    emitter: {
      burstMode: false,
      spawnRate: 18,
      spawnShape: 'ring',
      spawnRadius: 20,
      angle: { min: 0, max: 360 },
      speed: { min: 5, max: 15 },
      gravity: { x: 0, y: 0 },
    },
    particle: {
      lifetime: { min: 0.5, max: 1.2 },
      shape: 'circle',
      size: { start: { min: 2, max: 4 }, end: { min: 0, max: 1 }, easing: 'easeOutQuad' },
      color: {
        gradient: [
          { stop: 0.0, color: '#aaddff' },
          { stop: 0.4, color: '#6644cc' },
          { stop: 0.8, color: '#8833ff' },
          { stop: 1.0, color: '#220066' },
        ],
      },
      alpha: { start: 0.8, end: 0, easing: 'easeOutCubic' },
      blendMode: 'lighter',
    },
  },

  // ══════════════════════════════════════════════
  // PORTAL — Compound layers (stack together)
  // ══════════════════════════════════════════════

  // Layer 1: Ground ring — large ring of slow purple/blue particles hugging the ground
  {
    name: 'portal-ground-ring',
    version: 1,
    duration: 4.0,
    loop: true,
    tags: ['portal', 'compound', 'ring'],
    emitter: {
      burstMode: false,
      spawnRate: 22,
      spawnShape: 'ring',
      spawnRadius: 18,
      angle: { min: 0, max: 360 },
      speed: { min: 3, max: 10 },
      gravity: { x: 0, y: 0 },
      friction: 0.01,
    },
    particle: {
      lifetime: { min: 0.8, max: 1.6 },
      shape: 'circle',
      size: { start: { min: 3, max: 6 }, end: { min: 0, max: 1 }, easing: 'easeOutQuad' },
      color: {
        gradient: [
          { stop: 0.0, color: '#aaddff' },
          { stop: 0.3, color: '#7766dd' },
          { stop: 0.6, color: '#8833ff' },
          { stop: 1.0, color: '#2200aa' },
        ],
      },
      alpha: { start: 0.7, end: 0, easing: 'easeOutCubic' },
      blendMode: 'lighter',
      trail: { length: 3 },
    },
  },

  // Layer 2: Core glow — bright tight center pulse
  {
    name: 'portal-core-glow',
    version: 1,
    duration: 2.0,
    loop: true,
    tags: ['portal', 'compound', 'glow'],
    emitter: {
      burstMode: false,
      spawnRate: 12,
      spawnShape: 'circle',
      spawnRadius: 5,
      angle: { min: 0, max: 360 },
      speed: { min: 2, max: 8 },
      gravity: { x: 0, y: 0 },
    },
    particle: {
      lifetime: { min: 0.3, max: 0.7 },
      shape: 'circle',
      size: { start: { min: 4, max: 8 }, end: { min: 1, max: 3 }, easing: 'easeOutCubic' },
      color: {
        gradient: [
          { stop: 0.0, color: '#ffffff' },
          { stop: 0.3, color: '#ccddff' },
          { stop: 0.7, color: '#8899ff' },
          { stop: 1.0, color: '#4433aa' },
        ],
      },
      alpha: { start: 0.9, end: 0, easing: 'easeOutQuad' },
      blendMode: 'lighter',
    },
  },

  // Layer 3: Rising sparks — upward-drifting particles from center
  {
    name: 'portal-rising-sparks',
    version: 1,
    duration: 3.0,
    loop: true,
    tags: ['portal', 'compound', 'sparks'],
    emitter: {
      burstMode: false,
      spawnRate: 8,
      spawnShape: 'circle',
      spawnRadius: 10,
      angle: { min: 250, max: 290 },
      speed: { min: 25, max: 55 },
      gravity: { x: 0, y: -10 },
      friction: 0.01,
    },
    particle: {
      lifetime: { min: 0.6, max: 1.4 },
      shape: 'star',
      size: { start: { min: 2, max: 4 }, end: { min: 0, max: 1 }, easing: 'easeOutQuad' },
      color: {
        gradient: [
          { stop: 0.0, color: '#ffffff' },
          { stop: 0.2, color: '#ddaaff' },
          { stop: 0.6, color: '#aa66ff' },
          { stop: 1.0, color: '#440088' },
        ],
      },
      alpha: { start: 1, end: 0, easing: 'easeOutCubic' },
      rotation: { start: { min: 0, max: 6.28 }, speed: { min: -3, max: 3 } },
      trail: { length: 4 },
      blendMode: 'lighter',
    },
  },

  // Layer 4: Channel swirl — cast-time effect on the caster (tighter, faster)
  {
    name: 'portal-channel-swirl',
    version: 1,
    duration: 3.0,
    loop: true,
    tags: ['portal', 'compound', 'cast'],
    emitter: {
      burstMode: false,
      spawnRate: 30,
      spawnShape: 'ring',
      spawnRadius: 14,
      angle: { min: 0, max: 360 },
      speed: { min: 15, max: 35 },
      gravity: { x: 0, y: -5 },
      friction: 0.02,
    },
    particle: {
      lifetime: { min: 0.3, max: 0.8 },
      shape: 'circle',
      size: { start: { min: 2, max: 5 }, end: { min: 0, max: 1 }, easing: 'easeOutElastic' },
      color: {
        gradient: [
          { stop: 0.0, color: '#ffffff' },
          { stop: 0.15, color: '#aaccff' },
          { stop: 0.5, color: '#7744dd' },
          { stop: 0.8, color: '#5522bb' },
          { stop: 1.0, color: '#110033' },
        ],
      },
      alpha: { start: 1, end: 0, easing: 'easeOutCubic' },
      trail: { length: 5 },
      blendMode: 'lighter',
    },
  },

  // Portal open flash — one-shot burst when portal materializes
  {
    name: 'portal-open-flash',
    version: 1,
    duration: 0.5,
    loop: false,
    tags: ['portal', 'compound', 'flash'],
    emitter: {
      burstMode: true,
      burstCount: 35,
      spawnShape: 'point',
      angle: { min: 0, max: 360 },
      speed: { min: 40, max: 120 },
      gravity: { x: 0, y: 0 },
      friction: 0.03,
    },
    particle: {
      lifetime: { min: 0.2, max: 0.6 },
      shape: 'circle',
      size: { start: { min: 3, max: 8 }, end: { min: 0, max: 2 }, easing: 'easeOutCubic' },
      color: {
        gradient: [
          { stop: 0.0, color: '#ffffff' },
          { stop: 0.2, color: '#ccddff' },
          { stop: 0.5, color: '#8855ff' },
          { stop: 1.0, color: '#2200aa' },
        ],
      },
      alpha: { start: 1, end: 0, easing: 'easeOutQuad' },
      blendMode: 'lighter',
    },
  },
];

export default PRESETS;
