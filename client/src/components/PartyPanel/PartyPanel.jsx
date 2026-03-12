import React, { useCallback } from 'react';
import { useGameState, useGameDispatch } from '../../context/GameStateContext';

/**
 * PartyPanel — Displays controllable party members (hero allies).
 * Phase 7B-2: Supports multi-selection with shift-click toggle.
 * Phase 7C-3: Stance UI — per-unit stance toggles + group stance buttons.
 * Click a member to take control and issue commands as that unit.
 * Shift-click to add/remove from multi-selection.
 * "Select All" / "Deselect All" buttons for group management.
 * 6E-3: In solo mode (no party), shows the player's own unit as a read-only display.
 */

const STANCES = [
  { id: 'follow',     label: '⇢', title: 'Follow — stay near owner, regroup after combat', color: '#64c8ff' },
  { id: 'aggressive', label: '⚔', title: 'Aggressive — pursue and fight enemies, may roam far', color: '#ff4040' },
  { id: 'defensive',  label: '🛡', title: 'Defensive — stay close, only attack nearby enemies', color: '#508cff' },
  { id: 'hold',       label: '⚓', title: 'Hold Position — never move, attack in range only', color: '#c8c8c8' },
];

export default function PartyPanel({ sendAction }) {
  const { partyMembers, activeUnitId, selectedUnitIds, playerId, players, partyQueues, actionQueue } = useGameState();
  const dispatch = useGameDispatch();

  // Click = soft-target for healing/skills; Ctrl+Click = take control; Shift+Click = toggle multi-select
  const handleSelect = useCallback((unitId, shiftKey = false, ctrlKey = false) => {
    if (shiftKey) {
      // Shift-click: toggle multi-select (unchanged)
      const isCurrentlySelected = selectedUnitIds.includes(unitId);
      if (isCurrentlySelected) {
        sendAction({ type: 'release_party_member', unit_id: unitId });
      } else {
        sendAction({ type: 'select_party_member', unit_id: unitId });
      }
      dispatch({ type: 'TOGGLE_UNIT_SELECTION', payload: unitId });
    } else if (ctrlKey) {
      // Ctrl+Click: take control of this party member
      for (const selId of selectedUnitIds) {
        if (selId !== playerId && selId !== unitId) {
          sendAction({ type: 'release_party_member', unit_id: selId });
        }
      }
      if (activeUnitId === unitId) {
        // Already the primary — release to self
        sendAction({ type: 'release_party_member', unit_id: unitId });
        dispatch({ type: 'SELECT_ACTIVE_UNIT', payload: null });
      } else {
        sendAction({ type: 'select_party_member', unit_id: unitId });
      }
    } else {
      // Plain click: soft-select as target (for healing, auto-target skills, etc.)
      dispatch({ type: 'SELECT_TARGET', payload: { targetId: unitId } });
    }
  }, [activeUnitId, selectedUnitIds, sendAction, dispatch, playerId]);

  const handleReturnToSelf = useCallback(() => {
    // Release all selected party members
    for (const selId of selectedUnitIds) {
      if (selId !== playerId) {
        sendAction({ type: 'release_party_member', unit_id: selId });
      }
    }
    dispatch({ type: 'DESELECT_ALL_UNITS' });
  }, [selectedUnitIds, playerId, sendAction, dispatch]);

  // Phase 7B-2: Select All alive party members + self
  const handleSelectAll = useCallback(() => {
    sendAction({ type: 'select_all_party' });
    dispatch({ type: 'SELECT_ALL_PARTY' });
  }, [sendAction, dispatch]);

  // Phase 7B-2: Deselect all
  const handleDeselectAll = useCallback(() => {
    sendAction({ type: 'release_all_party' });
    dispatch({ type: 'DESELECT_ALL_UNITS' });
  }, [sendAction, dispatch]);

  // Phase 7C-3: Set stance for a single unit
  const handleSetStance = useCallback((unitId, stance) => {
    sendAction({ type: 'set_stance', unit_id: unitId, stance });
  }, [sendAction]);

  // Phase 7C-3: Set stance for all party members
  const handleSetAllStances = useCallback((stance) => {
    sendAction({ type: 'set_all_stances', stance });
  }, [sendAction]);

  const hasParty = partyMembers && partyMembers.length > 0;

  // 6E-3: Solo mode — show self as a single read-only entry
  if (!hasParty) {
    const self = players[playerId];
    if (!self) return null;
    const hpPct = self.max_hp > 0 ? Math.max(0, self.hp / self.max_hp * 100) : 0;
    const queueLen = actionQueue?.length || 0;
    return (
      <div className="party-panel">
        <h3 className="party-panel-title">Party</h3>
        <div className="party-member-list">
          <div className="party-member party-member-selected">
            <div className="party-member-info">
              <span className="party-member-name">{self.username} (you)</span>
              <span className="party-member-class">{self.class_id || 'Hero'}</span>
            </div>
            <div className="party-member-hp-bar">
              <div
                className="party-member-hp-fill"
                style={{
                  width: `${hpPct}%`,
                  backgroundColor: hpPct > 50 ? '#4caf50' : hpPct > 25 ? '#ff9800' : '#f44336',
                }}
              />
            </div>
            <div className="party-member-status">
              <span className="party-member-hp-text">{self.hp}/{self.max_hp}</span>
              {queueLen > 0 && <span className="party-member-queue">Q:{queueLen}</span>}
            </div>
          </div>
        </div>
      </div>
    );
  }

  const anyPartySelected = selectedUnitIds.some(id => id !== playerId);
  const multiCount = selectedUnitIds.length;

  return (
    <div className="party-panel">
      <h3 className="party-panel-title">
        Party
        {multiCount > 1 && (
          <span className="party-multi-badge" title={`${multiCount} units selected`}>
            {multiCount} sel
          </span>
        )}
        {anyPartySelected && (
          <button className="btn-return-self" onClick={handleReturnToSelf} title="Return to your character (deselect all)">
            ↩ Self
          </button>
        )}
      </h3>

      {/* Phase 7B-2: Group selection buttons */}
      <div className="party-group-buttons">
        <span className="party-ctrl-hint" title="Left-click to target, Ctrl+Click to control">
          Click = Target · Ctrl = Control
        </span>
        <button
          className="btn-select-all"
          onClick={handleSelectAll}
          title="Select all alive party members (Ctrl+A)"
        >
          ✦ Select All
        </button>
        <button
          className="btn-deselect-all"
          onClick={handleDeselectAll}
          disabled={selectedUnitIds.length === 0}
          title="Deselect all units"
        >
          ✕ Deselect
        </button>
      </div>

      {/* Phase 7C-3: Group stance buttons */}
      <div className="party-stance-group">
        {STANCES.map((s) => (
          <button
            key={s.id}
            className="btn-stance-group"
            style={{ color: s.color, borderColor: s.color + '55' }}
            onClick={() => handleSetAllStances(s.id)}
            title={`All ${s.id.charAt(0).toUpperCase() + s.id.slice(1)} (Ctrl+${STANCES.indexOf(s) + 1})`}
          >
            {s.label}
          </button>
        ))}
      </div>

      <div className="party-member-list">
        {partyMembers.map((member) => {
          const unit = players[member.unit_id];
          if (!unit) return null;

          const isSelected = selectedUnitIds.includes(member.unit_id);
          const isPrimary = activeUnitId === member.unit_id;
          const isAlive = unit.is_alive !== false;
          const hpPct = unit.max_hp > 0 ? Math.max(0, unit.hp / unit.max_hp * 100) : 0;
          const queueLen = partyQueues[member.unit_id]?.length || 0;
          const currentStance = member.ai_stance || 'follow';

          return (
            <div
              key={member.unit_id}
              className={`party-member ${isPrimary ? 'party-member-primary' : ''} ${isSelected && !isPrimary ? 'party-member-selected' : ''} ${!isAlive ? 'party-member-dead' : ''}`}
            >
              <button
                className="party-member-clickable"
                onClick={(e) => isAlive && handleSelect(member.unit_id, e.shiftKey, e.ctrlKey || e.metaKey)}
                disabled={!isAlive}
                title={
                  isPrimary ? 'Click to target | Ctrl+Click to release | Shift-click to toggle multi-select'
                  : isSelected ? 'Click to target | Shift-click to deselect | Ctrl+Click to make primary'
                  : `Click to target ${unit.username} | Ctrl+Click to control | Shift to add to selection`
                }
              >
                <div className="party-member-info">
                  <span className="party-member-name">{unit.username}</span>
                  <span className="party-member-class">{member.class_id || unit.class_id || 'Ally'}</span>
                </div>
                <div className="party-member-hp-bar">
                  <div
                    className="party-member-hp-fill"
                    style={{
                      width: `${hpPct}%`,
                      backgroundColor: hpPct > 50 ? '#4caf50' : hpPct > 25 ? '#ff9800' : '#f44336',
                    }}
                  />
                </div>
                <div className="party-member-status">
                  <span className="party-member-hp-text">{unit.hp}/{unit.max_hp}</span>
                  {queueLen > 0 && <span className="party-member-queue">Q:{queueLen}</span>}
                  {isPrimary && <span className="party-member-controlled">PRIMARY</span>}
                  {isSelected && !isPrimary && <span className="party-member-multi-sel">SEL</span>}
                  {isSelected && multiCount > 1 && queueLen > 0 && (
                    <span className="party-member-group-move" title="Moving as group">⇶</span>
                  )}
                </div>
              </button>
              {/* Phase 7C-3: Per-unit stance toggle buttons */}
              {isAlive && (
                <div className="party-member-stances">
                  {STANCES.map((s) => (
                    <button
                      key={s.id}
                      className={`btn-stance ${currentStance === s.id ? 'btn-stance-active' : ''}`}
                      style={{
                        color: currentStance === s.id ? s.color : undefined,
                        borderColor: currentStance === s.id ? s.color + '88' : undefined,
                        backgroundColor: currentStance === s.id ? s.color + '20' : undefined,
                      }}
                      onClick={(e) => { e.stopPropagation(); handleSetStance(member.unit_id, s.id); }}
                      title={s.title}
                    >
                      {s.label}
                    </button>
                  ))}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
