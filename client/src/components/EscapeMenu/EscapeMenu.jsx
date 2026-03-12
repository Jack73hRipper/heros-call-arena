/**
 * EscapeMenu.jsx — Overlay menu triggered by the Escape key.
 * Phase 15: Menu Overhaul
 *
 * Supports two contexts:
 *  - 'game' (default): In-game menu with Surrender & Leave
 *  - 'town': Town hub menu with Quit Game (exit to desktop)
 *
 * Options:
 *  - Resume (close menu)
 *  - Settings (placeholder — will house Keybinds, Graphics, Audio sub-menus)
 *  - Keybinds (quick reference of all keyboard shortcuts)
 *  - Surrender / Leave Match (game) or Quit Game (town)
 */
import React, { useState } from 'react';

// ──── Keybind reference data ────
const KEYBIND_SECTIONS = [
  {
    title: 'Movement & Actions',
    binds: [
      { key: 'W A S D', desc: 'Move (cardinal + diagonal combos)' },
      { key: 'E', desc: 'Interact (loot, open chests, toggle doors, use portal/stairs)' },
      { key: 'I', desc: 'Toggle inventory (dungeon only)' },
      { key: 'Left Click', desc: 'Queue movement / select target' },
      { key: 'Right Click', desc: 'Auto-target pursue enemy' },
    ],
  },
  {
    title: 'Combat',
    binds: [
      { key: '1 – 5', desc: 'Activate skill slot' },
      { key: 'X', desc: 'Cancel all (clear queue, auto-target, action mode)' },
      { key: 'Tab', desc: 'Cycle target to next visible enemy' },
      { key: 'Shift + Tab', desc: 'Cycle target to previous visible enemy' },
    ],
  },
  {
    title: 'Party Control',
    binds: [
      { key: 'Ctrl + A', desc: 'Select all party members' },
      { key: 'F1', desc: 'Target self' },
      { key: 'F2 – F5', desc: 'Target party member by slot' },
      { key: 'Shift + F1', desc: 'Return control to self' },
      { key: 'Shift + F2–F5', desc: 'Take control of party member' },
      { key: 'Ctrl + 1–4', desc: 'Set stance (Follow / Aggressive / Defensive / Hold)' },
    ],
  },
  {
    title: 'UI & Display',
    binds: [
      { key: 'M', desc: 'Toggle minimap (normal / expanded)' },
      { key: 'Alt (hold)', desc: 'Show ground item labels' },
      { key: 'Esc', desc: 'Open / close this menu' },
    ],
  },
];

export default function EscapeMenu({ onResume, onLeave, context = 'game' }) {
  const [view, setView] = useState('main'); // 'main' | 'keybinds' | 'settings'

  const handleQuitGame = () => {
    if (window.electronAPI?.quitApp) {
      window.electronAPI.quitApp();
    } else {
      // Browser fallback — close the tab/window
      window.close();
    }
  };

  const handleBackdropClick = (e) => {
    // Only close if clicking the backdrop itself, not the panel
    if (e.target === e.currentTarget) {
      onResume();
    }
  };

  return (
    <div className="esc-menu-backdrop" onClick={handleBackdropClick}>
      <div className="esc-menu-panel grim-frame grim-frame--ember">

        {/* ── Main Menu ── */}
        {view === 'main' && (
          <>
            <h2 className="esc-menu-title grim-header">Menu</h2>
            <div className="grim-separator">◆</div>
            <div className="esc-menu-buttons">
              <button className="grim-btn grim-btn--md grim-btn--ember grim-btn--full" onClick={onResume}>
                Resume
              </button>
              <button className="grim-btn grim-btn--md grim-btn--steel grim-btn--full" onClick={() => setView('settings')}>
                Settings
              </button>
              <button className="grim-btn grim-btn--md grim-btn--steel grim-btn--full" onClick={() => setView('keybinds')}>
                Keybinds
              </button>
              <div className="grim-separator grim-separator--subtle">◆</div>
              {context === 'town' ? (
                <button className="grim-btn grim-btn--md grim-btn--crimson grim-btn--full" onClick={handleQuitGame}>
                  Quit Game
                </button>
              ) : (
                <button className="grim-btn grim-btn--md grim-btn--crimson grim-btn--full" onClick={onLeave}>
                  Surrender &amp; Leave
                </button>
              )}
            </div>
          </>
        )}

        {/* ── Settings (placeholder) ── */}
        {view === 'settings' && (
          <>
            <h2 className="esc-menu-title grim-header">Settings</h2>
            <div className="grim-separator">◆</div>
            <div className="esc-menu-settings-placeholder">
              <p className="esc-menu-coming-soon">Audio, Graphics &amp; Keybind settings coming soon.</p>
            </div>
            <div className="esc-menu-buttons">
              <button className="grim-btn grim-btn--md grim-btn--steel grim-btn--full" onClick={() => setView('main')}>
                ← Back
              </button>
            </div>
          </>
        )}

        {/* ── Keybinds Reference ── */}
        {view === 'keybinds' && (
          <>
            <h2 className="esc-menu-title grim-header">Keybinds</h2>
            <div className="grim-separator">◆</div>
            <div className="esc-menu-keybinds">
              {KEYBIND_SECTIONS.map((section) => (
                <div key={section.title} className="esc-menu-keybind-section">
                  <h3 className="esc-menu-keybind-section-title">{section.title}</h3>
                  <div className="esc-menu-keybind-list">
                    {section.binds.map((bind) => (
                      <div key={bind.key} className="esc-menu-keybind-row">
                        <kbd className="esc-menu-kbd">{bind.key}</kbd>
                        <span className="esc-menu-keybind-desc">{bind.desc}</span>
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </div>
            <div className="esc-menu-buttons">
              <button className="grim-btn grim-btn--md grim-btn--steel grim-btn--full" onClick={() => setView('main')}>
                ← Back
              </button>
            </div>
          </>
        )}

      </div>
    </div>
  );
}
