/**
 * Skill utility functions — shared across components.
 *
 * Phase 13-1C: Extracted from BottomBar.jsx and HUD.jsx to eliminate duplication.
 */

/**
 * Check if a caster is within skill range of a target.
 * Mirrors server-side _is_in_skill_range() logic.
 *
 * @param {Object} caster - Unit with position {x, y} and ranged_range
 * @param {Object} target - Unit with position {x, y}
 * @param {Object} skillDef - Skill definition with targeting and range fields
 * @returns {boolean} Whether the target is within skill range
 */
export function isInSkillRange(caster, target, skillDef) {
  if (!caster?.position || !target?.position) return false;
  const dx = Math.abs(caster.position.x - target.position.x);
  const dy = Math.abs(caster.position.y - target.position.y);

  switch (skillDef?.targeting) {
    case 'enemy_adjacent':
      // Chebyshev ≤ 1 (adjacent)
      return Math.max(dx, dy) <= 1 && (dx + dy) > 0;
    case 'enemy_ranged': {
      // Euclidean distance ≤ effective range
      const effectiveRange = skillDef.range > 0 ? skillDef.range : (caster.ranged_range || 5);
      const dist = Math.sqrt(dx * dx + dy * dy);
      return dist <= effectiveRange;
    }
    case 'ally_or_self': {
      // Chebyshev ≤ skill range
      return Math.max(dx, dy) <= (skillDef.range || 1);
    }
    case 'ground_aoe': {
      // Ground AoE: target must be within skill range (cast at target's tile)
      const aoeRange = skillDef.range > 0 ? skillDef.range : (caster.ranged_range || 5);
      const aoeDist = Math.sqrt(dx * dx + dy * dy);
      return aoeDist <= aoeRange;
    }
    default:
      return false;
  }
}
