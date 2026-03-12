// ─────────────────────────────────────────────────────────
// Shared slider + control helpers for the control panel
// ─────────────────────────────────────────────────────────

import React from 'react';

/**
 * A labeled slider with numeric input and double-click-to-reset.
 */
export function Slider({ label, value, min, max, step, onChange, defaultValue, title }) {
  const handleDoubleClick = () => {
    if (defaultValue !== undefined) onChange(defaultValue);
  };

  return (
    <div className="slider-row" title={title}>
      <label className="slider-label">{label}</label>
      <input
        type="range"
        className="slider-input"
        min={min}
        max={max}
        step={step || 0.01}
        value={value}
        onChange={e => onChange(Number(e.target.value))}
        onDoubleClick={handleDoubleClick}
      />
      <input
        type="number"
        className="slider-number"
        min={min}
        max={max}
        step={step || 0.01}
        value={typeof value === 'number' ? Math.round(value * 100) / 100 : value}
        onChange={e => onChange(Number(e.target.value))}
      />
    </div>
  );
}

/**
 * A min/max range slider pair on one row.
 */
export function RangeSlider({ label, minVal, maxVal, min, max, step, onChangeMin, onChangeMax, title }) {
  return (
    <div className="range-row" title={title}>
      <label className="slider-label">{label}</label>
      <div className="range-inputs">
        <span className="range-label">Min</span>
        <input
          type="range"
          className="slider-input range-half"
          min={min}
          max={max}
          step={step || 0.01}
          value={minVal}
          onChange={e => onChangeMin(Number(e.target.value))}
        />
        <input
          type="number"
          className="slider-number"
          min={min}
          max={max}
          step={step || 0.01}
          value={Math.round(minVal * 100) / 100}
          onChange={e => onChangeMin(Number(e.target.value))}
        />
        <span className="range-label">Max</span>
        <input
          type="range"
          className="slider-input range-half"
          min={min}
          max={max}
          step={step || 0.01}
          value={maxVal}
          onChange={e => onChangeMax(Number(e.target.value))}
        />
        <input
          type="number"
          className="slider-number"
          min={min}
          max={max}
          step={step || 0.01}
          value={Math.round(maxVal * 100) / 100}
          onChange={e => onChangeMax(Number(e.target.value))}
        />
      </div>
    </div>
  );
}

/**
 * Dropdown selector.
 */
export function Select({ label, value, options, onChange, title }) {
  return (
    <div className="slider-row" title={title}>
      <label className="slider-label">{label}</label>
      <select className="control-select" value={value} onChange={e => onChange(e.target.value)}>
        {options.map(opt => (
          <option key={opt.value || opt} value={opt.value || opt}>
            {opt.label || opt}
          </option>
        ))}
      </select>
    </div>
  );
}

/**
 * Toggle checkbox.
 */
export function Toggle({ label, value, onChange, title }) {
  return (
    <div className="slider-row" title={title}>
      <label className="slider-label">{label}</label>
      <label className="toggle-switch">
        <input type="checkbox" checked={value} onChange={e => onChange(e.target.checked)} />
        <span className="toggle-slider"></span>
      </label>
    </div>
  );
}
