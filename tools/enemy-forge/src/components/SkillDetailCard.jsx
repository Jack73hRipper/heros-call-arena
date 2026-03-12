// ─────────────────────────────────────────────────────────
// SkillDetailCard.jsx — Detailed skill breakdown for Enemy Editor
// Phase 18J2: Shows description, targeting, effects with human-readable renderers
// ─────────────────────────────────────────────────────────

import React from 'react';

/* ── Effect Type Renderers ──────────────────────────────
   Each renderer maps an effect object → an array of { label, value } pairs.
   Unknown effect types fall through to a generic key-value dump.
   ─────────────────────────────────────────────────────── */

const EFFECT_RENDERERS = {
  passive_enrage: (eff) => [
    { label: 'HP Threshold', value: `${Math.round((eff.hp_threshold || 0) * 100)}%` },
    { label: 'Damage Multiplier', value: `${eff.damage_multiplier || 1}×` },
  ],

  damage_absorb: (eff) => [
    { label: 'Absorb Amount', value: `${eff.absorb_amount || 0}` },
    { label: 'Duration', value: `${eff.duration_turns || 0} turns` },
  ],

  passive_aura_ally_buff: (eff) => [
    { label: 'Stat', value: `${formatStat(eff.stat)} +${eff.value || 0}` },
    { label: 'Radius', value: `${eff.radius || 0} tiles` },
    ...(eff.requires_tag ? [{ label: 'Requires Tag', value: eff.requires_tag }] : []),
  ],

  buff: (eff) => {
    const stat = eff.stat || '';
    const isMultiplier = stat.includes('multiplier');
    const isPct = stat.includes('pct');
    const magStr = isMultiplier
      ? `${eff.magnitude || 1}×`
      : isPct
        ? `${Math.round((eff.magnitude || 0) * 100)}%`
        : `+${eff.magnitude || 0}`;
    return [
      { label: 'Stat', value: formatStat(stat) },
      { label: 'Magnitude', value: magStr },
      { label: 'Duration', value: `${eff.duration_turns || 0} turns` },
    ];
  },

  stat_multiplier: (eff) => [
    { label: 'Stat', value: formatStat(eff.stat) },
    { label: 'Value', value: `${eff.value || 1}×` },
  ],

  set_stat: (eff) => [
    { label: 'Stat', value: formatStat(eff.stat) },
    { label: 'Value', value: `${eff.value}` },
  ],

  heal: (eff) => [
    { label: 'Amount', value: `${eff.magnitude || eff.amount || 0}` },
  ],

  hot: (eff) => [
    { label: 'Heal/Turn', value: `${eff.heal_per_tick || 0}` },
    { label: 'Duration', value: `${eff.duration_turns || 0} turns` },
    { label: 'Total', value: `${(eff.heal_per_tick || 0) * (eff.duration_turns || 0)}` },
  ],

  damage: (eff) => [
    { label: 'Amount', value: `${eff.amount || eff.base_damage || 0}` },
    ...(eff.damage_type ? [{ label: 'Type', value: eff.damage_type }] : []),
  ],

  melee_damage: (eff) => [
    { label: 'Hits', value: `${eff.hits || 1}` },
    { label: 'Damage Multiplier', value: `${eff.damage_multiplier || 1}×` },
  ],

  ranged_damage: (eff) => [
    { label: 'Damage Multiplier', value: `${eff.damage_multiplier || 1}×` },
  ],

  magic_damage: (eff) => [
    { label: 'Damage Multiplier', value: `${eff.damage_multiplier || 1}×` },
  ],

  holy_damage: (eff) => [
    { label: 'Base Damage', value: `${eff.base_damage || 0}` },
    ...(eff.bonus_vs_tags ? [{ label: 'Bonus vs', value: eff.bonus_vs_tags.join(', ') }] : []),
    ...(eff.bonus_multiplier ? [{ label: 'Bonus Multiplier', value: `${eff.bonus_multiplier}×` }] : []),
  ],

  teleport: () => [
    { label: 'Effect', value: 'Teleport to target tile' },
  ],

  dot: (eff) => [
    { label: 'Damage/Turn', value: `${eff.damage_per_tick || 0}` },
    { label: 'Duration', value: `${eff.duration_turns || 0} turns` },
    { label: 'Total', value: `${(eff.damage_per_tick || 0) * (eff.duration_turns || 0)}` },
  ],

  shield_charges: (eff) => [
    { label: 'Charges', value: `${eff.charges || 0}` },
    { label: 'Reflect Damage', value: `${eff.reflect_damage || 0}` },
    { label: 'Duration', value: `${eff.duration_turns || 0} turns` },
  ],

  detection: (eff) => [
    { label: 'Radius', value: `${eff.radius || 0} tiles` },
    ...(eff.detect_tags ? [{ label: 'Detects', value: eff.detect_tags.join(', ') }] : []),
    { label: 'Duration', value: `${eff.duration_turns || 0} turns` },
  ],

  taunt: (eff) => [
    { label: 'Radius', value: `${eff.radius || 0} tiles` },
    { label: 'Duration', value: `${eff.duration_turns || 0} turns` },
  ],

  stun_damage: (eff) => [
    { label: 'Damage Multiplier', value: `${eff.damage_multiplier || 1}×` },
    { label: 'Stun Duration', value: `${eff.stun_duration || 0} turns` },
  ],

  aoe_heal: (eff) => [
    { label: 'Radius', value: `${eff.radius || 0} tiles` },
    { label: 'Heal Amount', value: `${eff.magnitude || 0}` },
  ],

  aoe_damage: (eff) => [
    { label: 'Radius', value: `${eff.radius || 0} tiles` },
    { label: 'Damage Multiplier', value: `${eff.damage_multiplier || 1}×` },
  ],

  aoe_damage_slow: (eff) => [
    { label: 'Radius', value: `${eff.radius || 0} tiles` },
    { label: 'Base Damage', value: `${eff.base_damage || 0}` },
    { label: 'Slow Duration', value: `${eff.slow_duration || 0} turns` },
  ],

  evasion: (eff) => [
    { label: 'Charges', value: `${eff.charges || 0}` },
    { label: 'Duration', value: `${eff.duration_turns || 0} turns` },
  ],

  ranged_damage_slow: (eff) => [
    { label: 'Damage Multiplier', value: `${eff.damage_multiplier || 1}×` },
    { label: 'Slow Duration', value: `${eff.slow_duration || 0} turns` },
  ],
};

/** Convert snake_case stat names to Title Case */
function formatStat(stat) {
  if (!stat) return '—';
  return stat.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
}

/** Emoji map for targeting types */
const TARGETING_LABELS = {
  passive:        '🔄 Passive',
  self:           '🎯 Self',
  ally:           '💚 Ally',
  ally_or_self:   '💚 Ally or Self',
  enemy_adjacent: '⚔️ Enemy (Adjacent)',
  enemy_ranged:   '🏹 Enemy (Ranged)',
  empty_tile:     '📍 Empty Tile',
  ground_aoe:     '💥 Ground (AoE)',
};

/** Render a single effect block */
function EffectBlock({ effect }) {
  const type = effect.type || 'unknown';
  const renderer = EFFECT_RENDERERS[type];
  const fields = renderer ? renderer(effect) : genericRender(effect);

  return (
    <div className="skill-effect-block">
      <div className="skill-effect-type">{type}</div>
      <div className="skill-effect-fields">
        {fields.map((f, i) => (
          <div key={i} className="skill-effect-field">
            <span className="skill-effect-label">{f.label}:</span>
            <span className="skill-effect-value">{f.value}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

/** Generic fallback: dump all keys except "type" */
function genericRender(effect) {
  return Object.entries(effect)
    .filter(([k]) => k !== 'type')
    .map(([k, v]) => ({
      label: formatStat(k),
      value: typeof v === 'object' ? JSON.stringify(v) : String(v),
    }));
}

/* ── Main Component ──────────────────────────────────── */
export default function SkillDetailCard({ skill }) {
  if (!skill) return null;

  const isPassive = skill.is_passive === true;
  const targetLabel = TARGETING_LABELS[skill.targeting] || skill.targeting || '—';
  const effects = skill.effects || [];

  return (
    <div className={`skill-detail-card ${isPassive ? 'skill-passive' : ''}`}>
      {/* Header row */}
      <div className="skill-detail-header">
        <span className="skill-detail-icon">{skill.icon || '⚙️'}</span>
        <span className="skill-detail-name">{skill.name}</span>
        {isPassive && <span className="skill-passive-badge">PASSIVE</span>}
        {skill.is_auto_attack && <span className="skill-auto-badge">AUTO</span>}
      </div>

      {/* Description */}
      {skill.description && (
        <p className="skill-detail-desc">{skill.description}</p>
      )}

      {/* Targeting / Range / Cooldown bar */}
      <div className="skill-detail-meta">
        <span className="skill-meta-item">
          <span className="skill-meta-label">Targeting</span>
          <span className="skill-meta-value">{targetLabel}</span>
        </span>
        <span className="skill-meta-item">
          <span className="skill-meta-label">Range</span>
          <span className="skill-meta-value">{skill.range || 0}</span>
        </span>
        <span className="skill-meta-item">
          <span className="skill-meta-label">Cooldown</span>
          <span className="skill-meta-value">{skill.cooldown_turns || 0} turns</span>
        </span>
      </div>

      {/* Effects */}
      {effects.length > 0 && (
        <div className="skill-detail-effects">
          <div className="skill-effects-heading">Effects</div>
          {effects.map((eff, idx) => (
            <EffectBlock key={idx} effect={eff} />
          ))}
        </div>
      )}
    </div>
  );
}
