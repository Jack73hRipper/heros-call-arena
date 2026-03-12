import React, { useCallback, useEffect } from 'react';
import { useGameState } from '../../context/GameStateContext';
import { useCombatStats, useCombatStatsDispatch } from '../../context/GameStateContext';
import DamageDoneView from './DamageDoneView';
import DamageTakenView from './DamageTakenView';
import HealingDoneView from './HealingDoneView';
import KillsView from './KillsView';
import OverviewView from './OverviewView';
import SkillBreakdownView from './SkillBreakdownView';

const VIEW_OPTIONS = [
  { id: 'damage_done', label: 'Damage Done' },
  { id: 'damage_taken', label: 'Damage Taken' },
  { id: 'healing_done', label: 'Healing Done' },
  { id: 'kills', label: 'Kills' },
  { id: 'overview', label: 'Overview' },
];

/**
 * CombatMeter — Toggleable combat statistics panel.
 * Drops down from the action bar area. Contains a view selector dropdown
 * and renders the active stat view.
 *
 * Click any player row to drill into their per-skill breakdown.
 * Press Escape or click Back to return to the list view.
 *
 * Hotkey: Tab or M to toggle.
 */
export default function CombatMeter() {
  const { playerId, currentTurn } = useGameState();
  const combatStats = useCombatStats();
  const statsDispatch = useCombatStatsDispatch();

  const { unitStats, activeView, visible, selectedUnit } = combatStats;

  const handleViewChange = useCallback((e) => {
    statsDispatch({ type: 'COMBAT_STATS_SET_VIEW', payload: e.target.value });
  }, [statsDispatch]);

  const handleClose = useCallback(() => {
    statsDispatch({ type: 'COMBAT_STATS_TOGGLE' });
  }, [statsDispatch]);

  const handleSelectUnit = useCallback((unitId) => {
    statsDispatch({ type: 'COMBAT_STATS_SELECT_UNIT', payload: unitId });
  }, [statsDispatch]);

  const handleBack = useCallback(() => {
    statsDispatch({ type: 'COMBAT_STATS_SELECT_UNIT', payload: null });
  }, [statsDispatch]);

  // Escape key to go back from breakdown, or close panel
  useEffect(() => {
    if (!visible) return;
    const handleKey = (e) => {
      if (e.key === 'Escape') {
        if (selectedUnit) {
          handleBack();
        } else {
          handleClose();
        }
      } else if (e.key === 'Backspace' && selectedUnit) {
        // Only if not typing in an input
        if (e.target.tagName !== 'INPUT' && e.target.tagName !== 'TEXTAREA') {
          handleBack();
        }
      }
    };
    window.addEventListener('keydown', handleKey);
    return () => window.removeEventListener('keydown', handleKey);
  }, [visible, selectedUnit, handleBack, handleClose]);

  if (!visible) return null;

  // If a unit is selected, show their skill breakdown instead of the list view
  const selectedUnitData = selectedUnit ? unitStats[selectedUnit] : null;

  const renderView = () => {
    if (selectedUnitData) {
      return (
        <SkillBreakdownView
          unit={selectedUnitData}
          currentTurn={currentTurn}
          onBack={handleBack}
        />
      );
    }

    switch (activeView) {
      case 'damage_done':
        return <DamageDoneView unitStats={unitStats} playerId={playerId} currentTurn={currentTurn} onSelectUnit={handleSelectUnit} />;
      case 'damage_taken':
        return <DamageTakenView unitStats={unitStats} playerId={playerId} currentTurn={currentTurn} onSelectUnit={handleSelectUnit} />;
      case 'healing_done':
        return <HealingDoneView unitStats={unitStats} playerId={playerId} currentTurn={currentTurn} onSelectUnit={handleSelectUnit} />;
      case 'kills':
        return <KillsView unitStats={unitStats} playerId={playerId} onSelectUnit={handleSelectUnit} />;
      case 'overview':
        return <OverviewView unitStats={unitStats} playerId={playerId} currentTurn={currentTurn} onSelectUnit={handleSelectUnit} />;
      default:
        return <DamageDoneView unitStats={unitStats} playerId={playerId} currentTurn={currentTurn} onSelectUnit={handleSelectUnit} />;
    }
  };

  return (
    <div className="combat-meter-panel">
      {/* Header row with dropdown + close button */}
      <div className="combat-meter-header">
        <span className="combat-meter-icon" title="Combat Meter">⚔</span>
        <select
          className="combat-meter-select"
          value={activeView}
          onChange={handleViewChange}
        >
          {VIEW_OPTIONS.map(opt => (
            <option key={opt.id} value={opt.id}>{opt.label}</option>
          ))}
        </select>
        {selectedUnitData && (
          <span className="combat-meter-viewing">
            → {selectedUnitData.username}
          </span>
        )}
        <span className="combat-meter-turn">Turn {currentTurn}</span>
        <button className="combat-meter-close" onClick={handleClose} title="Close (Tab)">✕</button>
      </div>

      {/* Active view content */}
      <div className="combat-meter-body">
        {renderView()}
      </div>
    </div>
  );
}
