// ─────────────────────────────────────────────────────────
// PresetLibrary.jsx — Searchable, tagged preset browser
// ─────────────────────────────────────────────────────────

import React, { useState, useMemo } from 'react';

/** Group presets by their first tag (or 'uncategorized'). */
function groupByCategory(presets) {
  const groups = {};
  for (const p of presets) {
    const tag = (p.tags && p.tags[0]) || 'uncategorized';
    if (!groups[tag]) groups[tag] = [];
    groups[tag].push(p);
  }
  return groups;
}

const CATEGORY_ORDER = ['combat', 'magic', 'environment', 'ui', 'random', 'uncategorized'];

export default function PresetLibrary({ presets, selectedName, onSelect, onDelete }) {
  const [search, setSearch] = useState('');
  const [filterTag, setFilterTag] = useState('all');

  // Collect all unique tags
  const allTags = useMemo(() => {
    const tags = new Set();
    for (const p of presets) {
      if (p.tags) p.tags.forEach(t => tags.add(t));
    }
    return ['all', ...Array.from(tags).sort()];
  }, [presets]);

  // Filter presets
  const filtered = useMemo(() => {
    return presets.filter(p => {
      if (search && !p.name.toLowerCase().includes(search.toLowerCase())) return false;
      if (filterTag !== 'all' && (!p.tags || !p.tags.includes(filterTag))) return false;
      return true;
    });
  }, [presets, search, filterTag]);

  // Group by category
  const grouped = useMemo(() => groupByCategory(filtered), [filtered]);

  // Sort categories
  const sortedCategories = Object.keys(grouped).sort((a, b) => {
    const ia = CATEGORY_ORDER.indexOf(a);
    const ib = CATEGORY_ORDER.indexOf(b);
    return (ia === -1 ? 99 : ia) - (ib === -1 ? 99 : ib);
  });

  return (
    <div className="preset-library">
      <div className="library-header">
        <h3>Presets</h3>
        <span className="library-count">{filtered.length}</span>
      </div>

      <div className="library-filters">
        <input
          type="text"
          className="library-search"
          placeholder="Search presets..."
          value={search}
          onChange={e => setSearch(e.target.value)}
        />
        <select
          className="library-tag-filter"
          value={filterTag}
          onChange={e => setFilterTag(e.target.value)}
        >
          {allTags.map(tag => (
            <option key={tag} value={tag}>
              {tag === 'all' ? 'All Tags' : tag}
            </option>
          ))}
        </select>
      </div>

      <div className="library-list">
        {sortedCategories.map(category => (
          <div key={category} className="library-category">
            <div className="category-header">{category}</div>
            {grouped[category].map(p => (
              <div
                key={p.name + (p.builtIn ? '-builtin' : '')}
                className={`library-item ${p.name === selectedName ? 'selected' : ''}`}
                onClick={() => onSelect(p.name)}
              >
                <span className="item-name">{p.name}</span>
                <span className="item-badges">
                  {p.builtIn && <span className="badge badge-builtin">built-in</span>}
                  {p.loop && <span className="badge badge-loop">loop</span>}
                </span>
                {!p.builtIn && (
                  <button
                    className="btn-delete-preset"
                    onClick={(e) => { e.stopPropagation(); onDelete(p.name); }}
                    title="Delete this preset"
                  >
                    ×
                  </button>
                )}
              </div>
            ))}
          </div>
        ))}
        {filtered.length === 0 && (
          <div className="library-empty">No presets match your search.</div>
        )}
      </div>
    </div>
  );
}
