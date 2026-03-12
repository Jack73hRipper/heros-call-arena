// ─────────────────────────────────────────────────────────
// ParameterPanel.jsx — CA parameter controls sidebar
// ─────────────────────────────────────────────────────────

import React from 'react';

export default function ParameterPanel({
  params,
  onParamChange,
  onRandomSeed,
  onStepOnce,
  onApplySmooth,
  onApplyErode,
  onApplyDilate,
  onEnsureConnectivity,
  connectivityInfo,
}) {
  const update = (key, value) => {
    onParamChange({ ...params, [key]: value });
  };

  return (
    <div className="panel parameter-panel">
      <h3 className="panel-title">Generation Parameters</h3>

      <div className="param-group">
        <label className="param-label">
          Seed:
          <div className="param-row">
            <input
              type="number"
              value={params.seed}
              onChange={e => update('seed', parseInt(e.target.value) || 0)}
              className="input-number input-wide"
            />
            <button onClick={onRandomSeed} className="btn btn-small" title="Random seed">
              Dice
            </button>
          </div>
        </label>
      </div>

      <div className="param-group">
        <label className="param-label">
          Fill Density: {params.fillPercent}%
          <input
            type="range"
            min={20}
            max={80}
            value={params.fillPercent}
            onChange={e => update('fillPercent', parseInt(e.target.value))}
            className="input-range"
          />
        </label>
      </div>

      <div className="param-group">
        <label className="param-label">
          Birth Threshold: {params.birthThreshold}
          <input
            type="range"
            min={1}
            max={8}
            value={params.birthThreshold}
            onChange={e => update('birthThreshold', parseInt(e.target.value))}
            className="input-range"
          />
        </label>
        <span className="param-hint">Neighbors needed to create wall</span>
      </div>

      <div className="param-group">
        <label className="param-label">
          Survival Threshold: {params.survivalThreshold}
          <input
            type="range"
            min={1}
            max={8}
            value={params.survivalThreshold}
            onChange={e => update('survivalThreshold', parseInt(e.target.value))}
            className="input-range"
          />
        </label>
        <span className="param-hint">Neighbors needed to keep wall alive</span>
      </div>

      <div className="param-group">
        <label className="param-label">
          Iterations: {params.iterations}
          <input
            type="range"
            min={1}
            max={20}
            value={params.iterations}
            onChange={e => update('iterations', parseInt(e.target.value))}
            className="input-range"
          />
        </label>
      </div>

      <div className="param-group">
        <label className="param-label checkbox-label">
          <input
            type="checkbox"
            checked={params.solidBorder}
            onChange={e => update('solidBorder', e.target.checked)}
          />
          Solid Border
        </label>
      </div>

      <h3 className="panel-title" style={{ marginTop: 16 }}>Single Step</h3>
      <div className="param-group">
        <button onClick={onStepOnce} className="btn btn-secondary btn-full">
          Step +1 Iteration
        </button>
      </div>

      <h3 className="panel-title" style={{ marginTop: 16 }}>Post-Processing</h3>

      <div className="param-group">
        <button onClick={onApplySmooth} className="btn btn-secondary btn-full">
          Smooth
        </button>
        <span className="param-hint">Remove jagged protrusions</span>
      </div>

      <div className="param-group">
        <button onClick={onApplyErode} className="btn btn-secondary btn-full">
          Erode
        </button>
        <span className="param-hint">Widen passages</span>
      </div>

      <div className="param-group">
        <button onClick={onApplyDilate} className="btn btn-secondary btn-full">
          Dilate
        </button>
        <span className="param-hint">Thicken walls</span>
      </div>

      <h3 className="panel-title" style={{ marginTop: 16 }}>Connectivity</h3>

      <div className="param-group">
        {connectivityInfo && (
          <div className={`connectivity-status ${connectivityInfo.connected ? 'connected' : 'disconnected'}`}>
            {connectivityInfo.connected
              ? `Connected (1 region)`
              : `Disconnected (${connectivityInfo.regionCount} regions)`
            }
          </div>
        )}
        <button onClick={onEnsureConnectivity} className="btn btn-secondary btn-full">
          Connect All Regions
        </button>
        <span className="param-hint">Carve corridors between isolated chambers</span>
      </div>
    </div>
  );
}
