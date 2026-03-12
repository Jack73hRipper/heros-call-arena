// ─────────────────────────────────────────────────────────
// ThemeSelector.jsx — Left sidebar: theme list + thumbnails
// ─────────────────────────────────────────────────────────

import React, { useRef, useEffect } from 'react';
import { getThemeSummaries } from '../engine/themes.js';
import { ThemeRenderer } from '../engine/themeRenderer.js';
import { hexToRgb, rgbToCSS } from '../engine/noiseUtils.js';

const THUMB_SIZE = 48;  // Thumbnail tile size
const THUMB_GRID = 3;   // 3x3 mini preview
const CANVAS_SIZE = THUMB_SIZE * THUMB_GRID;

/**
 * Small theme thumbnail canvas — renders a 3x3 grid of wall/floor/corridor
 * tiles in the given theme for visual identification.
 */
function ThemeThumbnail({ theme }) {
  const canvasRef = useRef(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');

    // Mini renderer for this thumbnail
    const renderer = new ThemeRenderer();
    renderer.setTheme(theme.id, THUMB_SIZE);

    // Clear
    ctx.fillStyle = '#0d0d1a';
    ctx.fillRect(0, 0, CANVAS_SIZE, CANVAS_SIZE);

    // Draw 3x3 grid: walls on edges, floor in center, corridor between
    const layout = [
      ['wall', 'wall',     'wall'],
      ['wall', 'floor',    'corridor'],
      ['wall', 'corridor', 'floor'],
    ];

    for (let r = 0; r < THUMB_GRID; r++) {
      for (let c = 0; c < THUMB_GRID; c++) {
        renderer.drawTile(ctx, layout[r][c], c * THUMB_SIZE, r * THUMB_SIZE, c, r);
      }
    }
  }, [theme.id]);

  return (
    <canvas
      ref={canvasRef}
      width={CANVAS_SIZE}
      height={CANVAS_SIZE}
      style={{ width: CANVAS_SIZE, height: CANVAS_SIZE, borderRadius: 4 }}
    />
  );
}

export default function ThemeSelector({ activeThemeId, onSelectTheme }) {
  const themes = getThemeSummaries();

  return (
    <div className="theme-selector">
      <h3 className="panel-title">Dungeon Themes</h3>
      <div className="theme-list">
        {themes.map(theme => (
          <div
            key={theme.id}
            className={`theme-card ${theme.id === activeThemeId ? 'active' : ''}`}
            onClick={() => onSelectTheme(theme.id)}
          >
            <ThemeThumbnail theme={theme} />
            <div className="theme-info">
              <div className="theme-name">{theme.name}</div>
              <div className="theme-desc">{theme.description}</div>
            </div>
            <div className="theme-palette-row">
              {Object.entries(theme.palette).slice(0, 5).map(([key, color]) => (
                <div
                  key={key}
                  className="palette-dot"
                  style={{ backgroundColor: color }}
                  title={`${key}: ${color}`}
                />
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
