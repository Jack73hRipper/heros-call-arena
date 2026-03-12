// ─────────────────────────────────────────────────────────
// App.jsx — Theme Designer root component
//
// Three-panel layout:
//   Left:   Theme selector with thumbnails
//   Center: Live dungeon preview on canvas
//   Right:  Palette details + tile previews
// ─────────────────────────────────────────────────────────

import React, { useState, useCallback } from 'react';
import ThemeSelector from './components/ThemeSelector.jsx';
import DungeonPreview from './components/DungeonPreview.jsx';
import PaletteEditor from './components/PaletteEditor.jsx';
import Toolbar from './components/Toolbar.jsx';
import './styles/theme-designer.css';

export default function App() {
  const [activeThemeId, setActiveThemeId] = useState('bleeding_catacombs');
  const [sampleMapId, setSampleMapId] = useState('classic');

  const handleSelectTheme = useCallback((themeId) => {
    setActiveThemeId(themeId);
  }, []);

  const handleSelectMap = useCallback((mapId) => {
    setSampleMapId(mapId);
  }, []);

  const handleExport = useCallback((themeId) => {
    console.log(`[ThemeDesigner] Exported theme: ${themeId}`);
  }, []);

  return (
    <div className="app-layout">
      <Toolbar
        activeThemeId={activeThemeId}
        sampleMapId={sampleMapId}
        onSelectMap={handleSelectMap}
        onExportTheme={handleExport}
      />
      <ThemeSelector
        activeThemeId={activeThemeId}
        onSelectTheme={handleSelectTheme}
      />
      <DungeonPreview
        themeId={activeThemeId}
        sampleMapId={sampleMapId}
      />
      <PaletteEditor
        themeId={activeThemeId}
      />
    </div>
  );
}
