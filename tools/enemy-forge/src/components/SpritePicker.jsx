// ─────────────────────────────────────────────────────────
// SpritePicker.jsx — Visual sprite assignment for enemies
// ─────────────────────────────────────────────────────────
// Shows a thumbnail grid of all sprites from the atlas,
// filterable by category/name. Click to assign a base sprite,
// then pick which variants to include.

import React, { useState, useEffect, useRef, useMemo, useCallback } from 'react';

const SHEET_URL = '/spritesheet.png';

/**
 * Groups sprites by base name (e.g. Demon_1, Demon_2 → "Demon")
 * Returns { baseName: [sprite1, sprite2, ...], ... }
 */
function groupSpritesByBase(sprites) {
  const groups = {};
  for (const [name, data] of Object.entries(sprites)) {
    // Strip trailing _N variant number to get base name
    // Use greedy match so "Undead_Knight_2" → base "Undead_Knight", variant 2
    const match = name.match(/^(.+?)_(\d+)$/);
    const baseName = match ? match[1] : name;
    if (!groups[baseName]) groups[baseName] = [];
    groups[baseName].push({ name, variant: match ? parseInt(match[2]) : 0, ...data });
  }
  // Sort variants within each group by variant number
  for (const group of Object.values(groups)) {
    group.sort((a, b) => a.variant - b.variant || a.name.localeCompare(b.name, undefined, { numeric: true }));
  }
  return groups;
}

/**
 * Convert atlas sprite name to a sprite_id key compatible with SpriteLoader.
 * Atlas uses "Demon_1", game uses "demon". Atlas "Undead_Knight_2" → "undead_knight_2"
 */
function atlasNameToSpriteId(atlasName) {
  // Remove trailing _1 (it's the default variant, maps to base key)
  let name = atlasName.replace(/_1$/, '');
  // Convert PascalCase/spaces to snake_case
  name = name
    .replace(/([a-z])([A-Z])/g, '$1_$2')
    .replace(/\s+/g, '_')
    .toLowerCase();
  return name;
}

/**
 * Convert a base group name to the sprite_id base key.
 * e.g. "Demon" → "demon", "Undead_Knight" → "undead_knight"
 */
function baseNameToSpriteId(baseName) {
  return baseName
    .replace(/([a-z])([A-Z])/g, '$1_$2')
    .replace(/\s+/g, '_')
    .toLowerCase();
}

/** Thumbnail canvas — draws a single sprite from the sheet */
function SpriteThumbnail({ sprite, sheetImage, size = 56, selected, onClick, label }) {
  const canvasRef = useRef(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || !sheetImage) return;
    const ctx = canvas.getContext('2d');
    ctx.clearRect(0, 0, size, size);

    // Draw sprite scaled to fit thumbnail
    const padding = 2;
    const drawSize = size - padding * 2;
    ctx.drawImage(
      sheetImage,
      sprite.x, sprite.y, sprite.w, sprite.h,
      padding, padding, drawSize, drawSize
    );
  }, [sprite, sheetImage, size]);

  return (
    <div
      className={`sprite-thumb ${selected ? 'selected' : ''}`}
      onClick={onClick}
      title={label || sprite.name}
    >
      <canvas ref={canvasRef} width={size} height={size} />
      <span className="sprite-thumb-label">{label || sprite.name}</span>
    </div>
  );
}

export default function SpritePicker({ spriteAtlas, enemyId, enemy, onUpdate }) {
  const [sheetImage, setSheetImage] = useState(null);
  const [search, setSearch] = useState('');
  const [categoryFilter, setCategoryFilter] = useState('Monsters');
  const [expanded, setExpanded] = useState(false);

  // Load the spritesheet image
  useEffect(() => {
    const img = new Image();
    img.onload = () => setSheetImage(img);
    img.onerror = () => console.warn('[SpritePicker] Failed to load spritesheet');
    img.src = SHEET_URL;
  }, []);

  // Group all sprites by base name
  const spriteGroups = useMemo(() => {
    if (!spriteAtlas?.sprites) return {};
    return groupSpritesByBase(spriteAtlas.sprites);
  }, [spriteAtlas]);

  // Filter groups by category and search
  const filteredGroups = useMemo(() => {
    return Object.entries(spriteGroups)
      .filter(([baseName, sprites]) => {
        // Category filter
        if (categoryFilter !== 'all') {
          const anyMatch = sprites.some(s => s.category === categoryFilter);
          if (!anyMatch) return false;
        }
        // Search filter
        if (search) {
          const q = search.toLowerCase();
          if (!baseName.toLowerCase().includes(q)) return false;
        }
        return true;
      })
      .sort(([a], [b]) => a.localeCompare(b));
  }, [spriteGroups, categoryFilter, search]);

  // Current assignment
  const currentSpriteId = enemy?.sprite_id || null;
  const currentVariants = enemy?.sprite_variants || 0;

  // Find the currently assigned group for the variant picker
  const assignedGroup = useMemo(() => {
    if (!currentSpriteId) return null;
    // Find the group whose base matches
    for (const [baseName, sprites] of Object.entries(spriteGroups)) {
      if (baseNameToSpriteId(baseName) === currentSpriteId) {
        return { baseName, sprites };
      }
    }
    return null;
  }, [currentSpriteId, spriteGroups]);

  const handleAssign = useCallback((baseName, sprites) => {
    const spriteId = baseNameToSpriteId(baseName);
    onUpdate(enemyId, {
      ...enemy,
      sprite_id: spriteId,
      sprite_variants: sprites.length,
    });
  }, [enemyId, enemy, onUpdate]);

  const handleClear = useCallback(() => {
    const { sprite_id, sprite_variants, ...rest } = enemy;
    onUpdate(enemyId, rest);
  }, [enemyId, enemy, onUpdate]);

  if (!spriteAtlas) {
    return (
      <div className="sprite-picker-empty">
        <span className="text-dim">Loading sprite atlas...</span>
      </div>
    );
  }

  const categories = spriteAtlas.categories || [];

  return (
    <div className="sprite-picker">
      {/* Current Assignment Display */}
      <div className="sprite-current">
        {currentSpriteId && assignedGroup ? (
          <div className="sprite-assigned">
            <div className="sprite-assigned-previews">
              {assignedGroup.sprites.map(s => (
                <SpriteThumbnail
                  key={s.name}
                  sprite={s}
                  sheetImage={sheetImage}
                  size={48}
                  selected={true}
                  label={s.name}
                />
              ))}
            </div>
            <div className="sprite-assigned-info">
              <span className="sprite-assigned-name">{currentSpriteId}</span>
              <span className="sprite-assigned-count">
                {currentVariants} variant{currentVariants !== 1 ? 's' : ''}
              </span>
            </div>
            <button className="btn btn-sm btn-danger" onClick={handleClear} title="Remove sprite">
              ✕
            </button>
          </div>
        ) : (
          <div className="sprite-none">
            <span className="text-dim">No sprite assigned — using shape fallback</span>
          </div>
        )}
      </div>

      {/* Toggle browse panel */}
      <button
        className="btn btn-sm"
        onClick={() => setExpanded(!expanded)}
        style={{ marginTop: 8, width: '100%' }}
      >
        {expanded ? '▲ Hide Sprite Browser' : '▼ Browse & Assign Sprite'}
      </button>

      {/* Sprite Browser (collapsible) */}
      {expanded && (
        <div className="sprite-browser">
          <div className="sprite-browser-filters">
            <input
              type="text"
              placeholder="Search sprites..."
              value={search}
              onChange={e => setSearch(e.target.value)}
              className="search-input"
            />
            <select
              value={categoryFilter}
              onChange={e => setCategoryFilter(e.target.value)}
            >
              <option value="all">All Categories</option>
              {categories.map(c => (
                <option key={c} value={c}>{c}</option>
              ))}
            </select>
          </div>

          <div className="sprite-grid">
            {filteredGroups.map(([baseName, sprites]) => {
              const isAssigned = baseNameToSpriteId(baseName) === currentSpriteId;
              return (
                <div
                  key={baseName}
                  className={`sprite-group ${isAssigned ? 'assigned' : ''}`}
                  onClick={() => handleAssign(baseName, sprites)}
                >
                  {/* Show first variant as the group thumbnail */}
                  <SpriteThumbnail
                    sprite={sprites[0]}
                    sheetImage={sheetImage}
                    size={56}
                    selected={isAssigned}
                  />
                  <div className="sprite-group-info">
                    <span className="sprite-group-name">{baseName}</span>
                    {sprites.length > 1 && (
                      <span className="sprite-group-count">{sprites.length}v</span>
                    )}
                  </div>
                  {isAssigned && <span className="sprite-check">✓</span>}
                </div>
              );
            })}
            {filteredGroups.length === 0 && (
              <div className="sprite-empty text-dim">No sprites match your filter</div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
