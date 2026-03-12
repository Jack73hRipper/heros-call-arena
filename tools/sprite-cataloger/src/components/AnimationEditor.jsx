import React, { useState, useCallback, useEffect, useRef } from 'react';
import { useAtlas } from '../context/AtlasContext';

/**
 * AnimationEditor — Create and preview animation sequences from cataloged sprites.
 */
export default function AnimationEditor() {
  const { state, actions } = useAtlas();
  const [newAnimName, setNewAnimName] = useState('');
  const [selectedAnim, setSelectedAnim] = useState(null);
  const [playing, setPlaying] = useState(false);
  const [currentFrame, setCurrentFrame] = useState(0);
  const canvasRef = useRef(null);
  const imgRef = useRef(null);
  const intervalRef = useRef(null);

  const anim = selectedAnim ? state.animations[selectedAnim] : null;
  const animNames = Object.keys(state.animations);

  // Image ref
  useEffect(() => {
    if (!state.sheetSrc) { imgRef.current = null; return; }
    const img = new Image();
    img.onload = () => { imgRef.current = img; };
    img.src = state.sheetSrc;
  }, [state.sheetSrc]);

  // Playback
  useEffect(() => {
    if (playing && anim && anim.frames.length > 0) {
      intervalRef.current = setInterval(() => {
        setCurrentFrame(f => (f + 1) % anim.frames.length);
      }, 1000 / (anim.fps || 4));
    }
    return () => clearInterval(intervalRef.current);
  }, [playing, anim]);

  // Draw current frame
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    ctx.fillStyle = '#1a1a2e';
    ctx.fillRect(0, 0, canvas.width, canvas.height);

    if (!anim || anim.frames.length === 0 || !imgRef.current) {
      ctx.fillStyle = '#666';
      ctx.font = '11px Segoe UI';
      ctx.textAlign = 'center';
      ctx.fillText('No frames', canvas.width / 2, canvas.height / 2);
      return;
    }

    const frameId = anim.frames[currentFrame % anim.frames.length];
    const sprite = state.sprites[frameId];
    if (!sprite) return;

    ctx.imageSmoothingEnabled = false;
    const scale = Math.min(canvas.width / sprite.w, canvas.height / sprite.h) * 0.8;
    const dw = sprite.w * scale;
    const dh = sprite.h * scale;
    ctx.drawImage(imgRef.current,
      sprite.x, sprite.y, sprite.w, sprite.h,
      (canvas.width - dw) / 2, (canvas.height - dh) / 2, dw, dh
    );
  }, [anim, currentFrame, state.sprites, state.sheetSrc]);

  const handleCreate = useCallback(() => {
    const name = newAnimName.trim();
    if (!name) return;
    actions.addAnimation({ name, frames: [], fps: 4, loop: true });
    setSelectedAnim(name);
    setNewAnimName('');
  }, [newAnimName, actions]);

  const handleAddFrame = useCallback(() => {
    if (!anim || !state.selectedSpriteId) return;
    actions.updateAnimation(anim.name, {
      frames: [...anim.frames, state.selectedSpriteId],
    });
  }, [anim, state.selectedSpriteId, actions]);

  const handleRemoveFrame = useCallback((idx) => {
    if (!anim) return;
    const frames = [...anim.frames];
    frames.splice(idx, 1);
    actions.updateAnimation(anim.name, { frames });
  }, [anim, actions]);

  const handleFpsChange = useCallback((fps) => {
    if (!anim) return;
    actions.updateAnimation(anim.name, { fps: Math.max(1, Math.min(30, fps)) });
  }, [anim, actions]);

  const handleDelete = useCallback(() => {
    if (!anim) return;
    actions.deleteAnimation(anim.name);
    setSelectedAnim(null);
    setPlaying(false);
  }, [anim, actions]);

  return (
    <div className="panel animation-editor">
      <h3 className="panel-title">Animations</h3>

      <div className="anim-create">
        <input
          type="text"
          placeholder="New animation…"
          value={newAnimName}
          onChange={(e) => setNewAnimName(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && handleCreate()}
        />
        <button onClick={handleCreate} className="btn btn-small btn-primary" disabled={!newAnimName.trim()}>
          +
        </button>
      </div>

      {animNames.length > 0 && (
        <select
          value={selectedAnim || ''}
          onChange={(e) => { setSelectedAnim(e.target.value || null); setCurrentFrame(0); setPlaying(false); }}
          className="anim-select"
        >
          <option value="">Select animation…</option>
          {animNames.map(n => <option key={n} value={n}>{n} ({(state.animations[n]?.frames || []).length} frames)</option>)}
        </select>
      )}

      {anim && (
        <>
          <div className="anim-preview">
            <canvas ref={canvasRef} width={80} height={80} className="preview-canvas" />
            <div className="anim-controls">
              <button onClick={() => { setPlaying(!playing); }} className="btn btn-small">
                {playing ? '⏸' : '▶'}
              </button>
              <span className="muted small">
                Frame {currentFrame + 1}/{anim.frames.length || 0}
              </span>
            </div>
          </div>

          <div className="anim-fps">
            <label>FPS</label>
            <input type="number" min="1" max="30" value={anim.fps}
              onChange={(e) => handleFpsChange(parseInt(e.target.value) || 4)} />
            <label className="checkbox-label">
              <input type="checkbox" checked={anim.loop}
                onChange={(e) => actions.updateAnimation(anim.name, { loop: e.target.checked })} />
              Loop
            </label>
          </div>

          <div className="anim-frames">
            <div className="anim-frames-header">
              <span>Frames</span>
              <button
                onClick={handleAddFrame}
                className="btn btn-small btn-primary"
                disabled={!state.selectedSpriteId}
                title="Add currently selected sprite as a frame"
              >
                + Add Selected
              </button>
            </div>
            <ul className="anim-frame-list">
              {anim.frames.map((frameId, idx) => {
                const sprite = state.sprites[frameId];
                return (
                  <li key={`${frameId}-${idx}`} className="anim-frame-item">
                    <span>{idx + 1}.</span>
                    <span>{sprite ? sprite.name : '(missing)'}</span>
                    <button onClick={() => handleRemoveFrame(idx)} className="btn-icon btn-danger-icon">×</button>
                  </li>
                );
              })}
            </ul>
          </div>

          <button onClick={handleDelete} className="btn btn-danger btn-small">
            Delete Animation
          </button>
        </>
      )}
    </div>
  );
}
