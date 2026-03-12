import React, { useState, useCallback } from 'react';
import { useAtlas } from '../context/AtlasContext';

/**
 * CategoryManager — Create, rename, and delete sprite categories.
 */
export default function CategoryManager() {
  const { state, actions } = useAtlas();
  const [newCatName, setNewCatName] = useState('');
  const [editingCat, setEditingCat] = useState(null);
  const [editName, setEditName] = useState('');

  const handleAdd = useCallback(() => {
    const name = newCatName.trim();
    if (name) {
      actions.addCategory(name);
      setNewCatName('');
    }
  }, [newCatName, actions]);

  const handleKeyDown = useCallback((e) => {
    if (e.key === 'Enter') handleAdd();
  }, [handleAdd]);

  const startEdit = useCallback((cat) => {
    setEditingCat(cat);
    setEditName(cat);
  }, []);

  const handleRename = useCallback(() => {
    const name = editName.trim();
    if (name && name !== editingCat) {
      actions.renameCategory(editingCat, name);
    }
    setEditingCat(null);
  }, [editName, editingCat, actions]);

  const handleRenameKeyDown = useCallback((e) => {
    if (e.key === 'Enter') handleRename();
    if (e.key === 'Escape') setEditingCat(null);
  }, [handleRename]);

  // Count sprites per category
  const catCounts = {};
  state.categories.forEach(c => { catCounts[c] = 0; });
  Object.values(state.sprites).forEach(s => {
    catCounts[s.category] = (catCounts[s.category] || 0) + 1;
  });

  return (
    <div className="panel category-manager">
      <h3 className="panel-title">Categories</h3>

      <div className="category-add">
        <input
          type="text"
          placeholder="New category..."
          value={newCatName}
          onChange={(e) => setNewCatName(e.target.value)}
          onKeyDown={handleKeyDown}
        />
        <button onClick={handleAdd} className="btn btn-small btn-primary" disabled={!newCatName.trim()}>
          +
        </button>
      </div>

      <ul className="category-list">
        {state.categories.map((cat) => (
          <li key={cat} className="category-item">
            {editingCat === cat ? (
              <input
                type="text"
                value={editName}
                onChange={(e) => setEditName(e.target.value)}
                onKeyDown={handleRenameKeyDown}
                onBlur={handleRename}
                autoFocus
                className="category-edit-input"
              />
            ) : (
              <span className="category-name" onDoubleClick={() => startEdit(cat)}>
                {cat}
                <span className="category-count">({catCounts[cat] || 0})</span>
              </span>
            )}
            {cat !== 'Uncategorized' && (
              <button
                onClick={() => actions.deleteCategory(cat)}
                className="btn-icon btn-danger-icon"
                title="Delete category"
              >
                ×
              </button>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}
