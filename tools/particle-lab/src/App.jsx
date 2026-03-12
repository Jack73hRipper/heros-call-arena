// ─────────────────────────────────────────────────────────
// App.jsx — Root component for the Particle Effects Lab
// ─────────────────────────────────────────────────────────

import React, { useState, useRef, useCallback, useEffect } from 'react';
import { ParticleEngine } from './engine/ParticleEngine.js';
import PRESETS from './presets.js';
import Canvas from './components/Canvas.jsx';
import CompoundCanvas from './components/CompoundCanvas.jsx';
import ProjectileCanvas from './components/ProjectileCanvas.jsx';
import Toolbar from './components/Toolbar.jsx';
import ControlPanel from './components/ControlPanel.jsx';
import PresetLibrary from './components/PresetLibrary.jsx';
import CompoundPanel from './components/CompoundPanel.jsx';
import ProjectilePanel from './components/ProjectilePanel.jsx';
import './styles/lab.css';

/** Deep-clone a plain object (JSON-safe). */
function deepClone(obj) {
  return JSON.parse(JSON.stringify(obj));
}

/** Default "blank" preset for creating new effects. */
function createBlankPreset() {
  return {
    name: 'New Effect',
    version: 1,
    duration: 1.0,
    loop: false,
    tags: [],
    emitter: {
      burstMode: true,
      burstCount: 20,
      spawnRate: 30,
      spawnShape: 'point',
      spawnRadius: 0,
      spawnWidth: 0,
      spawnHeight: 0,
      angle: { min: 0, max: 360 },
      speed: { min: 40, max: 100 },
      gravity: { x: 0, y: 0 },
      friction: 0,
      wind: { x: 0 },
    },
    particle: {
      lifetime: { min: 0.3, max: 1.0 },
      shape: 'circle',
      size: { start: { min: 3, max: 6 }, end: { min: 0, max: 1 }, easing: 'easeOutQuad' },
      color: {
        gradient: [
          { stop: 0.0, color: '#ffffff' },
          { stop: 1.0, color: '#ff6600' },
        ],
      },
      alpha: { start: 1, end: 0, easing: 'easeOutCubic' },
      rotation: { start: { min: 0, max: 0 }, speed: { min: 0, max: 0 } },
      trail: { length: 0 },
      blendMode: 'lighter',
    },
  };
}

export default function App() {
  // Engine ref (persists across renders)
  const engineRef = useRef(null);
  if (!engineRef.current) {
    engineRef.current = new ParticleEngine();
  }

  // ── State ──
  const [preset, setPreset] = useState(() => deepClone(PRESETS[0]));
  const [presetLibrary, setPresetLibrary] = useState(() => {
    // Load user presets from localStorage, merge with built-ins
    const saved = localStorage.getItem('particleLab_userPresets');
    const userPresets = saved ? JSON.parse(saved) : [];
    return [...PRESETS.map(p => ({ ...deepClone(p), builtIn: true })), ...userPresets];
  });
  const [selectedPresetName, setSelectedPresetName] = useState(PRESETS[0].name);
  const [showGrid, setShowGrid] = useState(true);
  const [autoEmit, setAutoEmit] = useState(true);
  const [timeScale, setTimeScale] = useState(1);
  const [bgMode, setBgMode] = useState('dark'); // 'dark' | 'grid' | 'grey'
  const [particleCount, setParticleCount] = useState(0);
  const [fps, setFps] = useState(60);

  // ── View Mode ── ('single' | 'compound' | 'projectile')
  const [viewMode, setViewMode] = useState('single');
  const compoundMode = viewMode === 'compound';
  const projectileMode = viewMode === 'projectile';

  const cycleMode = useCallback((mode) => {
    // Toggle: clicking the active mode goes back to single
    setViewMode(prev => prev === mode ? 'single' : mode);
  }, []);
  const [compoundLayers, setCompoundLayers] = useState(() => {
    const saved = localStorage.getItem('particleLab_compoundLayers');
    return saved ? JSON.parse(saved) : [];
  });
  const [activeLayerIndex, setActiveLayerIndex] = useState(null);
  const compoundEngineRef = useRef(null);
  if (!compoundEngineRef.current) {
    compoundEngineRef.current = new ParticleEngine();
  }

  // ── Projectile Mode ──
  const projectileEngineRef = useRef(null);
  if (!projectileEngineRef.current) {
    projectileEngineRef.current = new ParticleEngine();
  }
  const [projectileConfig, setProjectileConfig] = useState(() => {
    const saved = localStorage.getItem('particleLab_projectileConfig');
    return saved ? JSON.parse(saved) : {
      trailPreset: 'arrow-trail',
      headPreset: '',
      impactPreset: 'ranged-hit',
      impactExtras: [],
      speed: 350,
      arc: 0.15,
    };
  });
  const [projectileEndpoints, setProjectileEndpoints] = useState({ startX: 120, startY: 200, endX: 380, endY: 200 });

  // Keep projectile engine presets in sync with library
  useEffect(() => {
    projectileEngineRef.current.presets.clear();
    for (const p of presetLibrary) {
      projectileEngineRef.current.addPreset(p);
    }
  }, [presetLibrary]);

  // Persist projectile config
  useEffect(() => {
    localStorage.setItem('particleLab_projectileConfig', JSON.stringify(projectileConfig));
  }, [projectileConfig]);

  const projectileCanvasRef = useRef(null);
  const [launchTrigger, setLaunchTrigger] = useState(0);

  // Persist compound layers
  useEffect(() => {
    localStorage.setItem('particleLab_compoundLayers', JSON.stringify(compoundLayers));
  }, [compoundLayers]);

  // When selecting a layer in compound mode, load its preset into the editor
  const handleSelectLayer = useCallback((index) => {
    setActiveLayerIndex(index);
    if (index !== null && compoundLayers[index]) {
      setPreset(deepClone(compoundLayers[index].preset));
    }
  }, [compoundLayers]);

  // Sync edits from control panel back to the active compound layer
  useEffect(() => {
    if (!compoundMode || activeLayerIndex === null || activeLayerIndex >= compoundLayers.length) return;
    const currentLayer = compoundLayers[activeLayerIndex];
    if (!currentLayer) return;
    // Only update if preset actually changed (avoid infinite loop)
    if (JSON.stringify(currentLayer.preset) !== JSON.stringify(preset)) {
      setCompoundLayers(prev => prev.map((l, i) =>
        i === activeLayerIndex ? { ...l, preset: deepClone(preset), presetName: preset.name } : l
      ));
    }
  }, [preset, compoundMode, activeLayerIndex]);

  // Undo/redo stacks
  const [undoStack, setUndoStack] = useState([]);
  const [redoStack, setRedoStack] = useState([]);

  // ── Undo/Redo ──
  const pushUndo = useCallback((oldPreset) => {
    setUndoStack(prev => [...prev.slice(-50), deepClone(oldPreset)]);
    setRedoStack([]);
  }, []);

  const undo = useCallback(() => {
    setUndoStack(prev => {
      if (prev.length === 0) return prev;
      const last = prev[prev.length - 1];
      setRedoStack(r => [...r, deepClone(preset)]);
      setPreset(deepClone(last));
      return prev.slice(0, -1);
    });
  }, [preset]);

  const redo = useCallback(() => {
    setRedoStack(prev => {
      if (prev.length === 0) return prev;
      const last = prev[prev.length - 1];
      setUndoStack(u => [...u, deepClone(preset)]);
      setPreset(deepClone(last));
      return prev.slice(0, -1);
    });
  }, [preset]);

  // ── Preset Updates ──
  const updatePreset = useCallback((updater) => {
    setPreset(prev => {
      pushUndo(prev);
      const next = deepClone(prev);
      updater(next);
      return next;
    });
  }, [pushUndo]);

  // ── Preset Library ──
  const selectPreset = useCallback((name) => {
    const found = presetLibrary.find(p => p.name === name);
    if (found) {
      pushUndo(preset);
      setPreset(deepClone(found));
      setSelectedPresetName(name);
    }
  }, [presetLibrary, preset, pushUndo]);

  const savePreset = useCallback(() => {
    setPresetLibrary(prev => {
      const entry = { ...deepClone(preset), builtIn: false };
      // Find any existing entry with this name (built-in OR user)
      const existing = prev.findIndex(p => p.name === preset.name);
      let next;
      if (existing !== -1) {
        // Replace in-place (overwrite built-in or update user copy)
        next = [...prev];
        next[existing] = entry;
      } else {
        next = [...prev, entry];
      }
      // Persist user presets
      const userPresets = next.filter(p => !p.builtIn);
      localStorage.setItem('particleLab_userPresets', JSON.stringify(userPresets));
      return next;
    });
  }, [preset]);

  const deletePreset = useCallback((name) => {
    setPresetLibrary(prev => {
      const next = prev.filter(p => !(p.name === name && !p.builtIn));
      const userPresets = next.filter(p => !p.builtIn);
      localStorage.setItem('particleLab_userPresets', JSON.stringify(userPresets));
      return next;
    });
  }, []);

  const duplicatePreset = useCallback(() => {
    const copy = deepClone(preset);
    copy.name = preset.name + ' (copy)';
    setPreset(copy);
    setSelectedPresetName(copy.name);
  }, [preset]);

  const newPreset = useCallback(() => {
    pushUndo(preset);
    const blank = createBlankPreset();
    setPreset(blank);
    setSelectedPresetName('');
  }, [preset, pushUndo]);

  // ── Import/Export ──
  const exportPreset = useCallback(() => {
    const json = JSON.stringify(preset, null, 2);
    const blob = new Blob([json], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${preset.name.replace(/\s+/g, '-').toLowerCase()}.json`;
    a.click();
    URL.revokeObjectURL(url);
  }, [preset]);

  const exportAll = useCallback(() => {
    // Deduplicate by name — last entry wins (user overrides built-in)
    const seen = new Map();
    for (const p of presetLibrary) {
      const { builtIn, ...rest } = p;
      seen.set(rest.name, rest);
    }
    const all = Array.from(seen.values());
    const json = JSON.stringify(all, null, 2);
    const blob = new Blob([json], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'particle-presets.json';
    a.click();
    URL.revokeObjectURL(url);
  }, [presetLibrary]);

  const importPresets = useCallback(() => {
    const input = document.createElement('input');
    input.type = 'file';
    input.accept = '.json';
    input.multiple = true;
    input.onchange = async (e) => {
      for (const file of e.target.files) {
        try {
          const text = await file.text();
          const data = JSON.parse(text);
          const items = Array.isArray(data) ? data : [data];
          setPresetLibrary(prev => {
            const next = [...prev];
            for (const item of items) {
              if (!item.name) item.name = file.name.replace('.json', '');
              // Check for conflicts
              const existing = next.findIndex(p => p.name === item.name && !p.builtIn);
              const entry = { ...item, builtIn: false };
              if (existing !== -1) {
                next[existing] = entry;
              } else {
                next.push(entry);
              }
            }
            const userPresets = next.filter(p => !p.builtIn);
            localStorage.setItem('particleLab_userPresets', JSON.stringify(userPresets));
            return next;
          });
          // Load the first imported preset into the editor
          const first = Array.isArray(data) ? data[0] : data;
          if (first) {
            pushUndo(preset);
            setPreset(deepClone(first));
            setSelectedPresetName(first.name);
          }
        } catch (err) {
          console.error('Import failed:', err);
          alert(`Failed to import ${file.name}: ${err.message}`);
        }
      }
    };
    input.click();
  }, [preset, pushUndo]);

  const copyToClipboard = useCallback(() => {
    const json = JSON.stringify(preset, null, 2);
    navigator.clipboard.writeText(json).then(() => {
      // Brief visual feedback would go here
    });
  }, [preset]);

  const pasteFromClipboard = useCallback(async () => {
    try {
      const text = await navigator.clipboard.readText();
      const data = JSON.parse(text);
      if (data && (data.name || data.emitter)) {
        pushUndo(preset);
        if (!data.name) data.name = 'Pasted Effect';
        setPreset(deepClone(data));
        setSelectedPresetName(data.name);
      }
    } catch (err) {
      console.error('Paste failed:', err);
    }
  }, [preset, pushUndo]);

  const randomize = useCallback(() => {
    pushUndo(preset);
    const shapes = ['circle', 'square', 'triangle', 'star', 'line'];
    const spawnShapes = ['point', 'circle', 'ring', 'line', 'rect'];
    const easings = ['linear', 'easeOutQuad', 'easeOutCubic', 'easeOutElastic', 'easeOutBounce'];
    const blends = ['lighter', 'source-over', 'screen'];

    const randColor = () => '#' + Math.floor(Math.random() * 0xffffff).toString(16).padStart(6, '0');
    const r = (min, max) => min + Math.random() * (max - min);
    const pick = (arr) => arr[Math.floor(Math.random() * arr.length)];

    const randomPreset = {
      name: 'Random Effect',
      version: 1,
      duration: r(0.2, 3.0),
      loop: Math.random() > 0.6,
      tags: ['random'],
      emitter: {
        burstMode: Math.random() > 0.4,
        burstCount: Math.floor(r(5, 50)),
        spawnRate: Math.floor(r(5, 80)),
        spawnShape: pick(spawnShapes),
        spawnRadius: r(0, 25),
        spawnWidth: r(0, 40),
        spawnHeight: r(0, 40),
        angle: { min: r(0, 180), max: r(180, 360) },
        speed: { min: r(10, 60), max: r(60, 200) },
        gravity: { x: r(-30, 30), y: r(-60, 80) },
        friction: r(0, 0.05),
        wind: { x: r(-20, 20) },
      },
      particle: {
        lifetime: { min: r(0.1, 0.5), max: r(0.5, 2.0) },
        shape: pick(shapes),
        size: {
          start: { min: r(1, 4), max: r(4, 10) },
          end: { min: 0, max: r(0, 3) },
          easing: pick(easings),
        },
        color: {
          gradient: [
            { stop: 0.0, color: randColor() },
            { stop: 0.3 + Math.random() * 0.3, color: randColor() },
            { stop: 1.0, color: randColor() },
          ],
        },
        alpha: { start: r(0.6, 1), end: 0, easing: pick(easings) },
        rotation: { start: { min: 0, max: 0 }, speed: { min: r(-4, 0), max: r(0, 4) } },
        trail: { length: Math.random() > 0.7 ? Math.floor(r(3, 8)) : 0 },
        blendMode: pick(blends),
      },
    };

    setPreset(randomPreset);
    setSelectedPresetName('');
  }, [preset, pushUndo]);

  // ── Keyboard shortcuts ──
  useEffect(() => {
    const handleKey = (e) => {
      // Ctrl+Z = Undo, Ctrl+Y / Ctrl+Shift+Z = Redo
      if (e.ctrlKey && e.key === 'z' && !e.shiftKey) { e.preventDefault(); undo(); }
      if (e.ctrlKey && (e.key === 'y' || (e.key === 'z' && e.shiftKey))) { e.preventDefault(); redo(); }
      if (e.ctrlKey && e.key === 's') { e.preventDefault(); savePreset(); }
      if (e.ctrlKey && e.key === 'e') { e.preventDefault(); exportPreset(); }
      if (e.key === 'g' && !e.ctrlKey && e.target.tagName !== 'INPUT') { setShowGrid(g => !g); }
      if (e.key === 'l' && !e.ctrlKey && e.target.tagName !== 'INPUT') { setAutoEmit(a => !a); }
    };
    window.addEventListener('keydown', handleKey);
    return () => window.removeEventListener('keydown', handleKey);
  }, [undo, redo, savePreset, exportPreset]);

  // ── Drag & Drop import ──
  useEffect(() => {
    const handleDrop = async (e) => {
      e.preventDefault();
      for (const file of e.dataTransfer.files) {
        if (file.name.endsWith('.json')) {
          try {
            const text = await file.text();
            const data = JSON.parse(text);
            const items = Array.isArray(data) ? data : [data];
            setPresetLibrary(prev => {
              const next = [...prev];
              for (const item of items) {
                if (!item.name) item.name = file.name.replace('.json', '');
                next.push({ ...item, builtIn: false });
              }
              const userPresets = next.filter(p => !p.builtIn);
              localStorage.setItem('particleLab_userPresets', JSON.stringify(userPresets));
              return next;
            });
            pushUndo(preset);
            const first = items[0];
            setPreset(deepClone(first));
            setSelectedPresetName(first.name);
          } catch (err) {
            alert(`Failed to import ${file.name}: ${err.message}`);
          }
        }
      }
    };
    const handleDragOver = (e) => e.preventDefault();
    window.addEventListener('drop', handleDrop);
    window.addEventListener('dragover', handleDragOver);
    return () => {
      window.removeEventListener('drop', handleDrop);
      window.removeEventListener('dragover', handleDragOver);
    };
  }, [preset, pushUndo]);

  return (
    <div className="lab-root">
      <Toolbar
        onNew={newPreset}
        onSave={savePreset}
        onDuplicate={duplicatePreset}
        onExport={exportPreset}
        onExportAll={exportAll}
        onImport={importPresets}
        onCopy={copyToClipboard}
        onPaste={pasteFromClipboard}
        onUndo={undo}
        onRedo={redo}
        onRandomize={randomize}
        canUndo={undoStack.length > 0}
        canRedo={redoStack.length > 0}
        presetName={preset.name}
        particleCount={particleCount}
        fps={fps}
        viewMode={viewMode}
        compoundMode={compoundMode}
        onToggleCompound={() => cycleMode('compound')}
        compoundLayerCount={compoundLayers.length}
        projectileMode={projectileMode}
        onToggleProjectile={() => cycleMode('projectile')}
      />

      <div className="lab-body">
        <div className="lab-left">
          {compoundMode ? (
            <CompoundCanvas
              engine={compoundEngineRef.current}
              layers={compoundLayers}
              showGrid={showGrid}
              autoEmit={autoEmit}
              timeScale={timeScale}
              bgMode={bgMode}
              onStatsUpdate={(count, currentFps) => {
                setParticleCount(count);
                setFps(currentFps);
              }}
            />
          ) : projectileMode ? (
            <ProjectileCanvas
              engine={projectileEngineRef.current}
              projectileConfig={projectileConfig}
              showGrid={showGrid}
              autoEmit={autoEmit}
              timeScale={timeScale}
              bgMode={bgMode}
              endpoints={projectileEndpoints}
              onEndpointsChange={setProjectileEndpoints}
              launchTrigger={launchTrigger}
              onStatsUpdate={(count, currentFps) => {
                setParticleCount(count);
                setFps(currentFps);
              }}
            />
          ) : (
            <Canvas
              engine={engineRef.current}
              preset={preset}
              showGrid={showGrid}
              autoEmit={autoEmit}
              timeScale={timeScale}
              bgMode={bgMode}
              onStatsUpdate={(count, currentFps) => {
                setParticleCount(count);
                setFps(currentFps);
              }}
            />
          )}
          <div className="canvas-controls">
            <label title="Toggle grid overlay (G)">
              <input type="checkbox" checked={showGrid} onChange={e => setShowGrid(e.target.checked)} />
              Grid
            </label>
            <label title="Auto-emit loop (L)">
              <input type="checkbox" checked={autoEmit} onChange={e => setAutoEmit(e.target.checked)} />
              Auto-emit
            </label>
            <label>
              BG:
              <select value={bgMode} onChange={e => setBgMode(e.target.value)}>
                <option value="dark">Dark</option>
                <option value="grid">Grid Only</option>
                <option value="grey">Grey</option>
              </select>
            </label>
            <label>
              Speed:
              <select value={timeScale} onChange={e => setTimeScale(Number(e.target.value))}>
                <option value={0.25}>0.25x</option>
                <option value={0.5}>0.5x</option>
                <option value={1}>1x</option>
                <option value={2}>2x</option>
                <option value={4}>4x</option>
              </select>
            </label>
          </div>
          {compoundMode ? (
            <CompoundPanel
              layers={compoundLayers}
              onLayersChange={setCompoundLayers}
              presetLibrary={presetLibrary}
              activeLayerIndex={activeLayerIndex}
              onSelectLayer={handleSelectLayer}
            />
          ) : projectileMode ? (
            <ProjectilePanel
              config={projectileConfig}
              onConfigChange={setProjectileConfig}
              presetLibrary={presetLibrary}
              onLaunch={() => setLaunchTrigger(n => n + 1)}
            />
          ) : (
            <PresetLibrary
              presets={presetLibrary}
              selectedName={selectedPresetName}
              onSelect={selectPreset}
              onDelete={deletePreset}
            />
          )}
        </div>

        <div className="lab-right">
          {projectileMode ? (
            <div className="projectile-editing-label">
              🎯 Projectile Preview Mode
            </div>
          ) : compoundMode && activeLayerIndex !== null && activeLayerIndex < compoundLayers.length ? (
            <div className="compound-editing-label">
              Editing Layer {activeLayerIndex + 1}: <strong>{compoundLayers[activeLayerIndex].presetName}</strong>
            </div>
          ) : null}
          {!projectileMode && (
            <ControlPanel
              preset={preset}
              updatePreset={updatePreset}
            />
          )}
        </div>
      </div>
    </div>
  );
}
