// ─────────────────────────────────────────────────────────
// AtlasPalette.jsx — Browse sprite atlas, pick tiles
//
// Displays the full atlas spritesheet as a grid of selectable
// tiles. Supports category filtering, search, and both named
// sprites view and full grid view.
// ─────────────────────────────────────────────────────────

import React, { useState, useRef, useEffect, useCallback } from 'react';
import { filterByCategory, filterBySearch, filterByTags } from '../engine/atlasLoader.js';

const PALETTE_TILE_SIZE = 32; // Display size for palette tiles
const GRID_GAP = 2;

export default function AtlasPalette({
  atlasData,
  fullGrid,
  atlasImage,
  atlasLoaded,
  selectedSprite,
  onSelectSprite,
}) {
  const [viewMode, setViewMode] = useState('named'); // 'named' or 'grid'
  const [category, setCategory] = useState('All');
  const [searchText, setSearchText] = useState('');
  const [activeTags, setActiveTags] = useState([]);
  const canvasRef = useRef(null);
  const containerRef = useRef(null);

  // Toggle a tag filter on/off
  const toggleTag = useCallback((tag) => {
    setActiveTags(prev =>
      prev.includes(tag) ? prev.filter(t => t !== tag) : [...prev, tag]
    );
  }, []);

  // Filter sprites based on mode, category, search, and tags
  const baseSprites = viewMode === 'named'
    ? filterBySearch(filterByCategory(atlasData.sprites, category), searchText)
    : filterBySearch(filterByCategory(fullGrid, category), searchText);
  const sprites = filterByTags(baseSprites, activeTags);

  // Calculate grid layout
  const containerWidth = 240;
  const cols = Math.floor(containerWidth / (PALETTE_TILE_SIZE + GRID_GAP));
  const rows = Math.ceil(sprites.length / cols);

  // Draw the palette canvas
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const width = cols * (PALETTE_TILE_SIZE + GRID_GAP);
    const height = rows * (PALETTE_TILE_SIZE + GRID_GAP);
    canvas.width = width;
    canvas.height = Math.max(height, 100);
    const ctx = canvas.getContext('2d');
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    sprites.forEach((sprite, i) => {
      const col = i % cols;
      const row = Math.floor(i / cols);
      const px = col * (PALETTE_TILE_SIZE + GRID_GAP);
      const py = row * (PALETTE_TILE_SIZE + GRID_GAP);

      // Background
      ctx.fillStyle = '#2a2a3e';
      ctx.fillRect(px, py, PALETTE_TILE_SIZE, PALETTE_TILE_SIZE);

      // Draw sprite if atlas image loaded
      if (atlasLoaded && atlasImage) {
        ctx.drawImage(
          atlasImage,
          sprite.x, sprite.y, sprite.w, sprite.h,
          px, py, PALETTE_TILE_SIZE, PALETTE_TILE_SIZE
        );
      } else {
        // Color fallback
        ctx.fillStyle = getCategoryColor(sprite.category);
        ctx.fillRect(px + 2, py + 2, PALETTE_TILE_SIZE - 4, PALETTE_TILE_SIZE - 4);
        ctx.fillStyle = '#aaa';
        ctx.font = '8px monospace';
        ctx.textAlign = 'center';
        ctx.fillText(`${sprite.row},${sprite.col}`, px + PALETTE_TILE_SIZE / 2, py + PALETTE_TILE_SIZE / 2 + 3);
      }

      // Highlight selected
      if (selectedSprite && selectedSprite.x === sprite.x && selectedSprite.y === sprite.y) {
        ctx.strokeStyle = '#ffcc00';
        ctx.lineWidth = 2;
        ctx.strokeRect(px, py, PALETTE_TILE_SIZE, PALETTE_TILE_SIZE);
      }

      // Named indicator
      if (sprite.isNamed !== false) {
        ctx.fillStyle = '#4a9';
        ctx.fillRect(px, py, 4, 4);
      }
    });
  }, [sprites, atlasImage, atlasLoaded, selectedSprite, cols, rows]);

  // Handle click on palette
  const handleClick = useCallback((e) => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const rect = canvas.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;

    const col = Math.floor(x / (PALETTE_TILE_SIZE + GRID_GAP));
    const row = Math.floor(y / (PALETTE_TILE_SIZE + GRID_GAP));
    const idx = row * cols + col;

    if (idx >= 0 && idx < sprites.length) {
      onSelectSprite(sprites[idx]);
    }
  }, [sprites, cols, onSelectSprite]);

  return (
    <div className="atlas-palette">
      <div className="palette-header">
        <h3>Sprite Atlas</h3>
        <div className="palette-controls">
          <button
            className={`small-btn ${viewMode === 'named' ? 'active' : ''}`}
            onClick={() => setViewMode('named')}
            title="Show named sprites only"
          >
            Named
          </button>
          <button
            className={`small-btn ${viewMode === 'grid' ? 'active' : ''}`}
            onClick={() => setViewMode('grid')}
            title="Show full atlas grid"
          >
            All Tiles
          </button>
        </div>
      </div>

      <input
        type="text"
        className="search-input"
        placeholder="Search sprites..."
        value={searchText}
        onChange={e => setSearchText(e.target.value)}
      />

      <div className="category-filter">
        {['All', ...atlasData.categories].map(cat => (
          <button
            key={cat}
            className={`category-btn ${category === cat ? 'active' : ''}`}
            onClick={() => setCategory(cat)}
          >
            {cat.replace('_', ' ')}
          </button>
        ))}
      </div>

      {/* Tag filter — only show if atlas has tags */}
      {atlasData.tags && atlasData.tags.length > 0 && (
        <div className="tag-filter">
          <span className="tag-filter-label">Tags:</span>
          {atlasData.tags.map(tag => (
            <button
              key={tag}
              className={`tag-filter-btn ${activeTags.includes(tag) ? 'active' : ''}`}
              onClick={() => toggleTag(tag)}
            >
              {tag}
            </button>
          ))}
          {activeTags.length > 0 && (
            <button className="tag-filter-btn tag-clear" onClick={() => setActiveTags([])}>
              ✕ Clear
            </button>
          )}
        </div>
      )}

      <div className="palette-count">
        {sprites.length} sprite{sprites.length !== 1 ? 's' : ''}
      </div>

      <div className="palette-scroll" ref={containerRef}>
        <canvas
          ref={canvasRef}
          onClick={handleClick}
          className="palette-canvas"
        />
      </div>

      {/* Selected sprite info */}
      {selectedSprite && (
        <div className="selected-sprite-info">
          <div className="sprite-preview-box">
            {atlasLoaded && atlasImage ? (
              <SpritePreview sprite={selectedSprite} image={atlasImage} size={48} />
            ) : (
              <div className="sprite-color-preview" style={{ background: getCategoryColor(selectedSprite.category) }} />
            )}
          </div>
          <div className="sprite-details">
            <div className="sprite-name">{selectedSprite.name}</div>
            <div className="sprite-coords">({selectedSprite.x}, {selectedSprite.y})</div>
            <div className="sprite-cat">{selectedSprite.category}</div>
            {selectedSprite.tags && selectedSprite.tags.length > 0 && (
              <div className="sprite-tags-info">
                {selectedSprite.tags.map(t => <span key={t} className="sprite-tag-badge">{t}</span>)}
              </div>
            )}
            {selectedSprite.group && (
              <div className="sprite-group-info">
                ⛓ {selectedSprite.group}{selectedSprite.groupPart ? ` (${selectedSprite.groupPart})` : ''}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

// Mini sprite preview component
function SpritePreview({ sprite, image, size }) {
  const canvasRef = useRef(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || !image) return;
    canvas.width = size;
    canvas.height = size;
    const ctx = canvas.getContext('2d');
    ctx.imageSmoothingEnabled = false;
    ctx.clearRect(0, 0, size, size);
    ctx.drawImage(image, sprite.x, sprite.y, sprite.w, sprite.h, 0, 0, size, size);
  }, [sprite, image, size]);

  return <canvas ref={canvasRef} className="sprite-mini-preview" />;
}

function getCategoryColor(category) {
  const colors = {
    'Floor_Stone': '#6b6b5e',
    'Floor_Dirt': '#8b7355',
    'Floor_Special': '#7b6b9e',
    'Wall_Face': '#3a3a4a',
    'Wall_Top': '#4a4a5a',
    'Wall_Edge': '#3a4a4a',
    'Wall_Accent': '#5a4a4a',
    'Door': '#8a6a3a',
    'Stair': '#6a6a4a',
    'Deco_Wall': '#5a7a5a',
    'Deco_Floor': '#4a6a6a',
    'Furniture': '#7a5a3a',
    'Container': '#8a7a3a',
    'Column': '#5a5a6a',
    'Water': '#3a5a8a',
    'Vegetation': '#3a6a3a',
    'Character': '#4a7a4a',
    'Monster': '#8a3a3a',
    'Effect': '#8a6a8a',
    'UI': '#6a6a6a',
    // Legacy categories (backward compat)
    'Floor_Tiles': '#6b6b5e',
    'Wall_Tiles': '#3a3a4a',
    'Heros': '#4a7a4a',
    'Monsters': '#8a3a3a',
  };
  return colors[category] || '#555';
}
