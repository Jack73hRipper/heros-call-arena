import React, { useCallback, useState } from 'react';
import { useAtlas } from '../context/AtlasContext';

// ─── Common tag suggestions for dungeon tilesets ──────────────────
const TAG_SUGGESTIONS = [
  'stone', 'brick', 'cobble', 'wood', 'iron', 'moss', 'damaged', 'clean',
  'tall-2', 'tall-3', 'wide-2', 'wide-3', 'animated',
  'torch', 'banner', 'blood', 'crack', 'debris', 'puddle', 'cobweb',
  'dark', 'light', 'glow', 'shadow',
  'top', 'mid', 'bot', 'left', 'right',
  'corner-tl', 'corner-tr', 'corner-bl', 'corner-br',
  'edge-n', 'edge-s', 'edge-e', 'edge-w',
  'variant-a', 'variant-b', 'variant-c',
];

const GROUP_PART_OPTIONS = ['top', 'mid', 'bot', 'tl', 'tr', 'bl', 'br', 'left', 'right'];

/**
 * SpriteProperties — Edit selected sprite's name, category, tags, group, and coordinates.
 */
export default function SpriteProperties() {
  const { state, actions } = useAtlas();
  const sprite = state.selectedSpriteId ? state.sprites[state.selectedSpriteId] : null;
  const [tagInput, setTagInput] = useState('');
  const [batchTagInput, setBatchTagInput] = useState('');
  const [batchGroupInput, setBatchGroupInput] = useState('');

  const handleChange = useCallback((field, value) => {
    if (!sprite) return;
    actions.updateSprite(sprite.id, { [field]: value });
  }, [sprite, actions]);

  const handleDelete = useCallback(() => {
    if (!sprite) return;
    actions.deleteSprite(sprite.id);
  }, [sprite, actions]);

  // Tag management for single sprite
  const addTag = useCallback((tag) => {
    if (!sprite) return;
    const existing = sprite.tags || [];
    if (!existing.includes(tag)) {
      actions.updateSprite(sprite.id, { tags: [...existing, tag] });
    }
  }, [sprite, actions]);

  const removeTag = useCallback((tag) => {
    if (!sprite) return;
    const existing = sprite.tags || [];
    actions.updateSprite(sprite.id, { tags: existing.filter(t => t !== tag) });
  }, [sprite, actions]);

  const handleTagKeyDown = useCallback((e) => {
    if (e.key === 'Enter' && tagInput.trim()) {
      addTag(tagInput.trim().toLowerCase());
      setTagInput('');
    }
  }, [tagInput, addTag]);

  // Batch ops when multiple selected
  const multiCount = state.multiSelect.length;

  if (!sprite && multiCount === 0) {
    return (
      <div className="panel sprite-properties">
        <h3 className="panel-title">Sprite Properties</h3>
        <p className="muted">Click a grid cell to add or select a sprite.</p>
        <p className="muted small">Shift+click to multi-select.</p>
      </div>
    );
  }

  if (multiCount > 1) {
    return (
      <div className="panel sprite-properties">
        <h3 className="panel-title">{multiCount} Sprites Selected</h3>
        <div className="prop-row">
          <label>Category</label>
          <select
            onChange={(e) => actions.batchAssignCategory(state.multiSelect, e.target.value)}
            defaultValue=""
          >
            <option value="" disabled>Assign category…</option>
            {state.categories.map(c => <option key={c} value={c}>{c}</option>)}
          </select>
        </div>
        <div className="prop-row">
          <label>Name prefix</label>
          <input
            type="text"
            placeholder="e.g. Floor_Cobble"
            onKeyDown={(e) => {
              if (e.key === 'Enter' && e.target.value.trim()) {
                actions.batchNamePrefix(state.multiSelect, e.target.value.trim());
              }
            }}
          />
        </div>
        <div className="prop-row">
          <label>Add tags</label>
          <input
            type="text"
            placeholder="tag1, tag2 (Enter to apply)"
            value={batchTagInput}
            onChange={(e) => setBatchTagInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && batchTagInput.trim()) {
                const tags = batchTagInput.split(',').map(t => t.trim().toLowerCase()).filter(Boolean);
                if (tags.length) actions.batchAssignTags(state.multiSelect, tags);
                setBatchTagInput('');
              }
            }}
          />
        </div>
        <div className="prop-row">
          <label>Group name</label>
          <input
            type="text"
            placeholder="e.g. Bookcase_1 (Enter)"
            value={batchGroupInput}
            onChange={(e) => setBatchGroupInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && batchGroupInput.trim()) {
                // Auto-assign parts based on selection order: top, mid..., bot
                const count = state.multiSelect.length;
                let parts;
                if (count === 2) {
                  parts = ['top', 'bot'];
                } else if (count === 3) {
                  parts = ['top', 'mid', 'bot'];
                } else {
                  parts = state.multiSelect.map((_, i) => `part_${i + 1}`);
                }
                actions.batchAssignGroup(state.multiSelect, batchGroupInput.trim(), parts);
                setBatchGroupInput('');
              }
            }}
          />
          <span className="muted small">Parts auto-assigned: top→bot for 2-3 tiles</span>
        </div>
        <div className="tag-suggestions">
          {['tall-2', 'tall-3', 'wide-2', 'stone', 'brick', 'wood'].map(tag => (
            <button key={tag} className="tag-pill tag-suggest"
              onClick={() => actions.batchAssignTags(state.multiSelect, [tag])}>
              +{tag}
            </button>
          ))}
        </div>
        <button onClick={() => actions.clearSelection()} className="btn btn-small">
          Clear Selection
        </button>
      </div>
    );
  }

  // Filter tag suggestions to only show ones not already applied
  const currentTags = sprite.tags || [];
  const availableSuggestions = TAG_SUGGESTIONS.filter(t => !currentTags.includes(t));

  return (
    <div className="panel sprite-properties">
      <h3 className="panel-title">Sprite Properties</h3>

      <div className="prop-row">
        <label>Name</label>
        <input
          type="text"
          value={sprite.name}
          onChange={(e) => handleChange('name', e.target.value)}
        />
      </div>

      <div className="prop-row">
        <label>Category</label>
        <select
          value={sprite.category}
          onChange={(e) => {
            handleChange('category', e.target.value);
            actions.setLastUsedCategory(e.target.value);
          }}
        >
          {state.categories.map(c => <option key={c} value={c}>{c}</option>)}
        </select>
      </div>

      {/* Tags */}
      <div className="prop-row">
        <label>Tags</label>
        <div className="tags-container">
          {currentTags.map(tag => (
            <span key={tag} className="tag-pill">
              {tag}
              <button className="tag-remove" onClick={() => removeTag(tag)}>×</button>
            </span>
          ))}
        </div>
        <input
          type="text"
          placeholder="Add tag (Enter)"
          value={tagInput}
          onChange={(e) => setTagInput(e.target.value)}
          onKeyDown={handleTagKeyDown}
          className="tag-input"
        />
        <div className="tag-suggestions">
          {availableSuggestions.slice(0, 8).map(tag => (
            <button key={tag} className="tag-pill tag-suggest" onClick={() => addTag(tag)}>
              +{tag}
            </button>
          ))}
        </div>
      </div>

      {/* Group (multi-tile) */}
      <div className="prop-row">
        <label>Group</label>
        <input
          type="text"
          placeholder="e.g. Bookcase_1"
          value={sprite.group || ''}
          onChange={(e) => handleChange('group', e.target.value || null)}
        />
      </div>
      <div className="prop-row">
        <label>Part</label>
        <select
          value={sprite.groupPart || ''}
          onChange={(e) => handleChange('groupPart', e.target.value || null)}
        >
          <option value="">None</option>
          {GROUP_PART_OPTIONS.map(p => <option key={p} value={p}>{p}</option>)}
        </select>
      </div>

      <div className="coords-grid">
        <div className="coord-field">
          <label>X</label>
          <input type="number" value={sprite.x}
            onChange={(e) => handleChange('x', parseInt(e.target.value) || 0)} />
          <div className="nudge-btns">
            <button onClick={() => handleChange('x', sprite.x - 1)}>−</button>
            <button onClick={() => handleChange('x', sprite.x + 1)}>+</button>
          </div>
        </div>
        <div className="coord-field">
          <label>Y</label>
          <input type="number" value={sprite.y}
            onChange={(e) => handleChange('y', parseInt(e.target.value) || 0)} />
          <div className="nudge-btns">
            <button onClick={() => handleChange('y', sprite.y - 1)}>−</button>
            <button onClick={() => handleChange('y', sprite.y + 1)}>+</button>
          </div>
        </div>
        <div className="coord-field">
          <label>W</label>
          <input type="number" value={sprite.w}
            onChange={(e) => handleChange('w', parseInt(e.target.value) || 1)} />
          <div className="nudge-btns">
            <button onClick={() => handleChange('w', sprite.w - 1)}>−</button>
            <button onClick={() => handleChange('w', sprite.w + 1)}>+</button>
          </div>
        </div>
        <div className="coord-field">
          <label>H</label>
          <input type="number" value={sprite.h}
            onChange={(e) => handleChange('h', parseInt(e.target.value) || 1)} />
          <div className="nudge-btns">
            <button onClick={() => handleChange('h', sprite.h - 1)}>−</button>
            <button onClick={() => handleChange('h', sprite.h + 1)}>+</button>
          </div>
        </div>
      </div>

      <div className="prop-row">
        <span className="muted small">Row {sprite.row}, Col {sprite.col}</span>
        {sprite.group && (
          <span className="muted small"> | Group: {sprite.group}{sprite.groupPart ? ` (${sprite.groupPart})` : ''}</span>
        )}
      </div>

      <button onClick={handleDelete} className="btn btn-danger btn-small">
        🗑 Delete Sprite
      </button>
    </div>
  );
}
