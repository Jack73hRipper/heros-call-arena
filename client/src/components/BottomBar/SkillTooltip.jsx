import React from 'react';

/**
 * TARGETING_LABELS — Human-readable names for targeting types.
 */
const TARGETING_LABELS = {
  enemy_adjacent: 'Enemy (Melee)',
  enemy_ranged: 'Enemy (Ranged)',
  ally_or_self: 'Ally or Self',
  self: 'Self',
  empty_tile: 'Ground Target',
};

/**
 * Format a skill effect into a readable stat line.
 */
function formatEffect(effect) {
  switch (effect.type) {
    case 'melee_damage': {
      const hits = effect.hits || 1;
      const mult = effect.damage_multiplier || 1.0;
      if (hits > 1) {
        return `${hits} hits × ${Math.round(mult * 100)}% melee damage`;
      }
      return mult !== 1.0
        ? `${Math.round(mult * 100)}% melee damage`
        : 'Melee damage';
    }
    case 'ranged_damage': {
      const mult = effect.damage_multiplier || 1.0;
      return mult !== 1.0
        ? `${Math.round(mult * 100)}% ranged damage`
        : 'Ranged damage';
    }
    case 'holy_damage': {
      const base = effect.base_damage || 0;
      const bonusTags = effect.bonus_vs_tags || [];
      const bonusMult = effect.bonus_multiplier || 1.0;
      let line = `${base} holy damage`;
      if (bonusTags.length > 0) {
        const bonusDmg = Math.round(base * bonusMult);
        line += ` (${bonusDmg} vs ${bonusTags.join('/')})`;
      }
      return line;
    }
    case 'heal':
      return `Restores ${effect.magnitude} HP`;
    case 'hot': {
      const hpt = effect.heal_per_tick || effect.heal_per_turn || 0;
      return `Heals ${hpt} HP/turn for ${effect.duration_turns} turns (${hpt * effect.duration_turns} total)`;
    }
    case 'dot':
      return `${effect.damage_per_tick} damage/turn for ${effect.duration_turns} turns (${effect.damage_per_tick * effect.duration_turns} total)`;
    case 'buff': {
      const statNames = {
        melee_damage_multiplier: 'melee damage',
        armor: 'armor',
        ranged_damage_multiplier: 'ranged damage',
      };
      const statLabel = statNames[effect.stat] || effect.stat;
      const magStr = effect.stat?.includes('multiplier')
        ? `${effect.magnitude}×`
        : `+${effect.magnitude}`;
      return `${magStr} ${statLabel} for ${effect.duration_turns} turns`;
    }
    case 'shield_charges':
      return `${effect.charges} charges — reflects ${effect.reflect_damage} damage per hit (${effect.duration_turns} turns)`;
    case 'teleport':
      return 'Teleport to target tile';
    case 'detection': {
      const tags = effect.detect_tags?.join(', ') || 'enemies';
      return `Reveals ${tags} within ${effect.radius} tiles for ${effect.duration_turns} turns`;
    }
    case 'stun_damage': {
      const mult = effect.damage_multiplier || 1.0;
      return `${Math.round(mult * 100)}% melee damage + stun for ${effect.stun_duration} turn(s)`;
    }
    case 'aoe_heal':
      return `Heals all allies within ${effect.radius} tile(s) for ${effect.magnitude} HP`;
    case 'aoe_damage': {
      const mult = effect.damage_multiplier || 1.0;
      return `${Math.round(mult * 100)}% damage to all enemies within ${effect.radius} tile(s) of target`;
    }
    case 'aoe_damage_slow':
      return `${effect.base_damage} damage + slow all enemies within ${effect.radius} tile(s) for ${effect.slow_duration} turn(s)`;
    case 'aoe_damage_slow_targeted':
      return `${effect.base_damage} damage + slow all enemies within ${effect.radius} tile(s) of target for ${effect.slow_duration} turn(s)`;
    case 'aoe_buff': {
      const statNames = {
        all_damage_multiplier: 'damage',
        melee_damage_multiplier: 'melee damage',
        ranged_damage_multiplier: 'ranged damage',
        armor: 'armor',
        attack_damage: 'melee damage',
      };
      const statLabel = statNames[effect.stat] || effect.stat;
      const isMultiplier = effect.stat?.includes('multiplier');
      const magStr = isMultiplier
        ? `+${Math.round((effect.magnitude - 1) * 100)}%`
        : `+${effect.magnitude}`;
      return `${magStr} ${statLabel} to all allies within ${effect.radius} tile(s) for ${effect.duration_turns} turn(s)`;
    }
    case 'aoe_debuff': {
      const statNames = {
        damage_taken_multiplier: 'damage taken',
        damage_dealt_multiplier: 'damage dealt',
      };
      const statLabel = statNames[effect.stat] || effect.stat;
      const isIncrease = effect.magnitude > 1;
      const pctChange = isIncrease
        ? `+${Math.round((effect.magnitude - 1) * 100)}%`
        : `-${Math.round((1 - effect.magnitude) * 100)}%`;
      return `${pctChange} ${statLabel} to all enemies within ${effect.radius} tile(s) for ${effect.duration_turns} turn(s)`;
    }
    case 'magic_damage': {
      const mult = effect.damage_multiplier || 1.0;
      return `${mult}× magic damage`;
    }
    case 'lifesteal_damage': {
      const mult = effect.damage_multiplier || 1.0;
      const healPct = Math.round((effect.heal_pct || 0) * 100);
      return `${Math.round(mult * 100)}% melee damage, heal ${healPct}% of damage dealt`;
    }
    case 'lifesteal_aoe': {
      const mult = effect.damage_multiplier || 1.0;
      const healPct = Math.round((effect.heal_pct || 0) * 100);
      return `${Math.round(mult * 100)}% damage to all enemies within ${effect.radius} tile(s), heal ${healPct}% of total`;
    }
    case 'conditional_buff': {
      const threshPct = Math.round((effect.hp_threshold || 0) * 100);
      const statNames = {
        melee_damage_multiplier: 'melee damage',
        ranged_damage_multiplier: 'ranged damage',
        armor: 'armor',
      };
      const statLabel = statNames[effect.stat] || effect.stat;
      const magStr = effect.stat?.includes('multiplier')
        ? `+${Math.round((effect.magnitude - 1) * 100)}%`
        : `+${effect.magnitude}`;
      let line = `If below ${threshPct}% HP:`;
      if (effect.instant_heal) line += ` heal ${effect.instant_heal} HP,`;
      line += ` ${magStr} ${statLabel} for ${effect.duration_turns} turn(s)`;
      return line;
    }
    case 'buff_cleanse': {
      const statNames = {
        armor: 'armor',
        melee_damage_multiplier: 'melee damage',
        ranged_damage_multiplier: 'ranged damage',
      };
      const statLabel = statNames[effect.stat] || effect.stat;
      const magStr = effect.stat?.includes('multiplier')
        ? `${effect.magnitude}×`
        : `+${effect.magnitude}`;
      let line = `${magStr} ${statLabel} for ${effect.duration_turns} turn(s)`;
      if (effect.cleanse_dots) line += ', cleanses DoT effects';
      return line;
    }
    case 'cooldown_reduction':
      return `Reduce all skill cooldowns by ${effect.reduction} turn(s)`;
    case 'damage_absorb':
      return `Absorbs next ${effect.absorb_amount} damage (${effect.duration_turns} turn(s))`;
    case 'evasion':
      return `Dodge next ${effect.charges} attack(s) (up to ${effect.duration_turns} turn(s))`;
    case 'taunt':
      return `Force enemies within ${effect.radius} tile(s) to target you for ${effect.duration_turns} turn(s)`;
    case 'passive_enrage': {
      const threshPct = Math.round((effect.hp_threshold || 0) * 100);
      const bonusPct = Math.round(((effect.damage_multiplier || 1) - 1) * 100);
      return `Below ${threshPct}% HP: +${bonusPct}% melee damage (permanent)`;
    }
    case 'passive_aura_ally_buff': {
      const tagLabel = effect.requires_tag || 'allies';
      return `+${effect.value} ${effect.stat?.replace(/_/g, ' ')} to nearby ${tagLabel} within ${effect.radius} tile(s)`;
    }
    case 'ranged_damage_slow': {
      const mult = effect.damage_multiplier || 1.0;
      return `${Math.round(mult * 100)}% ranged damage + slow for ${effect.slow_duration} turn(s)`;
    }
    default:
      return effect.type;
  }
}

/**
 * Compute an approximate damage estimate for an effect based on attacker stats.
 * Returns a display string like "~31 dmg" or null if no estimate is applicable.
 */
function computeDamageEstimate(effect, attackerStats) {
  if (!attackerStats) return null;
  const { attack_damage = 0, ranged_damage = 0 } = attackerStats;

  switch (effect.type) {
    case 'melee_damage': {
      if (!attack_damage) return null;
      const mult = effect.damage_multiplier || 1.0;
      const hits = effect.hits || 1;
      const perHit = Math.round(attack_damage * mult);
      if (hits > 1) return `~${perHit} per hit, ~${perHit * hits} total`;
      return `~${perHit} dmg`;
    }
    case 'ranged_damage': {
      if (!ranged_damage) return null;
      const mult = effect.damage_multiplier || 1.0;
      return `~${Math.round(ranged_damage * mult)} dmg`;
    }
    case 'ranged_damage_slow': {
      if (!ranged_damage) return null;
      const mult = effect.damage_multiplier || 1.0;
      return `~${Math.round(ranged_damage * mult)} dmg`;
    }
    case 'magic_damage': {
      if (!ranged_damage) return null;
      const mult = effect.damage_multiplier || 1.0;
      return `~${Math.round(ranged_damage * mult)} dmg`;
    }
    case 'stun_damage': {
      if (!attack_damage) return null;
      const mult = effect.damage_multiplier || 1.0;
      return `~${Math.round(attack_damage * mult)} dmg`;
    }
    case 'lifesteal_damage': {
      if (!attack_damage) return null;
      const mult = effect.damage_multiplier || 1.0;
      const dmg = Math.round(attack_damage * mult);
      const healAmt = Math.round(dmg * (effect.heal_pct || 0));
      return `~${dmg} dmg, ~${healAmt} healed`;
    }
    case 'lifesteal_aoe': {
      if (!attack_damage) return null;
      const mult = effect.damage_multiplier || 1.0;
      return `~${Math.round(attack_damage * mult)} per target`;
    }
    case 'aoe_damage': {
      if (!ranged_damage) return null;
      const mult = effect.damage_multiplier || 1.0;
      return `~${Math.round(ranged_damage * mult)} per target`;
    }
    default:
      return null;
  }
}

/**
 * SkillTooltip — Rich tooltip for ability bar skills.
 *
 * Matches the gear-tooltip visual style (grimdark theme).
 * Shows: name, targeting, range, cooldown, effects, description, hotkey.
 *
 * Props:
 *   skill        — Skill definition object from skills_config
 *   hotkey       — Hotkey number string (e.g. "1")
 *   cooldown     — Current cooldown turns remaining (0 = ready)
 *   isAutoAttack — Whether this is an auto-attack skill
 */
export default function SkillTooltip({ skill, hotkey, cooldown = 0, isAutoAttack = false, attackerStats = null }) {
  if (!skill) return null;

  const targeting = TARGETING_LABELS[skill.targeting] || skill.targeting;
  const range = skill.range > 0 ? skill.range : null;
  const cdMax = skill.cooldown_turns || 0;
  const effects = skill.effects || [];
  const requiresLOS = skill.requires_line_of_sight;

  return (
    <div className="skill-tooltip">
      {/* ── Header: name + hotkey badge ── */}
      <div className="skill-tooltip-header">
        <div className="skill-tooltip-name">{skill.name}</div>
        {hotkey && <span className="skill-tooltip-hotkey-badge">{hotkey}</span>}
      </div>

      <div className="skill-tooltip-divider" />

      {/* ── Stats section: targeting + cooldown ── */}
      <div className="skill-tooltip-type">
        {targeting}
        {range != null && ` · Range: ${range}`}
        {requiresLOS && ' · LOS'}
      </div>

      {cdMax > 0 && (
        <div className={`skill-tooltip-cooldown ${cooldown > 0 ? 'on-cd' : ''}`}>
          {cooldown > 0
            ? `Cooldown: ${cooldown}/${cdMax} turns`
            : `Cooldown: ${cdMax} turns`
          }
          {cooldown > 0 && <span className="cd-status"> (not ready)</span>}
          {cooldown === 0 && cdMax > 0 && <span className="cd-ready"> (ready)</span>}
        </div>
      )}
      {isAutoAttack && (
        <div className="skill-tooltip-cooldown cd-ready">No cooldown</div>
      )}

      {/* ── Effects section ── */}
      {effects.length > 0 && (
        <>
          <div className="skill-tooltip-divider" />
          <div className="skill-tooltip-effects">
            {effects.map((eff, i) => {
              const estimate = computeDamageEstimate(eff, attackerStats);
              return (
                <span key={i}>
                  {formatEffect(eff)}
                  {estimate && <span className="skill-tooltip-estimate">({estimate})</span>}
                </span>
              );
            })}
          </div>
        </>
      )}

      {/* ── Info section: description + flavor ── */}
      {(skill.description || skill.flavor) && (
        <>
          <div className="skill-tooltip-divider" />
          {skill.description && (
            <div className="skill-tooltip-desc">{skill.description}</div>
          )}
          {skill.flavor && (
            <div className="skill-tooltip-flavor">{skill.flavor}</div>
          )}
        </>
      )}
    </div>
  );
}

/**
 * PotionTooltip — Rich tooltip for the potion slot.
 *
 * Props:
 *   potion      — Potion item from inventory (optional, for heal magnitude)
 *   potionCount — Number of potions available
 *   hotkey      — Hotkey number string
 */
export function PotionTooltip({ potion, potionCount = 0, hotkey }) {
  const healAmount = potion?.consumable_effect?.magnitude || 25;

  return (
    <div className="skill-tooltip">
      {/* ── Header: name + hotkey badge ── */}
      <div className="skill-tooltip-header">
        <div className="skill-tooltip-name">Health Potion</div>
        {hotkey && <span className="skill-tooltip-hotkey-badge">{hotkey}</span>}
      </div>

      <div className="skill-tooltip-divider" />

      {/* ── Stats ── */}
      <div className="skill-tooltip-type">Consumable · Self</div>

      {/* ── Effects ── */}
      <div className="skill-tooltip-divider" />
      <div className="skill-tooltip-effects">
        <span>Restores {healAmount} HP</span>
      </div>

      {/* ── Info ── */}
      <div className="skill-tooltip-divider" />
      <div className="skill-tooltip-desc">
        Drink a healing potion to recover health in combat.
      </div>
      <div className="skill-tooltip-stock">
        {potionCount > 0
          ? `${potionCount} remaining`
          : 'None available'
        }
      </div>
    </div>
  );
}
