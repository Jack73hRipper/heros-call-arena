// ─────────────────────────────────────────────────────────
// App.jsx — Theme Designer root component
//
// Three-panel layout:
//   Left:   Theme selector with thumbnails
//   Center: Live dungeon preview OR room archetype preview
//   Right:  Palette details + tile previews
// ─────────────────────────────────────────────────────────

import React, { useState, useCallback } from 'react';
import ThemeSelector from './components/ThemeSelector.jsx';
import DungeonPreview from './components/DungeonPreview.jsx';
import RoomArchetypePreview from './components/RoomArchetypePreview.jsx';
import ObjectBrowser from './components/ObjectBrowser.jsx';
import PvpvePreview from './components/PvpvePreview.jsx';
import PaletteEditor from './components/PaletteEditor.jsx';
import Toolbar from './components/Toolbar.jsx';
import './styles/theme-designer.css';

export default function App() {
  const [activeThemeId, setActiveThemeId] = useState('bleeding_catacombs');
  const [sampleMapId, setSampleMapId] = useState('classic');
  const [viewMode, setViewMode] = useState('dungeon'); // 'dungeon' | 'archetypes' | 'objects' | 'pvpve'
  const [pvpveConfig, setPvpveConfig] = useState({
    gridRows: 6, gridCols: 6, teamCount: 4, seed: 42, _regen: 0,
  });

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
        viewMode={viewMode}
        onViewModeChange={setViewMode}
        pvpveConfig={pvpveConfig}
        onPvpveConfigChange={setPvpveConfig}
      />
      <ThemeSelector
        activeThemeId={activeThemeId}
        onSelectTheme={handleSelectTheme}
      />
      {viewMode === 'pvpve' ? (
        <PvpvePreview
          themeId={activeThemeId}
          gridRows={pvpveConfig.gridRows}
          gridCols={pvpveConfig.gridCols}
          teamCount={pvpveConfig.teamCount}
          seed={pvpveConfig.seed}
          _regen={pvpveConfig._regen}
        />
      ) : viewMode === 'archetypes' ? (
        <RoomArchetypePreview themeId={activeThemeId} />
      ) : viewMode === 'objects' ? (
        <ObjectBrowser themeId={activeThemeId} />
      ) : (
        <DungeonPreview
          themeId={activeThemeId}
          sampleMapId={sampleMapId}
        />
      )}
      <PaletteEditor
        themeId={activeThemeId}
      />
    </div>
  );
}
