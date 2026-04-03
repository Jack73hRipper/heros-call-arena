// ─────────────────────────────────────────────────────────
// ObjectBrowser.jsx — Browse, inspect, and manage dungeon
// props/placeables across themes and room archetypes.
//
// Views:
//   Grid: Categorized catalog of all props with live previews
//   Detail: Single prop deep-dive with cross-theme rendering,
//           affinity table, and room placement data
// ─────────────────────────────────────────────────────────

import React, { useState, useRef, useEffect, useCallback } from 'react';
import { drawTileProp, PROP_DRAW_MAP, ARCHETYPE_PROP_SLOTS } from '../engine/tileProps.js';
import { getTheme, getThemeIds, THEMES } from '../engine/themes.js';

// ═══════════════════════════════════════════════════════════
//  PROP METADATA — categories + display info
// ═══════════════════════════════════════════════════════════

const PROP_CATEGORIES = {
  structural:    { label: 'Structural',    color: '#7a8a9a' },
  furniture:     { label: 'Furniture',     color: '#a08050' },
  wall_decor:    { label: 'Wall Decor',    color: '#8a6aa0' },
  lighting:      { label: 'Lighting',      color: '#cc9940' },
  environmental: { label: 'Environmental', color: '#50907a' },
  overlay:       { label: 'Overlay',       color: '#6a90b0' },
};

const PROP_META = {
  pillar:            { label: 'Pillar',            category: 'structural',    desc: 'Stone column — boss rooms, corridors' },
  statue:            { label: 'Statue',            category: 'structural',    desc: 'Crumbling stone figure on plinth — shrines, cathedrals, boss arenas' },
  fountain:          { label: 'Fountain',          category: 'structural',    desc: 'Crumbling octagonal stone basin with dark water and concentric ripples — sanctums, cathedrals' },
  rubble:            { label: 'Rubble',            category: 'environmental', desc: 'Scattered debris — abandoned rooms' },
  brazier:           { label: 'Brazier',           category: 'lighting',      desc: 'Flaming bowl — enemy and boss rooms' },
  torch_sconce:      { label: 'Torch Sconce',      category: 'lighting',      desc: 'Wall-mounted flaming torch with warm radial glow — universal lighting' },
  candelabra:        { label: 'Candelabra',        category: 'lighting',      desc: 'Tall ornate multi-armed candle holder with wax drips and individual flames — cathedrals, shrines' },
  coffin:            { label: 'Coffin',            category: 'furniture',     desc: 'Stone sarcophagus — crypts, ossuaries' },
  bookshelf:         { label: 'Bookshelf',         category: 'furniture',     desc: 'Tall shelf with tomes — vaults, libraries' },
  altar:             { label: 'Altar',             category: 'furniture',     desc: 'Sacrificial platform — boss, shrine rooms' },
  throne:            { label: 'Throne',            category: 'furniture',     desc: 'Ornate high-backed chair — boss rooms, dark lord\'s seat' },
  barrel:            { label: 'Barrel',            category: 'furniture',     desc: 'Wooden cask — cellars, loot rooms' },
  cage:              { label: 'Cage',              category: 'furniture',     desc: 'Hanging iron cage on chain — prisons, dungeons' },
  iron_maiden:       { label: 'Iron Maiden',       category: 'furniture',     desc: 'Half-open hinged torture sarcophagus with interior spikes — prisons, iron depths' },
  weapon_rack:       { label: 'Weapon Rack',       category: 'wall_decor',    desc: 'Wall-mounted weapon display — armories, enemy lairs' },
  chains:            { label: 'Chains',            category: 'wall_decor',    desc: 'Dangling links — prisons, iron depths' },
  banner:            { label: 'Banner',            category: 'wall_decor',    desc: 'Tattered cloth — cathedrals, boss rooms' },
  skull_pile:        { label: 'Skull Pile',         category: 'wall_decor',    desc: 'Mound of skulls and bone fragments — crypts, ossuaries' },
  tombstone:         { label: 'Tombstone',         category: 'structural',    desc: 'Weathered gravestone with engraved cross, cracks, and moss — crypts, graveyards' },
  ritual_circle:     { label: 'Ritual Circle',     category: 'environmental', desc: 'Glowing arcane floor sigil with runes and pulsing energy — boss rooms, cursed shrines' },
  puddle:            { label: 'Puddle',            category: 'environmental', desc: 'Water pool — flooded chambers' },
  mushroom_cluster:  { label: 'Mushroom Cluster',  category: 'environmental', desc: 'Bioluminescent fungi with soft glow — grottoes, drowned areas' },
  web:               { label: 'Web',               category: 'environmental', desc: 'Corner spider web — cellars, abandoned rooms' },
  lectern:           { label: 'Lectern',           category: 'furniture',     desc: 'Open book on a wooden stand — libraries, shrines, cathedrals' },
  desk:              { label: 'Desk',              category: 'furniture',     desc: 'Writing desk with quill and papers — libraries, vaults' },
  crate:             { label: 'Crate',             category: 'furniture',     desc: 'Nailed wooden supply crate with X bracing — armories, loot rooms, cellars' },
  bone_pile:         { label: 'Bone Pile',         category: 'environmental', desc: 'Scattered long bones and ribcage fragments — crypts, ossuaries, torture chambers' },
  hanging_lantern:   { label: 'Hanging Lantern',   category: 'lighting',      desc: 'Ceiling-hung iron lantern with warm glow — cathedrals, libraries, shrines' },
  // Overlay decorations — archetype-specific structural elements placed by room overlays
  corner_pillar:     { label: 'Corner Pillar',     category: 'overlay',       desc: 'Boss room corner column with highlight ring — boss sanctums' },
  floor_sigil:       { label: 'Floor Sigil',       category: 'overlay',       desc: 'Geometric circle + diamond pattern etched into floor — boss sanctums' },
  wall_torch:        { label: 'Wall Torch',        category: 'overlay',       desc: 'Wall-mounted torch with glow halo — enemy barracks' },
  wall_alcove:       { label: 'Wall Alcove',       category: 'overlay',       desc: 'Recessed wall niche — loot vaults' },
  corner_ornament:   { label: 'Corner Ornament',   category: 'overlay',       desc: 'L-shaped filigree corner mark — loot vaults' },
  arrival_circle:    { label: 'Arrival Circle',    category: 'overlay',       desc: 'Glowing floor arrival mark — spawn entry halls' },
  archway:           { label: 'Archway',           category: 'overlay',       desc: 'Flanking column archway over doors — spawn entry halls' },
  corner_rubble:     { label: 'Corner Rubble',     category: 'overlay',       desc: 'Debris cluster in room corners — abandoned rooms' },
  stair_descent:     { label: 'Stair Descent',     category: 'overlay',       desc: 'Concentric depth rings suggesting descent — stairwells' },
  wall_banner:       { label: 'Wall Banner',       category: 'overlay',       desc: 'Hanging tattered banner with rod — sacred shrines' },
  wall_chains:       { label: 'Wall Chains',       category: 'overlay',       desc: 'Dangling chain links mounted on wall — prisons' },
  iron_bars:         { label: 'Iron Bars',         category: 'overlay',       desc: 'Vertical iron bars across doorways — prisons' },
  ripple_pool:       { label: 'Ripple Pool',       category: 'overlay',       desc: 'Concentric water ripple arcs — flooded chambers' },
  nave_aisle:        { label: 'Nave Aisle',        category: 'overlay',       desc: 'Central walkway strip with border lines — grand cathedrals' },
  rose_window:       { label: 'Rose Window',       category: 'overlay',       desc: 'Circular stained-glass motif with radial spokes — grand cathedrals' },
  arcane_circle:     { label: 'Arcane Circle',     category: 'overlay',       desc: 'Glowing containment ring with center glow — ritual chambers' },
  floor_rune:        { label: 'Floor Rune',        category: 'overlay',       desc: 'Small cross-shaped arcane mark on floor edge — ritual chambers' },
  disturbed_earth:   { label: 'Disturbed Earth',   category: 'overlay',       desc: 'Irregular darker earth patches — burial grounds' },
  weapon_peg:        { label: 'Weapon Peg',        category: 'overlay',       desc: 'Wall-mounted display pegs with rack bar — armories' },
  wall_light:        { label: 'Wall Light',        category: 'overlay',       desc: 'Warm glow spot with fixture mark — armories' },
  bone_wall:         { label: 'Bone Wall',         category: 'overlay',       desc: 'Horizontal bone-layer texture on wall — ossuaries' },
  bone_alcove:       { label: 'Bone Alcove',       category: 'overlay',       desc: 'Dark inset recess with border — ossuaries' },
  glow_pool:         { label: 'Glow Pool',         category: 'overlay',       desc: 'Bioluminescent center glow with damp highlight — fungal grottoes' },
};

const ALL_PROP_IDS = Object.keys(PROP_META);
const CATEGORY_KEYS = ['all', ...Object.keys(PROP_CATEGORIES)];

// ═══════════════════════════════════════════════════════════
//  CANVAS HELPERS
// ═══════════════════════════════════════════════════════════

function renderPropToCanvas(canvas, propId, palette, size) {
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  canvas.width = size;
  canvas.height = size;

  // Draw floor background so the prop sits on a visible surface
  ctx.fillStyle = palette.floor || '#2a2a2a';
  ctx.fillRect(0, 0, size, size);

  // Subtle grout grid (floor tile feel)
  ctx.strokeStyle = palette.grout || '#111';
  ctx.lineWidth = 0.5;
  const half = size / 2;
  ctx.beginPath();
  ctx.moveTo(half, 0); ctx.lineTo(half, size);
  ctx.moveTo(0, half); ctx.lineTo(size, half);
  ctx.stroke();

  // Draw the prop
  drawTileProp(ctx, propId, 0, 0, size, 42, palette);
}

// ═══════════════════════════════════════════════════════════
//  PROP CARD (grid item)
// ═══════════════════════════════════════════════════════════

function PropCard({ propId, palette, isSelected, onClick }) {
  const canvasRef = useRef(null);
  const meta = PROP_META[propId];
  const cat = PROP_CATEGORIES[meta.category];

  useEffect(() => {
    renderPropToCanvas(canvasRef.current, propId, palette, 96);
  }, [propId, palette]);

  return (
    <div
      className={`obj-card ${isSelected ? 'active' : ''}`}
      onClick={onClick}
    >
      <canvas ref={canvasRef} width={96} height={96} />
      <div className="obj-card-info">
        <span className="obj-card-name">{meta.label}</span>
        <span className="obj-card-cat" style={{ color: cat.color }}>{cat.label}</span>
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════
//  PROP DETAIL PANEL
// ═══════════════════════════════════════════════════════════

function PropDetail({ propId, activeThemeId }) {
  const meta = PROP_META[propId];
  const cat = PROP_CATEGORIES[meta.category];
  const mainCanvasRef = useRef(null);
  const themeCanvasRefs = useRef({});
  const themeIds = getThemeIds();

  // Main large preview
  useEffect(() => {
    const theme = getTheme(activeThemeId);
    renderPropToCanvas(mainCanvasRef.current, propId, theme.palette, 128);
  }, [propId, activeThemeId]);

  // Cross-theme previews
  useEffect(() => {
    for (const tid of themeIds) {
      const canvas = themeCanvasRefs.current[tid];
      if (canvas) {
        const theme = getTheme(tid);
        renderPropToCanvas(canvas, propId, theme.palette, 56);
      }
    }
  }, [propId, themeIds]);

  // Gather affinity data across all themes
  const affinityRows = themeIds.map(tid => {
    const theme = getTheme(tid);
    const aff = theme.propAffinities?.[propId] ?? 0;
    return { id: tid, name: theme.name, affinity: aff };
  });

  // Sort: highest affinity first
  affinityRows.sort((a, b) => b.affinity - a.affinity);

  // Gather room archetype placements
  const archetypeRows = [];
  for (const [archId, config] of Object.entries(ARCHETYPE_PROP_SLOTS)) {
    // Check focal group
    if (config.focal) {
      for (const f of config.focal) {
        if (f.prop === propId) {
          archetypeRows.push({
            archetype: archId,
            position: 'center (focal)',
            chance: f.weight,
          });
        }
      }
    }
    // Check accents
    if (config.accents) {
      for (const slot of config.accents) {
        if (slot.prop === propId) {
          archetypeRows.push({
            archetype: archId,
            position: slot.position,
            chance: slot.chance,
          });
        }
      }
    }
  }

  return (
    <div className="obj-detail">
      {/* Header */}
      <div className="obj-detail-header">
        <canvas ref={mainCanvasRef} width={128} height={128} className="obj-detail-canvas" />
        <div className="obj-detail-titleblock">
          <h2 className="obj-detail-name">{meta.label}</h2>
          <span className="obj-detail-cat" style={{ color: cat.color }}>{cat.label}</span>
          <p className="obj-detail-desc">{meta.desc}</p>
        </div>
      </div>

      {/* Cross-theme previews */}
      <div className="obj-detail-section">
        <h3 className="section-label">Appearance Across Themes</h3>
        <div className="obj-theme-row">
          {themeIds.map(tid => {
            const theme = getTheme(tid);
            const aff = theme.propAffinities?.[propId] ?? 0;
            return (
              <div
                key={tid}
                className={`obj-theme-thumb ${tid === activeThemeId ? 'active' : ''} ${aff === 0 ? 'disabled' : ''}`}
                title={`${theme.name} — affinity: ${aff}`}
              >
                <canvas
                  ref={el => { themeCanvasRefs.current[tid] = el; }}
                  width={56}
                  height={56}
                />
                <span className="obj-theme-thumb-label">{theme.name.split(' ')[0]}</span>
                {aff === 0 && <span className="obj-theme-thumb-off">OFF</span>}
              </div>
            );
          })}
        </div>
      </div>

      {/* Theme Affinity Table */}
      <div className="obj-detail-section">
        <h3 className="section-label">Theme Affinities</h3>
        <div className="obj-affinity-table">
          <div className="obj-affinity-header">
            <span>Theme</span>
            <span>Affinity</span>
            <span></span>
          </div>
          {affinityRows.map(row => (
            <div key={row.id} className={`obj-affinity-row ${row.affinity === 0 ? 'off' : ''}`}>
              <span className="obj-affinity-name">{row.name}</span>
              <span className="obj-affinity-val">{row.affinity.toFixed(1)}</span>
              <div className="obj-affinity-bar-wrap">
                <div
                  className="obj-affinity-bar"
                  style={{
                    width: `${row.affinity * 100}%`,
                    backgroundColor: row.affinity >= 0.7 ? '#5a9a5a'
                      : row.affinity >= 0.3 ? '#9a8a4a' : '#6a4a4a',
                  }}
                />
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Room Placement Table */}
      <div className="obj-detail-section">
        <h3 className="section-label">Room Placements</h3>
        {archetypeRows.length === 0 ? (
          <p className="obj-detail-empty">Not placed in any room archetype.</p>
        ) : (
          <div className="obj-placement-table">
            <div className="obj-placement-header">
              <span>Room Type</span>
              <span>Position</span>
              <span>Base Chance</span>
            </div>
            {archetypeRows.map((row, i) => (
              <div key={i} className="obj-placement-row">
                <span className="obj-placement-arch">{row.archetype}</span>
                <span className="obj-placement-pos">{row.position.replace(/_/g, ' ')}</span>
                <span className="obj-placement-chance">{Math.round(row.chance * 100)}%</span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════
//  OBJECT BROWSER (main export)
// ═══════════════════════════════════════════════════════════

export default function ObjectBrowser({ themeId }) {
  const [activeCat, setActiveCat] = useState('all');
  const [selectedProp, setSelectedProp] = useState(null);
  const theme = getTheme(themeId);

  const filteredProps = activeCat === 'all'
    ? ALL_PROP_IDS
    : ALL_PROP_IDS.filter(id => PROP_META[id].category === activeCat);

  // Count per category
  const catCounts = {};
  for (const id of ALL_PROP_IDS) {
    const c = PROP_META[id].category;
    catCounts[c] = (catCounts[c] || 0) + 1;
  }

  const handleCardClick = useCallback((propId) => {
    setSelectedProp(prev => prev === propId ? null : propId);
  }, []);

  return (
    <div className="object-browser">
      {/* Category tabs */}
      <div className="obj-cat-tabs">
        {CATEGORY_KEYS.map(key => {
          const isAll = key === 'all';
          const label = isAll ? 'All' : PROP_CATEGORIES[key].label;
          const count = isAll ? ALL_PROP_IDS.length : (catCounts[key] || 0);
          return (
            <button
              key={key}
              className={`obj-cat-tab ${activeCat === key ? 'active' : ''}`}
              onClick={() => { setActiveCat(key); setSelectedProp(null); }}
              style={!isAll && activeCat === key ? { borderBottomColor: PROP_CATEGORIES[key].color } : {}}
            >
              {label} <span className="obj-cat-count">({count})</span>
            </button>
          );
        })}
      </div>

      <div className="obj-body">
        {/* Grid */}
        <div className={`obj-grid ${selectedProp ? 'narrowed' : ''}`}>
          {filteredProps.map(id => (
            <PropCard
              key={id}
              propId={id}
              palette={theme.palette}
              isSelected={selectedProp === id}
              onClick={() => handleCardClick(id)}
            />
          ))}
        </div>

        {/* Detail panel */}
        {selectedProp && (
          <div className="obj-detail-panel">
            <button className="obj-detail-close" onClick={() => setSelectedProp(null)}>&times;</button>
            <PropDetail propId={selectedProp} activeThemeId={themeId} />
          </div>
        )}
      </div>
    </div>
  );
}
