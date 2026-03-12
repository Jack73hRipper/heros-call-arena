// ─────────────────────────────────────────────────────────
// ExportPanel.jsx — Save configs, diff preview, backup list
// ─────────────────────────────────────────────────────────

import React, { useState, useCallback } from 'react';

const CONFIG_LABELS = {
  enemies: 'enemies_config.json',
  rarity: 'monster_rarity_config.json',
  super_uniques: 'super_uniques_config.json',
  loot_tables: 'loot_tables.json',
};

export default function ExportPanel({ configs, dirty, onSave }) {
  const [saving, setSaving] = useState(false);
  const [result, setResult] = useState(null);
  const [showDiff, setShowDiff] = useState(null);
  const [originals, setOriginals] = useState({});

  const dirtyConfigs = [...dirty];

  // Fetch original for diff
  const loadDiff = useCallback(async (key) => {
    if (originals[key]) { setShowDiff(key); return; }
    try {
      const res = await fetch(`/api/config/${key}`);
      const data = await res.json();
      setOriginals(prev => ({ ...prev, [key]: data }));
      setShowDiff(key);
    } catch {
      setShowDiff(key);
    }
  }, [originals]);

  const saveAll = async () => {
    setSaving(true);
    setResult(null);
    const results = [];

    for (const key of dirtyConfigs) {
      try {
        const res = await fetch(`/api/config/${key}`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(configs[key] || {}),
        });
        const data = await res.json();
        results.push({ key, ok: data.ok, msg: data.backup ? `backed up → ${data.backup}` : '' });
      } catch (err) {
        results.push({ key, ok: false, msg: err.message });
      }
    }
    setSaving(false);
    setResult(results);
    if (results.every(r => r.ok)) {
      onSave?.();
    }
  };

  const saveSingle = async (key) => {
    setSaving(true);
    setResult(null);
    try {
      const res = await fetch(`/api/config/${key}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(configs[key] || {}),
      });
      const data = await res.json();
      setResult([{ key, ok: data.ok, msg: data.backup ? `backed up → ${data.backup}` : '' }]);
      if (data.ok) onSave?.(key);
    } catch (err) {
      setResult([{ key, ok: false, msg: err.message }]);
    }
    setSaving(false);
  };

  // Simple JSON diff (line-based)
  const renderDiff = (key) => {
    const orig = originals[key];
    const current = configs[key];
    if (!orig || !current) return <div className="text-dim">Loading...</div>;
    const origLines = JSON.stringify(orig, null, 2).split('\n');
    const curLines = JSON.stringify(current, null, 2).split('\n');
    const maxLen = Math.max(origLines.length, curLines.length);
    const diffs = [];
    for (let i = 0; i < maxLen; i++) {
      const a = origLines[i] ?? '';
      const b = curLines[i] ?? '';
      if (a !== b) diffs.push({ line: i + 1, old: a, new: b });
    }
    if (diffs.length === 0) return <div className="text-dim">No changes</div>;
    return (
      <div className="diff-view">
        <div className="diff-header">{diffs.length} line(s) changed</div>
        <div className="diff-lines">
          {diffs.slice(0, 100).map((d, i) => (
            <div key={i} className="diff-line">
              <span className="diff-line-num">L{d.line}</span>
              {d.old && <div className="diff-old">- {d.old}</div>}
              {d.new && <div className="diff-new">+ {d.new}</div>}
            </div>
          ))}
          {diffs.length > 100 && <div className="text-dim">...and {diffs.length - 100} more</div>}
        </div>
      </div>
    );
  };

  return (
    <div className="export-panel">
      <h3>Export / Save Config Files</h3>
      <p className="text-dim">
        All changes are held in memory until you save. Saving creates a timestamped backup of the original file.
      </p>

      {/* Dirty file list */}
      <div className="card mb-8">
        <h4>Modified Configs</h4>
        {dirtyConfigs.length === 0 ? (
          <div className="text-dim" style={{ padding: 8 }}>No unsaved changes.</div>
        ) : (
          <div className="export-list">
            {dirtyConfigs.map(key => (
              <div key={key} className="export-item">
                <div className="export-item-name">
                  <span className="dirty-dot"></span>
                  {CONFIG_LABELS[key] || `${key}_config.json`}
                </div>
                <div className="flex-row gap-sm">
                  <button className="btn btn-sm" onClick={() => loadDiff(key)}>Diff</button>
                  <button className="btn btn-sm btn-primary" disabled={saving} onClick={() => saveSingle(key)}>Save</button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Save All */}
      {dirtyConfigs.length > 0 && (
        <button className="btn btn-primary" disabled={saving} onClick={saveAll}>
          {saving ? 'Saving...' : `Save All (${dirtyConfigs.length} files)`}
        </button>
      )}

      {/* Results */}
      {result && (
        <div className="card mt-8">
          <h4>Results</h4>
          {result.map((r, i) => (
            <div key={i} className={`export-result ${r.ok ? 'ok' : 'fail'}`}>
              <span>{r.ok ? '✓' : '✕'}</span>
              <span>{CONFIG_LABELS[r.key] || r.key}</span>
              <span className="text-dim">{r.msg}</span>
            </div>
          ))}
        </div>
      )}

      {/* Diff Viewer */}
      {showDiff && (
        <div className="card mt-8">
          <div className="flex-row" style={{ justifyContent: 'space-between' }}>
            <h4>Diff: {CONFIG_LABELS[showDiff] || showDiff}</h4>
            <button className="btn btn-sm" onClick={() => setShowDiff(null)}>Close</button>
          </div>
          {renderDiff(showDiff)}
        </div>
      )}

      {/* Info */}
      <div className="card mt-8">
        <h4>Config File Paths</h4>
        <div className="text-dim" style={{ fontSize: 12 }}>
          <ul style={{ listStyle: 'none', padding: 0, margin: 0 }}>
            <li>server/configs/enemies_config.json</li>
            <li>server/configs/monster_rarity_config.json</li>
            <li>server/configs/super_uniques_config.json</li>
            <li>server/configs/loot_tables.json</li>
          </ul>
        </div>
        <div className="text-dim" style={{ fontSize: 11, marginTop: 8 }}>
          Backups are saved as <code>filename.bak.timestamp.json</code> — last 5 are kept.
        </div>
      </div>
    </div>
  );
}
