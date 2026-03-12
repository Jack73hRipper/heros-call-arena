import React, { useState, useCallback, useMemo } from 'react';
import { useAtlas } from '../context/AtlasContext';

/**
 * SpriteList — Displays all cataloged sprites, filterable by category.
 */
export default function SpriteList() {
  const { state, actions } = useAtlas();
  const [filterCat, setFilterCat] = useState('All');
  const [search, setSearch] = useState('');

  const sprites = useMemo(() => {
    let list = Object.values(state.sprites);
    if (filterCat !== 'All') {
      list = list.filter(s => s.category === filterCat);
    }
    if (search.trim()) {
      const q = search.toLowerCase();
      list = list.filter(s => s.name.toLowerCase().includes(q));
    }
    list.sort((a, b) => {
      if (a.category !== b.category) return a.category.localeCompare(b.category);
      return a.name.localeCompare(b.name);
    });
    return list;
  }, [state.sprites, filterCat, search]);

  const handleClick = useCallback((id, e) => {
    if (e.shiftKey) {
      actions.toggleMultiSelect(id);
    } else {
      actions.selectSprite(id);
    }
  }, [actions]);

  return (
    <div className="panel sprite-list">
      <h3 className="panel-title">
        Sprites ({Object.keys(state.sprites).length})
      </h3>

      <div className="sprite-list-filters">
        <select value={filterCat} onChange={(e) => setFilterCat(e.target.value)}>
          <option value="All">All Categories</option>
          {state.categories.map(c => <option key={c} value={c}>{c}</option>)}
        </select>
        <input
          type="text"
          placeholder="Search…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
      </div>

      <ul className="sprite-list-items">
        {sprites.length === 0 && (
          <li className="muted">No sprites cataloged yet.</li>
        )}
        {sprites.map((sprite) => (
          <li
            key={sprite.id}
            className={`sprite-list-item ${sprite.id === state.selectedSpriteId ? 'selected' : ''} ${state.multiSelect.includes(sprite.id) ? 'multi-selected' : ''}`}
            onClick={(e) => handleClick(sprite.id, e)}
          >
            <span className="sprite-list-name">{sprite.name}</span>
            <span className="sprite-list-cat">{sprite.category}</span>
            <span className="sprite-list-coords">
              {sprite.x},{sprite.y} {sprite.w}×{sprite.h}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}
