// ─────────────────────────────────────────────────────────
// themes.js — Built-in dungeon theme definitions
//
// Each theme defines:
//   - palette: color scheme for all tile elements
//   - wall: wall drawing style + parameters
//   - floor: floor drawing style + parameters
//   - corridor: corridor-specific overrides
//   - fog: fog of war tinting
//   - ambient: vignette, glow, atmospheric effects
//   - details: decoration density & types
//
// Dark Souls / Bloodborne inspired — oppressive, decayed,
// with distinctive color identity per biome.
// ─────────────────────────────────────────────────────────

export const THEMES = {

  // ═══════════════════════════════════════════════════════
  // THEME 1: Bleeding Catacombs
  // Deep underground crypts with red mortar bleeding
  // through cracked stone. Dried blood, scattered bones.
  // Inspiration: Catacombs of Carthus, Chalice Dungeons
  // ═══════════════════════════════════════════════════════
  bleeding_catacombs: {
    id: 'bleeding_catacombs',
    name: 'Bleeding Catacombs',
    description: 'Ancient crypts where red mortar weeps through cracked stone walls. The air tastes of iron.',
    palette: {
      primary:    '#1a1015',   // Deepest background (near-black with red tint)
      secondary:  '#2a1520',   // Stone block faces
      accent:     '#8a2030',   // Blood red — mortar bleed, stains
      mortar:     '#4a1525',   // Mortar between stones
      highlight:  '#cc3040',   // Bright accent — fresh blood, glow
      floor:      '#3e2d3d',   // Floor base — notably lighter purple-stone for contrast
      floorAlt:   '#413040',   // Floor variation — very close to floor, subtle shift
      grout:      '#120a10',   // Floor grout lines
    },
    wall: {
      style: 'cracked_stone',
      brickRows: 3,
      brickCols: 2,
      mortarWidth: 2,
      crackDensity: 0.08,      // Minimal cracks — clean stone reads
      bleedChance: 0.05,        // Very subtle mortar bleed
      edgeVignette: true,
    },
    floor: {
      style: 'flagstone',
      slabGrid: 2,              // 2×2 flagstone pattern
      groutWidth: 1,
      stainChance: 0.0,         // No random stain circles
      stainColor: 'rgba(120, 20, 20, 0.18)',
      debrisChance: 0.0,        // No debris
      debrisColor: '#4a4040',
      textureDots: 1,           // Minimal surface texture
    },
    corridor: {
      style: 'worn_stone',
      streakChance: 0.0,        // No random streak lines
    },
    fog: {
      exploredTint: 'rgba(30, 10, 15, 0.6)',
      unexploredColor: '#0a0508',
    },
    ambient: {
      vignetteStrength: 0.15,
      vignetteColor: 'rgba(80, 10, 20, 0.10)',
    },
    details: {
      wallOverlayChance: 0.0,
      overlayTypes: [],
    },
  },

  // ═══════════════════════════════════════════════════════
  // THEME 2: Ashen Undercroft
  // A burned-out ruin still smoldering. Charred brick,
  // ember glow in the cracks, ash-dusted floors.
  // Inspiration: Smouldering Lake, Old Iron Keep
  // ═══════════════════════════════════════════════════════
  ashen_undercroft: {
    id: 'ashen_undercroft',
    name: 'Ashen Undercroft',
    description: 'Scorched ruins still smoldering beneath the earth. Embers glow in the cracks between blackened bricks.',
    palette: {
      primary:    '#1a1612',   // Charcoal black-brown
      secondary:  '#2a2218',   // Scorched brick face
      accent:     '#cc6a20',   // Ember orange
      mortar:     '#3a2a18',   // Ash-brown mortar
      highlight:  '#ff8830',   // Bright ember glow
      floor:      '#443a2c',   // Ash-dusted floor — notably lighter warm brown
      floorAlt:   '#473d2f',   // Floor variation — very close to floor, subtle shift
      grout:      '#121010',   // Dark grout
    },
    wall: {
      style: 'scorched_brick',
      brickRows: 3,
      brickCols: 2,
      mortarWidth: 2,
      crackDensity: 0.05,       // Minimal cracks
      emberChance: 0.06,        // Rare ember glow in mortar
      scorchChance: 0.10,       // Subtle charring
      edgeVignette: true,
    },
    floor: {
      style: 'ash_covered',
      slabGrid: 2,
      groutWidth: 1,
      ashDensity: 0.08,         // Light ash scatter — floor reads clean
      emberChance: 0.0,         // No random ember circles
      stainChance: 0.0,         // No random stain circles
      stainColor: 'rgba(60, 40, 20, 0.15)',
      debrisChance: 0.0,        // No debris
      debrisColor: '#3a3025',
    },
    corridor: {
      style: 'ash_trail',
      ashDensity: 0.15,         // Light ash trail
    },
    fog: {
      exploredTint: 'rgba(25, 18, 10, 0.6)',
      unexploredColor: '#0a0805',
    },
    ambient: {
      vignetteStrength: 0.14,
      vignetteColor: 'rgba(80, 50, 10, 0.08)',
    },
    details: {
      wallOverlayChance: 0.0,
      overlayTypes: [],
    },
  },

  // ═══════════════════════════════════════════════════════
  // THEME 3: Drowned Sanctum
  // A flooded underground temple. Slick mossy stone,
  // bioluminescent veins, water stains, eerie cyan glow.
  // Inspiration: Shrine of Amana, Fishing Hamlet
  // ═══════════════════════════════════════════════════════
  drowned_sanctum: {
    id: 'drowned_sanctum',
    name: 'Drowned Sanctum',
    description: 'A sunken temple claimed by dark waters. Bioluminescent veins pulse in the slick stone walls.',
    palette: {
      primary:    '#0a1520',   // Deep ocean dark
      secondary:  '#152535',   // Wet stone
      accent:     '#2a8a7a',   // Bioluminescent teal
      mortar:     '#0e1a25',   // Dark wet mortar
      highlight:  '#40ccbb',   // Bright bioluminescence
      floor:      '#24394f',   // Water-logged floor — notably lighter blue-green
      floorAlt:   '#273c52',   // Floor variation — very close to floor, subtle shift
      grout:      '#080e14',   // Deep grout
    },
    wall: {
      style: 'mossy_stone',
      brickRows: 2,            // Larger stone blocks
      brickCols: 2,
      mortarWidth: 2,
      crackDensity: 0.04,       // Minimal cracks
      mossChance: 0.0,          // No random moss circles
      waterStainChance: 0.0,    // No random drip lines
      veinChance: 0.0,          // No random vein lines through tiles
      edgeVignette: true,
    },
    floor: {
      style: 'flooded',
      slabGrid: 2,
      groutWidth: 1,
      waterDepth: 0.08,         // Faint water tint — not overwhelming
      rippleChance: 0.0,        // No random ripple circles
      stainChance: 0.0,         // No random stain circles
      stainColor: 'rgba(20, 80, 60, 0.12)',
      debrisChance: 0.0,        // No debris
      debrisColor: '#1a3a30',
    },
    corridor: {
      style: 'shallow_water',
      waterDepth: 0.15,         // Subtle water overlay
    },
    fog: {
      exploredTint: 'rgba(8, 20, 30, 0.6)',
      unexploredColor: '#040a10',
    },
    ambient: {
      vignetteStrength: 0.12,
      vignetteColor: 'rgba(10, 60, 60, 0.07)',
    },
    details: {
      wallOverlayChance: 0.0,
      overlayTypes: [],
    },
  },

  // ═══════════════════════════════════════════════════════
  // THEME 4: Hollowed Cathedral
  // Ruined grandeur. Crumbling carved stonework, faded
  // iconography, cracked marble, root intrusions.
  // Inspiration: Cathedral of the Deep, Anor Londo ruins
  // ═══════════════════════════════════════════════════════
  hollowed_cathedral: {
    id: 'hollowed_cathedral',
    name: 'Hollowed Cathedral',
    description: 'A once-grand cathedral, its carved stonework crumbling. Faded icons stare down from ruined walls.',
    palette: {
      primary:    '#1a1525',   // Deep purple-grey
      secondary:  '#2a2035',   // Carved stone face
      accent:     '#6a4a7a',   // Faded purple/gold
      mortar:     '#1e1528',   // Purple-tinted mortar
      highlight:  '#aa7a55',   // Gold/amber highlight
      floor:      '#3d3555',   // Marble floor — notably lighter purple-grey
      floorAlt:   '#403858',   // Floor variation — very close to floor, subtle shift
      grout:      '#100e18',   // Dark grout
    },
    wall: {
      style: 'carved_stone',
      brickRows: 2,            // Grand large blocks
      brickCols: 2,
      mortarWidth: 3,          // Wider mortar = grander blocks
      crackDensity: 0.05,      // Minimal cracks
      iconChance: 0.0,         // No random icon shapes
      crumbleChance: 0.05,     // Very subtle crumble
      goldTrimChance: 0.04,    // Very subtle gold trim
      edgeVignette: true,
    },
    floor: {
      style: 'cracked_marble',
      slabGrid: 3,             // Larger marble tiles
      groutWidth: 1,
      crackChance: 0.0,        // No random crack lines across tiles
      veinChance: 0.0,         // No random vein lines through slabs
      rootChance: 0.0,         // No random root curves
      stainChance: 0.0,        // No random stain circles
      stainColor: 'rgba(60, 40, 70, 0.12)',
      debrisChance: 0.0,       // No debris
      debrisColor: '#3a3045',
    },
    corridor: {
      style: 'worn_carpet',
      carpetColor: 'rgba(80, 40, 50, 0.12)', // Faded carpet hint
    },
    fog: {
      exploredTint: 'rgba(20, 15, 30, 0.6)',
      unexploredColor: '#08050e',
    },
    ambient: {
      vignetteStrength: 0.15,
      vignetteColor: 'rgba(50, 30, 60, 0.08)',
    },
    details: {
      wallOverlayChance: 0.0,
      overlayTypes: [],
    },
  },

  // ═══════════════════════════════════════════════════════
  // THEME 5: Iron Depths
  // An industrial nightmare. Riveted metal plates, rust,
  // grated flooring over bottomless voids, leaking pipes.
  // Inspiration: Sen's Fortress, Ailing Loran
  // ═══════════════════════════════════════════════════════
  iron_depths: {
    id: 'iron_depths',
    name: 'Iron Depths',
    description: 'Riveted iron plates and rusted grating over bottomless voids. The machinery groans in the dark.',
    palette: {
      primary:    '#151518',   // Deep steel black
      secondary:  '#2a2a30',   // Metal panel face
      accent:     '#7a5a3a',   // Rust orange-brown
      mortar:     '#1a1a20',   // Panel seam
      highlight:  '#aa7a4a',   // Bright rust / spark
      floor:      '#3e3e48',   // Metal floor — notably lighter steel tone
      floorAlt:   '#41414b',   // Floor variation — very close to floor, subtle shift
      grout:      '#0a0a10',   // Deep gap between grates
    },
    wall: {
      style: 'iron_plate',
      brickRows: 2,            // Large metal panels
      brickCols: 2,
      mortarWidth: 1,          // Thin seam lines
      crackDensity: 0.03,      // Minimal wear marks
      rivetChance: 0.40,       // Moderate rivets — structural detail
      rustChance: 0.08,        // Subtle rust streaks
      pipeChance: 0.0,         // No random pipe lines
      edgeVignette: true,
    },
    floor: {
      style: 'metal_grate',
      slabGrid: 2,
      groutWidth: 2,           // Wider gaps (void below)
      grateLineSpacing: 10,    // Sparser crosshatch — reads cleaner
      oilChance: 0.0,          // No random oil stain ellipses
      stainChance: 0.0,        // No random stains
      stainColor: 'rgba(90, 60, 30, 0.15)',
      debrisChance: 0.0,       // No debris
      debrisColor: '#3a3530',
    },
    corridor: {
      style: 'walkway',
      railHint: true,          // Edge rail suggestion
    },
    fog: {
      exploredTint: 'rgba(15, 15, 20, 0.6)',
      unexploredColor: '#050508',
    },
    ambient: {
      vignetteStrength: 0.14,
      vignetteColor: 'rgba(40, 40, 50, 0.08)',
    },
    details: {
      wallOverlayChance: 0.0,
      overlayTypes: [],
    },
  },

  // ═══════════════════════════════════════════════════════
  // THEME 6: Forgotten Cellar
  // A plain stone basement, long abandoned. Minimal detail,
  // quiet earth tones. The simplest, cleanest dungeon.
  // Inspiration: Undead Burg basements, simple cellars
  // ═══════════════════════════════════════════════════════
  forgotten_cellar: {
    id: 'forgotten_cellar',
    name: 'Forgotten Cellar',
    description: 'A plain stone cellar beneath a ruined keep. Quiet, bare, and long abandoned — only dust remains.',
    palette: {
      primary:    '#18160f',   // Warm dark brown-black
      secondary:  '#2c2820',   // Worn sandstone
      accent:     '#4a4035',   // Muted brown (barely visible)
      mortar:     '#1e1c15',   // Dark mortar
      highlight:  '#6a6050',   // Dull warm highlight
      floor:      '#443c30',   // Earthy floor — notably lighter warm brown
      floorAlt:   '#473f33',   // Floor variation — very close to floor, subtle shift
      grout:      '#100e0a',   // Dark grout
    },
    wall: {
      style: 'cracked_stone',
      brickRows: 3,
      brickCols: 2,
      mortarWidth: 2,
      crackDensity: 0.03,       // Almost no cracks — clean stone
      bleedChance: 0.0,         // No mortar bleed — just plain joints
      edgeVignette: false,       // No vignette — flatter, cleaner
    },
    floor: {
      style: 'flagstone',
      slabGrid: 2,
      groutWidth: 1,
      stainChance: 0.0,         // No random stain circles
      stainColor: 'rgba(60, 50, 40, 0.12)',
      debrisChance: 0.0,        // No debris
      debrisColor: '#3a3530',
    },
    corridor: {
      style: 'worn_stone',
      streakChance: 0.0,        // No streak marks
    },
    fog: {
      exploredTint: 'rgba(20, 18, 12, 0.55)',
      unexploredColor: '#0a0908',
    },
    ambient: {
      vignetteStrength: 0.08,
      vignetteColor: 'rgba(30, 25, 15, 0.05)',
    },
    details: {
      wallOverlayChance: 0.0,
      overlayTypes: [],
    },
  },

  // ═══════════════════════════════════════════════════════
  // THEME 7: Pale Ossuary
  // Bone-white stone chambers. Austere, sterile, unsettling.
  // Almost no decoration — the emptiness IS the horror.
  // Inspiration: Painted World of Ariamis, ash-white tombs
  // ═══════════════════════════════════════════════════════
  pale_ossuary: {
    id: 'pale_ossuary',
    name: 'Pale Ossuary',
    description: 'Bone-white stone halls, scrubbed clean by centuries. The silence here is heavy and absolute.',
    palette: {
      primary:    '#1c1a1e',   // Cool dark grey
      secondary:  '#35323a',   // Pale grey-violet stone
      accent:     '#504a55',   // Muted lavender-grey accent
      mortar:     '#28262c',   // Cool mortar
      highlight:  '#807580',   // Faint pale highlight
      floor:      '#4d4856',   // Cool floor — notably lighter violet-grey
      floorAlt:   '#504b59',   // Floor variation — very close to floor, subtle shift
      grout:      '#141218',   // Dark cool grout
    },
    wall: {
      style: 'carved_stone',
      brickRows: 2,
      brickCols: 2,
      mortarWidth: 2,
      crackDensity: 0.02,       // Nearly pristine
      iconChance: 0.0,          // No icons
      crumbleChance: 0.01,      // Barely any wear
      goldTrimChance: 0.0,      // No gold — austerity
      edgeVignette: false,
    },
    floor: {
      style: 'cracked_marble',
      slabGrid: 2,              // Larger slabs = less grid noise
      groutWidth: 1,
      crackChance: 0.0,         // No random crack lines
      veinChance: 0.0,          // No random vein lines
      rootChance: 0.0,          // No roots
      stainChance: 0.0,         // No random stains
      stainColor: 'rgba(40, 35, 45, 0.10)',
      debrisChance: 0.0,        // No debris
      debrisColor: '#302830',
    },
    corridor: {
      style: 'worn_carpet',
      carpetColor: 'rgba(60, 55, 65, 0.08)', // Ghost of a carpet
    },
    fog: {
      exploredTint: 'rgba(20, 18, 24, 0.55)',
      unexploredColor: '#08060c',
    },
    ambient: {
      vignetteStrength: 0.06,
      vignetteColor: 'rgba(40, 35, 50, 0.04)',
    },
    details: {
      wallOverlayChance: 0.0,
      overlayTypes: [],
    },
  },

  // ═══════════════════════════════════════════════════════
  // THEME 8: Silent Vault
  // Deep slate-blue stone archive. Clean, cold, vast.
  // Sparse detail, monastic geometry, restrained palette.
  // Inspiration: Duke's Archives, Grand Archives (quiet wing)
  // ═══════════════════════════════════════════════════════
  silent_vault: {
    id: 'silent_vault',
    name: 'Silent Vault',
    description: 'A sealed stone archive deep underground. Cold, orderly, and utterly still.',
    palette: {
      primary:    '#101520',   // Deep slate blue-black
      secondary:  '#1e2535',   // Cool blue-grey stone
      accent:     '#3a4a5a',   // Steel blue accent
      mortar:     '#151a28',   // Dark blue mortar
      highlight:  '#5a6a80',   // Muted silver-blue
      floor:      '#2e3c50',   // Slate floor — notably lighter cool blue
      floorAlt:   '#313f53',   // Floor variation — very close to floor, subtle shift
      grout:      '#0a0e15',   // Deep dark grout
    },
    wall: {
      style: 'mossy_stone',
      brickRows: 2,
      brickCols: 2,
      mortarWidth: 2,
      crackDensity: 0.02,       // Almost no cracks
      mossChance: 0.0,          // No moss — dry sealed vault
      waterStainChance: 0.0,    // No random drip lines
      veinChance: 0.0,          // No bioluminescence
      edgeVignette: false,
    },
    floor: {
      style: 'flooded',
      slabGrid: 2,
      groutWidth: 1,
      waterDepth: 0.04,         // Barely a sheen — not actually flooded
      rippleChance: 0.0,        // No ripple circles — still surface
      stainChance: 0.0,         // No random stains
      stainColor: 'rgba(30, 40, 55, 0.10)',
      debrisChance: 0.0,        // No debris
      debrisColor: '#1a2530',
    },
    corridor: {
      style: 'shallow_water',
      waterDepth: 0.04,         // Faintest moisture sheen
    },
    fog: {
      exploredTint: 'rgba(10, 15, 25, 0.55)',
      unexploredColor: '#060810',
    },
    ambient: {
      vignetteStrength: 0.06,
      vignetteColor: 'rgba(20, 30, 50, 0.04)',
    },
    details: {
      wallOverlayChance: 0.0,
      overlayTypes: [],
    },
  },
};

/**
 * Get a theme by ID. Falls back to bleeding_catacombs.
 */
export function getTheme(themeId) {
  return THEMES[themeId] || THEMES.bleeding_catacombs;
}

/**
 * Get all theme IDs.
 */
export function getThemeIds() {
  return Object.keys(THEMES);
}

/**
 * Get a minimal summary of all themes (for selector UIs).
 */
export function getThemeSummaries() {
  return Object.values(THEMES).map(t => ({
    id: t.id,
    name: t.name,
    description: t.description,
    palette: t.palette,
  }));
}
