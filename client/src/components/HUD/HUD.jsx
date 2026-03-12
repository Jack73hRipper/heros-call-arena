import React from 'react';
import { useGameState } from '../../context/GameStateContext';
import { isInSkillRange } from '../../utils/skillUtils';

/**
 * HUD — Slimmed info panel (6E-2: turn/timer/HP/buffs moved to HeaderBar).
 * Shows: cooldowns, equipment summary, queue status, auto-target frame.
 * Phase 10G-7: Extended with skill auto-target info + selected target pane.
 */
export default function HUD({ turnTimer }) {
  const gameState = useGameState();
  const { players, playerId, matchType,
          isDungeon,
          autoTargetId, activeUnitId,
          // Phase 10G-7: Skill auto-target + selected target
          autoSkillId, selectedTargetId,
          classSkills, allClassSkills } = gameState;

  const effectiveUnitId = activeUnitId || playerId;
  const myPlayer = players[playerId];
  const activeUnit = players[effectiveUnitId];

  const rangedCooldown = myPlayer?.cooldowns?.ranged_attack || 0;

  // Phase 10E-2: Auto-target info
  const targetPlayer = autoTargetId ? players[autoTargetId] : null;
  const hasAutoTarget = targetPlayer && targetPlayer.is_alive !== false;

  // Phase 10G-7: Resolve skill definition for auto-skill
  const autoSkillDef = (() => {
    if (!autoSkillId) return null;
    // Search all known skills across classSkills and allClassSkills
    if (classSkills) {
      const found = classSkills.find(s => s.skill_id === autoSkillId);
      if (found) return found;
    }
    if (allClassSkills) {
      for (const skills of Object.values(allClassSkills)) {
        const found = skills.find(s => s.skill_id === autoSkillId);
        if (found) return found;
      }
    }
    return null;
  })();

  const isHealSkill = autoSkillDef?.targeting === 'ally_or_self';

  // Phase 10G-7: Compute skill-aware status text
  let targetStatus = null;
  if (hasAutoTarget && activeUnit?.position && targetPlayer?.position) {
    if (autoSkillId && autoSkillDef) {
      const inRange = isInSkillRange(activeUnit, targetPlayer, autoSkillDef);
      const cdRemaining = activeUnit?.cooldowns?.[autoSkillId] || 0;
      if (inRange && cdRemaining > 0) {
        targetStatus = `Cooldown (${cdRemaining})`;
      } else if (inRange) {
        targetStatus = `Casting ${autoSkillDef.name}!`;
      } else {
        targetStatus = `Approaching for ${autoSkillDef.name}...`;
      }
    } else {
      // Original melee status
      const dx = Math.abs(activeUnit.position.x - targetPlayer.position.x);
      const dy = Math.abs(activeUnit.position.y - targetPlayer.position.y);
      targetStatus = (dx <= 1 && dy <= 1 && (dx + dy > 0)) ? 'Attacking!' : 'Pursuing...';
    }
  }

  // Phase 10G-7: Selected target info (soft-selected, no auto-target)
  const selectedTarget = (!hasAutoTarget && selectedTargetId) ? players[selectedTargetId] : null;
  const hasSelectedTarget = selectedTarget && selectedTarget.is_alive !== false;
  const selectedIsEnemy = hasSelectedTarget && activeUnit?.team && selectedTarget.team !== activeUnit.team;

  const hasCooldowns = rangedCooldown > 0;

  // Phase 10G-7: Determine status CSS class
  const statusClass = autoSkillId
    ? (targetStatus?.startsWith('Casting') ? 'status-casting' :
       targetStatus?.startsWith('Cooldown') ? 'status-cooldown' : 'status-pursuing')
    : (targetStatus === 'Attacking!' ? 'status-attacking' : 'status-pursuing');

  return (
    <div className="hud hud-slim">
      {/* Target frame — always rendered to prevent layout shift */}
      {hasAutoTarget ? (
        /* Phase 10E-2 / 10G-7: Auto-target frame — skill-aware */
        <div className={`hud-auto-target ${isHealSkill ? 'auto-target-heal' : ''}`}>
          <div className="hud-auto-target-header">
            <span className="hud-auto-target-icon">{isHealSkill ? '💚' : (autoSkillDef ? autoSkillDef.icon : '⚔')}</span>
            <span className="hud-auto-target-label">
              {autoSkillId ? `Skill: ${autoSkillDef?.name || autoSkillId}` : 'Targeting:'}
            </span>
          </div>
          <div className="hud-auto-target-name">{targetPlayer.username}</div>
          <div className="hud-auto-target-hp-bar">
            <div
              className={`hud-auto-target-hp-fill ${isHealSkill ? 'hp-fill-heal' : ''}`}
              style={{
                width: `${Math.max(0, ((targetPlayer.hp ?? 0) / (targetPlayer.max_hp ?? 100)) * 100)}%`,
              }}
            />
          </div>
          <div className="hud-auto-target-hp-text">
            {targetPlayer.hp ?? 0} / {targetPlayer.max_hp ?? 100}
          </div>
          <div className={`hud-auto-target-status ${statusClass}`}>
            {targetStatus}
          </div>
        </div>
      ) : hasSelectedTarget ? (
        /* Phase 10G-7: Selected target info pane (soft-selected, no auto-target) */
        <div className={`hud-selected-target ${selectedIsEnemy ? 'selected-enemy' : 'selected-ally'}`}>
          <div className="hud-selected-target-header">
            <span className="hud-selected-target-icon">{selectedIsEnemy ? '🎯' : '💚'}</span>
            <span className="hud-selected-target-label">Selected:</span>
          </div>
          <div className="hud-selected-target-name">{selectedTarget.username}</div>
          <div className="hud-selected-target-hp-bar">
            <div
              className={`hud-selected-target-hp-fill ${selectedIsEnemy ? '' : 'hp-fill-ally'}`}
              style={{
                width: `${Math.max(0, ((selectedTarget.hp ?? 0) / (selectedTarget.max_hp ?? 100)) * 100)}%`,
              }}
            />
          </div>
          <div className="hud-selected-target-hp-text">
            {selectedTarget.hp ?? 0} / {selectedTarget.max_hp ?? 100}
          </div>
        </div>
      ) : (
        /* Empty target placeholder — maintains layout stability */
        <div className="hud-selected-target hud-target-empty">
          <div className="hud-selected-target-header">
            <span className="hud-selected-target-icon">🎯</span>
            <span className="hud-selected-target-label">No Target</span>
          </div>
          <div className="hud-selected-target-name hud-target-muted">Click a unit to select</div>
        </div>
      )}

      {/* Cooldowns */}
      {rangedCooldown > 0 && (
        <div className="cooldown-display">
          <span className="cooldown-icon">🏹</span>
          <span className="cooldown-text">Ranged: {rangedCooldown} turn{rangedCooldown !== 1 ? 's' : ''}</span>
          <div className="cooldown-bar-bg">
            <div className="cooldown-bar-fill" style={{ width: `${(rangedCooldown / 3) * 100}%` }} />
          </div>
        </div>
      )}



    </div>
  );
}
