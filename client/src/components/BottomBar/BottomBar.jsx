import React, { useCallback, useMemo, useEffect, useState, useRef } from 'react';
import { useGameState, useGameDispatch, useCombatStats, useCombatStatsDispatch } from '../../context/GameStateContext';
import SkillIcon from './SkillIcon';
import SkillTooltip, { PotionTooltip } from './SkillTooltip';
import { loadSkillIconSheet, hasSkillSprite } from './SkillIconMap';
import { isInSkillRange } from '../../utils/skillUtils';

/**
 * BottomBar — Unified horizontal action + skill bar.
 * Phase 6E-4: Merges ActionBar + SkillBar into a single bottom bar.
 *
 * Sections (left to right):
 * 1. Skills: Class skill buttons with cooldown overlays + hotkey numbers (1-4)
 * 2. Potion: Always visible, hotkey 5
 * 3. Queue Info: Queue count, Undo, Clear buttons
 * 4. Leave: Leave match button
 *
 * Move, Attack, Interact, Loot, and Wait removed — all handled by smart right-click.
 * Keyboard hotkeys 1-4 trigger skills, 5 triggers potion.
 */
export default function BottomBar({ onAction, onLeave }) {
  const {
    actionMode, actionQueue, playerId, players, isDungeon,
    inventory, activeUnitId, selectedUnitIds, partyQueues, partyInventories,
    classSkills, allClassSkills, matchStatus,
    // Phase 10G-6: Selected target for target-first skill casting
    selectedTargetId,
    // Action Intent Banner: auto-target pursuit state
    autoTargetId, autoSkillId,
    // QoL: FOV-filtered visible tiles for auto-select nearest target
    visibleTiles,
  } = useGameState();
  const dispatch = useGameDispatch();

  // Active unit: either the controlled party member or the player themselves
  const effectiveUnitId = activeUnitId || playerId;
  const isControllingAlly = activeUnitId && activeUnitId !== playerId;
  const myPlayer = players[effectiveUnitId];
  const isAlive = myPlayer?.is_alive !== false;
  const myTeam = myPlayer?.team || 'a';
  const isDead = !isAlive;

  // Use party queue when controlling an ally, otherwise use player queue
  const currentQueue = isControllingAlly ? (partyQueues[activeUnitId] || []) : actionQueue;
  const queueLength = currentQueue?.length || 0;
  const queueFull = queueLength >= 10;

  // Effective inventory: use party member's inventory if controlling one
  const effectiveInventory = isControllingAlly
    ? (partyInventories[activeUnitId]?.inventory || [])
    : inventory;

  // Count health potions in effective inventory
  const healthPotionIndex = effectiveInventory?.findIndex?.(i =>
    i && i.item_type === 'consumable' && i.consumable_effect?.type === 'heal'
  ) ?? -1;
  const hasPotions = healthPotionIndex >= 0;
  const potionCount = effectiveInventory?.filter?.(i =>
    i && i.item_type === 'consumable' && i.consumable_effect?.type === 'heal'
  )?.length || 0;

  // ---------- Skills for current unit ----------
  const activeUnit = players[effectiveUnitId];

  // Helper: find a skill definition by ID across all known skill sources
  const findSkillDef = useCallback((skillId) => {
    if (!skillId) return null;
    if (classSkills) {
      const found = classSkills.find(s => s.skill_id === skillId);
      if (found) return found;
    }
    if (allClassSkills) {
      for (const skills of Object.values(allClassSkills)) {
        const found = skills.find(s => s.skill_id === skillId);
        if (found) return found;
      }
    }
    return null;
  }, [classSkills, allClassSkills]);

  const skills = useMemo(() => {
    if (!activeUnit) return classSkills || [];
    const unitClassId = activeUnit.class_id;
    if (!unitClassId) return [];
    if (!isControllingAlly) return classSkills || [];
    return allClassSkills[unitClassId] || [];
  }, [activeUnit, classSkills, allClassSkills, isControllingAlly]);

  // ---------- Helpers ----------

  /**
   * QoL: Find the nearest valid target for a skill when no target is pre-selected.
   * For enemy-targeting skills → nearest visible alive enemy.
   * For ally-targeting skills → nearest injured alive ally (or self if injured).
   * Mirrors the Tab-targeting sort (Euclidean distance, stable id tiebreaker).
   * Returns the target unit's ID, or null if none found.
   */
  const findNearestTarget = useCallback((skill) => {
    if (!activeUnit?.position) return null;

    const isAllySkill = skill.targeting === 'ally_or_self';
    const isEnemySkill = skill.targeting === 'enemy_adjacent' || skill.targeting === 'enemy_ranged' || skill.targeting === 'ground_aoe';
    if (!isAllySkill && !isEnemySkill) return null;

    let bestId = null;
    let bestDist = Infinity;

    for (const [id, unit] of Object.entries(players)) {
      if (!unit || unit.is_alive === false || !unit.position) continue;

      if (isEnemySkill) {
        // Must be an enemy
        if (unit.team === myTeam) continue;
      } else {
        // ally_or_self — must be on same team (includes self)
        if (unit.team !== myTeam) continue;
        // For heals, prefer injured allies — skip full-HP units
        if (unit.hp >= unit.max_hp) continue;
      }

      // FOV filter: only consider units on visible tiles
      if (visibleTiles) {
        const tileKey = `${unit.position.x},${unit.position.y}`;
        if (!visibleTiles.has(tileKey)) continue;
      }

      const dx = unit.position.x - activeUnit.position.x;
      const dy = unit.position.y - activeUnit.position.y;
      const dist = Math.sqrt(dx * dx + dy * dy);

      if (dist < bestDist || (dist === bestDist && id < bestId)) {
        bestDist = dist;
        bestId = id;
      }
    }

    // For ally heals: if no injured ally found, allow self-targeting if self is injured
    if (isAllySkill && !bestId) {
      if (activeUnit.hp < activeUnit.max_hp) {
        bestId = effectiveUnitId;
      }
    }

    return bestId;
  }, [activeUnit, players, myTeam, visibleTiles, effectiveUnitId]);

  // ---------- Action Handlers ----------

  const handleClearQueue = () => {
    if (isDead) return;
    const msg = { type: 'clear_queue' };
    if (isControllingAlly) msg.unit_id = activeUnitId;
    onAction(msg);
    dispatch({ type: 'QUEUE_CLEARED', payload: { unit_id: isControllingAlly ? activeUnitId : null } });
  };

  const handleRemoveLast = () => {
    if (isDead || queueLength === 0) return;
    const msg = { type: 'remove_last' };
    if (isControllingAlly) msg.unit_id = activeUnitId;
    onAction(msg);
  };

  const handleUsePotion = useCallback(() => {
    if (isDead || queueFull || !hasPotions) return;
    const msg = { type: 'action', action_type: 'use_item', target_x: healthPotionIndex };
    if (isControllingAlly) msg.unit_id = activeUnitId;
    onAction(msg);
  }, [isDead, queueFull, hasPotions, healthPotionIndex, isControllingAlly, activeUnitId, onAction]);

  const handleSkillClick = useCallback((skill) => {
    if (isDead || queueFull) return;

    // Check cooldown — BUT don't block for auto-target (player can approach while cooling)
    const cooldown = activeUnit?.cooldowns?.[skill.skill_id] || 0;

    // Find the class's auto-attack skill for fallback pursuit.
    // When casting a spell, auto-target should keep using the auto-attack skill
    // (not the spell) so auto-attacks resume between spell cooldowns.
    const autoAttackSkill = skills.find(s => s.is_auto_attack);
    const autoAttackSkillId = autoAttackSkill?.skill_id || null;

    const skillMode = `skill_${skill.skill_id}`;

    // Self-targeting skills auto-queue immediately (unchanged)
    if (skill.targeting === 'self') {
      if (cooldown > 0) return;  // Self skills need to be off cooldown
      const msg = {
        type: 'action',
        action_type: 'skill',
        skill_id: skill.skill_id,
        target_x: activeUnit.position.x,
        target_y: activeUnit.position.y,
        target_id: activeUnit.player_id || effectiveUnitId,
      };
      if (isControllingAlly) msg.unit_id = activeUnitId;
      onAction(msg);
      if (actionMode) {
        dispatch({ type: 'SET_ACTION_MODE', payload: null });
      }
      return;
    }

    // --- Phase 10G-6: Target-first skill casting ---
    if (selectedTargetId) {
      const targetUnit = players[selectedTargetId];
      if (targetUnit && targetUnit.is_alive !== false) {
        // Validate targeting compatibility
        const isEnemy = targetUnit.team !== myTeam;
        const isAlly = targetUnit.team === myTeam;
        const validTarget =
          (skill.targeting === 'enemy_adjacent' && isEnemy) ||
          (skill.targeting === 'enemy_ranged' && isEnemy) ||
          (skill.targeting === 'ground_aoe' && isEnemy) ||
          (skill.targeting === 'ally_or_self' && (isAlly || selectedTargetId === effectiveUnitId));

        if (validTarget) {
          // Check if already in range
          const inRange = isInSkillRange(activeUnit, targetUnit, skill);

          if (inRange && cooldown === 0) {
            // In range + off cooldown → cast immediately
            const msg = {
              type: 'action',
              action_type: 'skill',
              skill_id: skill.skill_id,
              target_x: targetUnit.position.x,
              target_y: targetUnit.position.y,
              target_id: selectedTargetId,
            };
            if (isControllingAlly) msg.unit_id = activeUnitId;
            onAction(msg);
          }
          // Always set auto-target so pursuit persists each round.
          // Use the class auto-attack skill (not the spell) so auto-attacks
          // resume between spell cooldowns instead of WAITing.
          {
            const atMsg = {
              type: 'set_auto_target',
              target_id: selectedTargetId,
              skill_id: autoAttackSkillId,
            };
            if (isControllingAlly) atMsg.unit_id = activeUnitId;
            onAction(atMsg);
          }
          return;  // Don't enter targeting mode — we handled it
        }
      }
    }

    // --- QoL: Auto-select nearest target when no target is pre-selected ---
    // Instead of dropping into targeting mode (click-to-select), automatically
    // find the nearest valid target and treat it as if the player Tab-targeted first.
    const autoSelectedId = findNearestTarget(skill);
    if (autoSelectedId) {
      const targetUnit = players[autoSelectedId];
      if (targetUnit && targetUnit.is_alive !== false) {
        // Update the UI: show who we auto-selected in the HUD
        dispatch({ type: 'SELECT_TARGET', payload: { targetId: autoSelectedId } });

        // Check if already in range
        const inRange = isInSkillRange(activeUnit, targetUnit, skill);

        if (inRange && cooldown === 0) {
          // In range + off cooldown → cast immediately
          const msg = {
            type: 'action',
            action_type: 'skill',
            skill_id: skill.skill_id,
            target_x: targetUnit.position.x,
            target_y: targetUnit.position.y,
            target_id: autoSelectedId,
          };
          if (isControllingAlly) msg.unit_id = activeUnitId;
          onAction(msg);
        }
        // Always set auto-target so pursuit persists each round.
        // Use the class auto-attack skill (not the spell) so auto-attacks
        // resume between spell cooldowns instead of WAITing.
        {
          const atMsg = {
            type: 'set_auto_target',
            target_id: autoSelectedId,
            skill_id: autoAttackSkillId,
          };
          if (isControllingAlly) atMsg.unit_id = activeUnitId;
          onAction(atMsg);
        }
        return;  // Handled — skip targeting mode
      }
    }

    // --- No valid target found anywhere → fall back to targeting mode ---
    if (cooldown > 0) return;  // Can't enter targeting mode if on cooldown
    if (actionMode === skillMode) {
      dispatch({ type: 'SET_ACTION_MODE', payload: null });
    } else {
      dispatch({ type: 'SET_ACTION_MODE', payload: skillMode });
    }
  }, [isDead, queueFull, activeUnit, actionMode, dispatch, onAction,
      isControllingAlly, activeUnitId, selectedTargetId, players, myTeam, effectiveUnitId,
      findNearestTarget]);

  // ---------- Keyboard Hotkeys for Skills (1-5) ----------
  useEffect(() => {
    const handleKeyDown = (e) => {
      // Ignore if typing in an input/textarea
      if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;
      if (!skills || skills.length === 0) return;

      const keyNum = parseInt(e.key, 10);
      if (isNaN(keyNum) || keyNum < 1) return;
      // Potion is always the slot after the last skill
      const potionKey = skills.length + 1;
      if (keyNum === potionKey) {
        e.preventDefault();
        handleUsePotion();
        return;
      }
      if (keyNum >= 1 && keyNum <= skills.length) {
        e.preventDefault();
        const skill = skills[keyNum - 1];
        if (skill) handleSkillClick(skill);
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [skills, handleSkillClick, handleUsePotion]);

  // ---------- Combat Meter toggle ----------
  const combatStats = useCombatStats();
  const statsDispatch = useCombatStatsDispatch();
  const meterVisible = combatStats.visible;

  const handleMeterToggle = useCallback(() => {
    statsDispatch({ type: 'COMBAT_STATS_TOGGLE' });
  }, [statsDispatch]);

  // ---------- Load skill icon sheet on mount ----------
  useEffect(() => {
    loadSkillIconSheet().catch(() => {});
  }, []);

  // ---------- Action Intent Banner: Compute current intent ----------
  const intentInfo = useMemo(() => {
    if (isDead) {
      return { text: 'You have been eliminated', icon: '💀', className: 'intent-dead' };
    }

    // 1. Skill targeting mode active (player clicked a skill, waiting to pick target)
    if (actionMode?.startsWith('skill_')) {
      const skillId = actionMode.replace('skill_', '');
      const skill = findSkillDef(skillId);
      const hint = skill?.targeting === 'ally_or_self' ? 'click an ally or self'
                 : skill?.targeting === 'enemy_adjacent' ? 'click an adjacent enemy'
                 : skill?.targeting === 'enemy_ranged' ? 'click an enemy in range'
                 : skill?.targeting === 'ground_aoe' ? 'click a tile to target area'
                 : 'click a target';
      return { text: `Targeting: ${skill?.name || skillId} — ${hint}`, icon: '🎯', skillId: skillId, className: 'intent-targeting', cancellable: true };
    }

    // 2. Auto-target pursuit active (persistent chase/attack)
    if (autoTargetId) {
      const target = players[autoTargetId];
      if (target && target.is_alive !== false) {
        const targetName = target.username || 'Unknown';
        if (autoSkillId) {
          const skill = findSkillDef(autoSkillId);
          const isHeal = skill?.targeting === 'ally_or_self';
          if (isHeal) {
            const inRange = activeUnit ? isInSkillRange(activeUnit, target, skill) : false;
            return inRange
              ? { text: `Healing: ${skill.name} → ${targetName}`, icon: '💚', skillId: autoSkillId, className: 'intent-healing', cancellable: true }
              : { text: `Approaching ${targetName} — ${skill.name} ready`, icon: '💚', skillId: autoSkillId, className: 'intent-heal-pursuing', cancellable: true };
          }
          const inRange = activeUnit ? isInSkillRange(activeUnit, target, skill) : false;
          const cdRemaining = activeUnit?.cooldowns?.[autoSkillId] || 0;
          if (inRange && cdRemaining === 0) {
            return { text: `Casting: ${skill?.name} → ${targetName}`, icon: '⚔', skillId: autoSkillId, className: 'intent-casting', cancellable: true };
          } else if (inRange && cdRemaining > 0) {
            return { text: `Cooldown (${cdRemaining}) — ${skill?.name} → ${targetName}`, icon: '⏳', skillId: autoSkillId, className: 'intent-cooldown', cancellable: true };
          }
          return { text: `Pursuing: ${targetName} — ${skill?.name} ready`, icon: '🏃', skillId: autoSkillId, className: 'intent-pursuing', cancellable: true };
        }
        // Melee auto-attack (no skill)
        if (activeUnit?.position && target.position) {
          const dx = Math.abs(activeUnit.position.x - target.position.x);
          const dy = Math.abs(activeUnit.position.y - target.position.y);
          const adjacent = dx <= 1 && dy <= 1 && (dx + dy > 0);
          if (adjacent) {
            return { text: `Attacking: ${targetName}`, icon: '⚔', skillId: 'auto_attack_melee', className: 'intent-attacking', cancellable: true };
          }
        }
        return { text: `Pursuing: ${targetName}`, icon: '🏃', skillId: 'auto_attack_melee', className: 'intent-pursuing', cancellable: true };
      }
    }

    // 3. Queue has actions — describe the first queued action
    if (queueLength > 0 && currentQueue.length > 0) {
      const first = currentQueue[0];
      const moveCount = currentQueue.filter(a => a.action_type === 'move').length;
      const nonMoveFirst = currentQueue.find(a => a.action_type !== 'move');

      // If mixed queue (moves then combat), describe the combat goal
      if (nonMoveFirst && moveCount > 0) {
        switch (nonMoveFirst.action_type) {
          case 'attack': {
            const t = nonMoveFirst.target_id ? players[nonMoveFirst.target_id] : null;
            return { text: `Moving to attack ${t?.username || 'target'} (${moveCount} steps)`, icon: '⚔', skillId: 'auto_attack_melee', className: 'intent-attack-queued' };
          }
          case 'ranged_attack': {
            const t = nonMoveFirst.target_id ? players[nonMoveFirst.target_id] : null;
            return { text: `Moving to shoot ${t?.username || 'target'} (${moveCount} steps)`, icon: '🏹', skillId: 'auto_attack_ranged', className: 'intent-attack-queued' };
          }
          case 'skill': {
            const sk = findSkillDef(nonMoveFirst.skill_id);
            const t = nonMoveFirst.target_id ? players[nonMoveFirst.target_id] : null;
            return { text: `Moving to cast ${sk?.name || 'skill'} → ${t?.username || 'target'}`, icon: '✦', skillId: nonMoveFirst.skill_id, className: 'intent-skill-queued' };
          }
          case 'interact':
            return { text: `Moving to interact (${moveCount} steps)`, icon: '🚪', className: 'intent-interact-queued' };
          default:
            break;
        }
      }

      // Pure move queue
      if (first.action_type === 'move') {
        const lastMove = [...currentQueue].reverse().find(a => a.action_type === 'move');
        return { text: `Moving to (${lastMove.target_x}, ${lastMove.target_y}) — ${moveCount} step${moveCount !== 1 ? 's' : ''}`, icon: '🦶', className: 'intent-moving' };
      }

      // Single action types
      switch (first.action_type) {
        case 'attack': {
          const t = first.target_id ? players[first.target_id] : null;
          return { text: `Queued: Attack → ${t?.username || 'target'}`, icon: '⚔', skillId: 'auto_attack_melee', className: 'intent-attack-queued' };
        }
        case 'ranged_attack': {
          const t = first.target_id ? players[first.target_id] : null;
          return { text: `Queued: Ranged Attack → ${t?.username || 'target'}`, icon: '🏹', skillId: 'auto_attack_ranged', className: 'intent-attack-queued' };
        }
        case 'skill': {
          const sk = findSkillDef(first.skill_id);
          const t = first.target_id ? players[first.target_id] : null;
          return { text: `Queued: ${sk?.name || 'Skill'} → ${t?.username || 'target'}`, icon: '✦', skillId: first.skill_id, className: 'intent-skill-queued' };
        }
        case 'use_item':
          return { text: 'Queued: Use Potion', icon: '🧪', skillId: 'potion', className: 'intent-item-queued' };
        case 'interact':
          return { text: `Queued: Interact at (${first.target_x}, ${first.target_y})`, icon: '🚪', className: 'intent-interact-queued' };
        default:
          return { text: `Queued: ${queueLength} action${queueLength !== 1 ? 's' : ''}`, icon: '📋', className: 'intent-queued' };
      }
    }

    // 4. Selected target but no action yet
    if (selectedTargetId) {
      const target = players[selectedTargetId];
      if (target && target.is_alive !== false) {
        const isEnemy = target.team !== myTeam;
        return {
          text: `Selected: ${target.username}${isEnemy ? ' (enemy)' : ' (ally)'}`,
          icon: isEnemy ? '🎯' : '💚',
          className: isEnemy ? 'intent-target-enemy' : 'intent-target-ally',
        };
      }
    }

    // 5. Idle
    return { text: 'Awaiting orders', icon: '—', className: 'intent-idle' };
  }, [isDead, actionMode, autoTargetId, autoSkillId, queueLength, currentQueue,
      selectedTargetId, players, activeUnit, myTeam, findSkillDef]);

  // ---------- Tooltip hover state ----------
  const [hoveredSkillId, setHoveredSkillId] = useState(null);
  const [hoveredPotion, setHoveredPotion] = useState(false);
  const tooltipTimerRef = useRef(null);

  const handleSlotMouseEnter = useCallback((skillId) => {
    clearTimeout(tooltipTimerRef.current);
    tooltipTimerRef.current = setTimeout(() => {
      setHoveredSkillId(skillId);
      setHoveredPotion(false);
    }, 200);
  }, []);

  const handleSlotMouseLeave = useCallback(() => {
    clearTimeout(tooltipTimerRef.current);
    setHoveredSkillId(null);
    setHoveredPotion(false);
  }, []);

  const handlePotionMouseEnter = useCallback(() => {
    clearTimeout(tooltipTimerRef.current);
    tooltipTimerRef.current = setTimeout(() => {
      setHoveredPotion(true);
      setHoveredSkillId(null);
    }, 200);
  }, []);

  // Cleanup timer on unmount
  useEffect(() => {
    return () => clearTimeout(tooltipTimerRef.current);
  }, []);

  // Ref callback: clamp tooltip so it never overflows viewport edges
  const clampTooltipRef = useCallback((el) => {
    if (!el) return;
    // Reset any previous adjustment so we measure the natural position
    el.style.left = '50%';
    el.style.transform = 'translateX(-50%)';
    const rect = el.getBoundingClientRect();
    const pad = 8; // min px from screen edge
    if (rect.left < pad) {
      // Overflowing left — pin to left edge
      el.style.left = '0';
      el.style.transform = `translateX(${pad - rect.left}px)`;
    } else if (rect.right > window.innerWidth - pad) {
      // Overflowing right — shift left
      el.style.left = '0';
      el.style.transform = `translateX(${window.innerWidth - pad - rect.width}px)`;
    }
  }, []);

  // Find potion item for tooltip info
  const potionItem = useMemo(() => {
    return effectiveInventory?.find?.(i =>
      i && i.item_type === 'consumable' && i.consumable_effect?.type === 'heal'
    ) || null;
  }, [effectiveInventory]);

  return (
    <div className="bottom-bar">
      {/* ---- Left: Action Slots (Skills + Core Actions) ---- */}
      <div className="action-slots">
        {/* Skills rendered as icon-centric square buttons */}
        {skills && skills.length > 0 && skills.map((skill, index) => {
          const cooldown = activeUnit?.cooldowns?.[skill.skill_id] || 0;
          const isOnCooldown = cooldown > 0;
          const isActive = actionMode === `skill_${skill.skill_id}`;
          const isAutoAttack = skill.is_auto_attack;
          const canAutoTarget = selectedTargetId && skill.targeting !== 'self' && skill.targeting !== 'empty_tile';
          const isDisabled = isDead || queueFull || (isOnCooldown && !canAutoTarget && !isAutoAttack);

          return (
            <div
              key={skill.skill_id}
              className="action-slot-wrapper"
              onMouseEnter={() => handleSlotMouseEnter(skill.skill_id)}
              onMouseLeave={handleSlotMouseLeave}
            >
              <button
                className={
                  `action-slot` +
                  `${isActive ? ' active' : ''}` +
                  `${isOnCooldown ? ' on-cooldown' : ''}` +
                  `${isAutoAttack ? ' slot-auto-attack' : ''}` +
                  `${isDisabled ? ' disabled' : ''}`
                }
                onClick={() => handleSkillClick(skill)}
                disabled={isDisabled}
              >
                {/* Hotkey badge — top-left */}
                <span className="slot-hotkey">{index + 1}</span>

                {/* Icon — large, center */}
                <div className="slot-icon">
                  <SkillIcon skillId={skill.skill_id} size={40} emoji={skill.icon} />
                </div>

                {/* Skill name — bottom label */}
                <span className="slot-label">{skill.name}</span>

                {/* Cooldown overlay */}
                {isOnCooldown && !isAutoAttack && (
                  <div className="slot-cooldown-overlay">
                    <span className="slot-cooldown-number">{cooldown}</span>
                  </div>
                )}
              </button>

              {/* Skill Tooltip */}
              {hoveredSkillId === skill.skill_id && (
                <div className="skill-tooltip-anchor" ref={clampTooltipRef}>
                  <SkillTooltip
                    skill={skill}
                    hotkey={String(index + 1)}
                    cooldown={cooldown}
                    isAutoAttack={isAutoAttack}
                    attackerStats={{
                      attack_damage: activeUnit?.attack_damage || 0,
                      ranged_damage: activeUnit?.ranged_damage || 0,
                    }}
                  />
                </div>
              )}
            </div>
          );
        })}

        {/* Potion slot (always visible, hotkey 5) */}
        <div
          className="action-slot-wrapper"
          onMouseEnter={handlePotionMouseEnter}
          onMouseLeave={handleSlotMouseLeave}
        >
          <button
            className={`action-slot slot-potion ${!hasPotions ? 'disabled' : ''}`}
            onClick={handleUsePotion}
            disabled={isDead || queueFull || !hasPotions}
          >
            <span className="slot-hotkey">{(skills?.length || 0) + 1}</span>
            <span className="slot-icon">
              <SkillIcon skillId="potion" size={40} emoji="🧪" />
            </span>
            <span className="slot-label">Potion</span>
            {potionCount > 0 && (
              <span className="slot-count">{potionCount}</span>
            )}
          </button>

          {/* Potion Tooltip */}
          {hoveredPotion && (
            <div className="skill-tooltip-anchor" ref={clampTooltipRef}>
              <PotionTooltip
                potion={potionItem}
                potionCount={potionCount}
                hotkey={String((skills?.length || 0) + 1)}
              />
            </div>
          )}
        </div>
      </div>

      {/* ---- Action Intent Banner (centered) ---- */}
      <div
        className={`action-intent-banner ${intentInfo.className}${intentInfo.cancellable ? ' intent-clickable' : ''}`}
        onClick={intentInfo.cancellable ? () => {
          // Click-to-cancel: exit targeting mode or clear auto-target
          if (actionMode?.startsWith('skill_')) {
            dispatch({ type: 'SET_ACTION_MODE', payload: null });
          } else if (autoTargetId) {
            onAction({ type: 'set_auto_target', target_id: null });
          }
        } : undefined}
        title={intentInfo.cancellable ? 'Click to cancel' : undefined}
      >
        <span className="intent-icon">
          {intentInfo.skillId && hasSkillSprite(intentInfo.skillId)
            ? <SkillIcon skillId={intentInfo.skillId} size={24} emoji={intentInfo.icon} />
            : intentInfo.icon}
        </span>
        <span className="intent-text">{intentInfo.text}</span>
        {queueLength > 1 && !isDead && (
          <span className="intent-queue-count">{queueLength} queued</span>
        )}
      </div>

      {/* ---- Combat Meter Toggle ---- */}
      <div className="bar-meter-toggle">
        <button
          className={`btn-bar btn-meter${meterVisible ? ' active' : ''}`}
          onClick={handleMeterToggle}
          title="Combat Meter"
        >
          <span className="meter-icon">⚔</span>
        </button>
      </div>

      {/* ---- Right: Queue + Controls ---- */}
      <div className="bar-controls">
        <div className="bar-queue-info">
          {isControllingAlly && <span className="controlling-badge">{myPlayer?.username || 'Ally'}</span>}
          {selectedUnitIds.length > 1 && <span className="multi-select-badge" title={`${selectedUnitIds.length} units selected`}>⬡{selectedUnitIds.length}</span>}
          <span className="bar-queue-count" title="Actions queued">
            Q: {queueLength}/10
          </span>
          {queueLength > 0 && (
            <span className="bar-queue-actions">
              {queueLength} action{queueLength !== 1 ? 's' : ''}
            </span>
          )}
        </div>
        <div className="bar-queue-buttons">
          <button
            className="btn-bar btn-undo"
            onClick={handleRemoveLast}
            disabled={isDead || queueLength === 0}
            title="Remove last action (Undo)"
          >
            ↩
          </button>
          <button
            className="btn-bar btn-clear-queue"
            onClick={handleClearQueue}
            disabled={isDead || queueLength === 0}
            title="Clear all queued actions"
          >
            ✕
          </button>
          <button className="btn-bar btn-leave" onClick={onLeave} title="Leave match">
            ✖
          </button>
        </div>
      </div>

      {/* Death status */}
      {isDead && (
        <div className="bottom-bar-hint">
          <span className="dead-message">💀 You have been eliminated</span>
        </div>
      )}

    </div>
  );
}


