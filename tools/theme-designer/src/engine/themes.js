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
      furniture:  '#4a3520',   // Dark rotting wood — coffins, shelves, barrels
      metal:      '#6a5540',   // Tarnished bronze — chains, brackets, brazier bowls
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
    edge: {
      style: 'crumble',
      intensity: 0.6,
      width: 4,
    },
    propAffinities: {
      pillar: 0.6, rubble: 0.4, brazier: 0.8, coffin: 1.0,
      bookshelf: 0.3, altar: 0.7, puddle: 0.0, barrel: 0.2,
      chains: 0.8, banner: 0.3,      statue: 0.5, throne: 0.2, cage: 0.6, weapon_rack: 0.0,
      torch_sconce: 0.7, skull_pile: 0.9, mushroom_cluster: 0.0, web: 0.5,
      fountain: 0.2, candelabra: 0.3, ritual_circle: 0.3, iron_maiden: 0.4, tombstone: 0.8,
      lectern: 0.3, desk: 0.2, crate: 0.4, bone_pile: 0.8, hanging_lantern: 0.4,
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
      furniture:  '#3a2a1a',   // Charred blackened wood
      metal:      '#5a5048',   // Heat-blackened iron
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
    edge: {
      style: 'scorch',
      intensity: 0.7,
      width: 4,
    },
    propAffinities: {
      pillar: 0.3, rubble: 0.6, brazier: 0.8, coffin: 0.0,
      bookshelf: 0.2, altar: 0.4, puddle: 0.0, barrel: 0.6,
      chains: 0.2, banner: 0.2,      statue: 0.2, throne: 0.1, cage: 0.3, weapon_rack: 0.0,
      torch_sconce: 0.9, skull_pile: 0.3, mushroom_cluster: 0.0, web: 0.3,
      fountain: 0.1, candelabra: 0.2, ritual_circle: 0.1, iron_maiden: 0.2, tombstone: 0.1,
      lectern: 0.2, desk: 0.2, crate: 0.6, bone_pile: 0.5, hanging_lantern: 0.3,
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
      furniture:  '#3a4a3a',   // Waterlogged grey-green wood
      metal:      '#4a5a55',   // Corroded verdigris patina
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
    edge: {
      style: 'moss_creep',
      intensity: 0.5,
      width: 3,
    },
    propAffinities: {
      pillar: 0.7, rubble: 0.3, brazier: 0.4, coffin: 0.0,
      bookshelf: 0.1, altar: 0.5, puddle: 1.0, barrel: 0.1,
      chains: 0.6, banner: 0.1,      statue: 0.6, throne: 0.1, cage: 0.2, weapon_rack: 0.0,
      torch_sconce: 0.3, skull_pile: 0.1, mushroom_cluster: 0.9, web: 0.0,
      fountain: 0.8, candelabra: 0.3, ritual_circle: 0.2, iron_maiden: 0.0, tombstone: 0.2,
      lectern: 0.1, desk: 0.1, crate: 0.2, bone_pile: 0.2, hanging_lantern: 0.3,
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
      furniture:  '#4a3830',   // Old dark oak
      metal:      '#7a6a48',   // Old brass
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
    edge: {
      style: 'rubble_strip',
      intensity: 0.5,
      width: 4,
    },
    propAffinities: {
      pillar: 0.5, rubble: 0.3, brazier: 0.5, coffin: 0.2,
      bookshelf: 0.8, altar: 0.8, puddle: 0.1, barrel: 0.1,
      chains: 0.2, banner: 1.0,      statue: 1.0, throne: 0.7, cage: 0.1, weapon_rack: 0.0,
      torch_sconce: 0.6, skull_pile: 0.2, mushroom_cluster: 0.0, web: 0.4,
      fountain: 0.7, candelabra: 0.9, ritual_circle: 0.3, iron_maiden: 0.0, tombstone: 0.4,
      lectern: 0.8, desk: 0.6, crate: 0.2, bone_pile: 0.4, hanging_lantern: 0.7,
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
      furniture:  '#3a3028',   // Oil-stained industrial wood
      metal:      '#6a6a72',   // Dull iron
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
    edge: {
      style: 'rust_drip',
      intensity: 0.6,
      width: 3,
    },
    propAffinities: {
      pillar: 0.7, rubble: 0.3, brazier: 0.5, coffin: 0.1,
      bookshelf: 0.1, altar: 0.3, puddle: 0.2, barrel: 0.7,
      chains: 0.9, banner: 0.2,      statue: 0.2, throne: 0.1, cage: 0.9, weapon_rack: 0.0,
      torch_sconce: 0.8, skull_pile: 0.4, mushroom_cluster: 0.0, web: 0.2,
      fountain: 0.1, candelabra: 0.2, ritual_circle: 0.1, iron_maiden: 0.9, tombstone: 0.2,
      lectern: 0.1, desk: 0.2, crate: 0.8, bone_pile: 0.3, hanging_lantern: 0.5,
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
      furniture:  '#5a4a35',   // Rough pine
      metal:      '#5a4a3a',   // Rusty iron
    },
    wall: {
      style: 'rough_hewn',
      brickRows: 3,
      mortarWidth: 2,
    },
    floor: {
      style: 'packed_earth',
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
    edge: {
      style: 'dust_drift',
      intensity: 0.4,
      width: 2,
    },
    propAffinities: {
      pillar: 0.4, rubble: 0.7, brazier: 0.7, coffin: 0.0,
      bookshelf: 0.3, altar: 0.3, puddle: 0.1, barrel: 0.9,
      chains: 0.3, banner: 0.1,      statue: 0.1, throne: 0.0, cage: 0.2, weapon_rack: 0.0,
      torch_sconce: 0.8, skull_pile: 0.1, mushroom_cluster: 0.2, web: 0.8,
      fountain: 0.1, candelabra: 0.1, ritual_circle: 0.0, iron_maiden: 0.1, tombstone: 0.1,
      lectern: 0.2, desk: 0.3, crate: 0.8, bone_pile: 0.2, hanging_lantern: 0.5,
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
      furniture:  '#4a4540',   // Bleached whitewashed wood
      metal:      '#6a6570',   // Silver-grey
    },
    wall: {
      style: 'bone_stack',
      boneRows: 4,
      seamWidth: 1,
    },
    floor: {
      style: 'polished_slab',
      slabGrid: 2,
      groutWidth: 1,
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
    edge: {
      style: 'clean_edge',
      intensity: 0.3,
      width: 1,
    },
    propAffinities: {
      pillar: 0.6, rubble: 0.2, brazier: 0.4, coffin: 0.9,
      bookshelf: 0.1, altar: 0.8, puddle: 0.1, barrel: 0.2,
      chains: 0.5, banner: 0.3,      statue: 0.8, throne: 0.4, cage: 0.3, weapon_rack: 0.0,
      torch_sconce: 0.5, skull_pile: 1.0, mushroom_cluster: 0.0, web: 0.3,
      fountain: 0.3, candelabra: 0.4, ritual_circle: 0.2, iron_maiden: 0.3, tombstone: 0.9,
      lectern: 0.3, desk: 0.2, crate: 0.3, bone_pile: 0.9, hanging_lantern: 0.4,
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
      furniture:  '#3a3040',   // Dark mahogany
      metal:      '#5a6068',   // Cold blued steel
    },
    wall: {
      style: 'ashlar_block',
      blockRows: 3,
      blockCols: 2,
      mortarWidth: 1,
    },
    floor: {
      style: 'dusty_tile',
      slabGrid: 3,
      groutWidth: 1,
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
    edge: {
      style: 'seam_line',
      intensity: 0.4,
      width: 1,
    },
    propAffinities: {
      pillar: 0.8, rubble: 0.2, brazier: 0.3, coffin: 0.1,
      bookshelf: 0.9, altar: 0.5, puddle: 0.0, barrel: 0.3,
      chains: 0.2, banner: 0.7,
      statue: 0.7, throne: 0.3, cage: 0.1, weapon_rack: 0.0,
      torch_sconce: 0.4, skull_pile: 0.1, mushroom_cluster: 0.0, web: 0.5,
      fountain: 0.5, candelabra: 0.7, ritual_circle: 0.1, iron_maiden: 0.0, tombstone: 0.1,
      lectern: 0.9, desk: 0.8, crate: 0.3, bone_pile: 0.1, hanging_lantern: 0.6,
    },
  },

  // ─── Phase 21E — New Themes ─────────────────────────────

  fungal_grotto: {
    id: 'fungal_grotto',
    name: 'Fungal Grotto',
    description: 'An alien cave network pulsing with bioluminescent fungal colonies. Mycelium tendrils creep across every surface.',
    palette: {
      primary:    '#121a10',
      secondary:  '#1e2a18',
      accent:     '#5aaa40',
      mortar:     '#0e1a0c',
      highlight:  '#80ee60',
      floor:      '#2a3822',
      floorAlt:   '#2d3b25',
      grout:      '#0a100a',
      furniture:  '#3a4520',   // Fungus-covered rotting wood
      metal:      '#4a6a45',   // Corroded copper
    },
    wall: {
      style: 'fungal_growth',
    },
    floor: {
      style: 'mycelium_mat',
    },
    corridor: {
      style: 'shallow_water',
      waterDepth: 0.06,
    },
    fog: {
      exploredTint: 'rgba(10, 20, 8, 0.55)',
      unexploredColor: '#060a05',
    },
    ambient: {
      vignetteStrength: 0.12,
      vignetteColor: 'rgba(30, 60, 15, 0.08)',
    },
    details: {
      wallOverlayChance: 0.0,
      overlayTypes: [],
    },
    edge: {
      style: 'spore_creep',
      intensity: 0.7,
      width: 5,
    },
    propAffinities: {
      pillar: 0.4, rubble: 0.5, brazier: 0.3, coffin: 0.0,
      bookshelf: 0.0, altar: 0.4, puddle: 0.8, barrel: 0.3,
      chains: 0.2, banner: 0.0,
      statue: 0.3, throne: 0.0, cage: 0.1, weapon_rack: 0.0,
      torch_sconce: 0.2, skull_pile: 0.1, mushroom_cluster: 1.0, web: 0.1,
      fountain: 0.4, candelabra: 0.0, ritual_circle: 0.2, iron_maiden: 0.0, tombstone: 0.1,
      lectern: 0.0, desk: 0.0, crate: 0.2, bone_pile: 0.3, hanging_lantern: 0.1,
    },
  },

  frozen_crypt: {
    id: 'frozen_crypt',
    name: 'Frozen Crypt',
    description: 'A crystalline ice tomb sealed in perpetual frost. Cracked ice over ancient stone, deadly cold radiating from every surface.',
    palette: {
      primary:    '#0a1020',
      secondary:  '#182838',
      accent:     '#4488cc',
      mortar:     '#101828',
      highlight:  '#88ccff',
      floor:      '#253a4e',
      floorAlt:   '#283d51',
      grout:      '#080e18',
      furniture:  '#4a4848',   // Frost-pale birch
      metal:      '#6a7a88',   // Frost-covered steel
    },
    wall: {
      style: 'ice_crystal',
    },
    floor: {
      style: 'frozen_stone',
      slabGrid: 2,
      groutWidth: 1,
    },
    corridor: {
      style: 'shallow_water',
      waterDepth: 0.08,
    },
    fog: {
      exploredTint: 'rgba(8, 12, 25, 0.55)',
      unexploredColor: '#040610',
    },
    ambient: {
      vignetteStrength: 0.10,
      vignetteColor: 'rgba(20, 40, 80, 0.06)',
    },
    details: {
      wallOverlayChance: 0.0,
      overlayTypes: [],
    },
    edge: {
      style: 'frost_creep',
      intensity: 0.8,
      width: 6,
    },
    propAffinities: {
      pillar: 0.7, rubble: 0.4, brazier: 0.2, coffin: 0.3,
      bookshelf: 0.0, altar: 0.5, puddle: 0.0, barrel: 0.2,
      chains: 0.6, banner: 0.3,
      statue: 0.6, throne: 0.3, cage: 0.4, weapon_rack: 0.0,
      torch_sconce: 0.6, skull_pile: 0.5, mushroom_cluster: 0.0, web: 0.2,
      fountain: 0.3, candelabra: 0.4, ritual_circle: 0.2, iron_maiden: 0.3, tombstone: 0.7,
      lectern: 0.2, desk: 0.1, crate: 0.3, bone_pile: 0.6, hanging_lantern: 0.3,
    },
  },

  cursed_shrine: {
    id: 'cursed_shrine',
    name: 'Cursed Shrine',
    description: 'A defiled sacred space drenched in crimson. Blood rituals have corrupted the stone, and cursed gold glows faintly in the dark.',
    palette: {
      primary:    '#1a0a10',
      secondary:  '#2a1520',
      accent:     '#cc4430',
      mortar:     '#200a12',
      highlight:  '#ffaa30',
      floor:      '#3a2028',
      floorAlt:   '#3d232b',
      grout:      '#100810',
      furniture:  '#4a2520',   // Blood-stained dark wood
      metal:      '#5a3a38',   // Dark iron with red patina
    },
    wall: {
      style: 'blood_stone',
      blockRows: 2,
      blockCols: 2,
      mortarWidth: 2,
    },
    floor: {
      style: 'ritual_tile',
      slabGrid: 3,
      groutWidth: 1,
    },
    corridor: {
      style: 'worn_carpet',
      carpetColor: 'rgba(120, 30, 30, 0.12)',
    },
    fog: {
      exploredTint: 'rgba(25, 8, 12, 0.6)',
      unexploredColor: '#0a0408',
    },
    ambient: {
      vignetteStrength: 0.16,
      vignetteColor: 'rgba(100, 20, 15, 0.10)',
    },
    details: {
      wallOverlayChance: 0.0,
      overlayTypes: [],
    },
    edge: {
      style: 'blood_seep',
      intensity: 0.6,
      width: 4,
    },
    propAffinities: {
      pillar: 0.5, rubble: 0.3, brazier: 0.8, coffin: 0.4,
      bookshelf: 0.2, altar: 1.0, puddle: 0.0, barrel: 0.1,
      chains: 0.7, banner: 0.9,
      statue: 0.8, throne: 0.9, cage: 0.5, weapon_rack: 0.0,
      torch_sconce: 0.7, skull_pile: 0.8, mushroom_cluster: 0.0, web: 0.2,
      fountain: 0.3, candelabra: 0.7, ritual_circle: 0.9, iron_maiden: 0.5, tombstone: 0.6,
      lectern: 0.4, desk: 0.3, crate: 0.3, bone_pile: 0.6, hanging_lantern: 0.5,
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
