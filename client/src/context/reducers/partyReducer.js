/**
 * Party sub-reducer — handles party selection, control, stances, and auto-target.
 *
 * Action types handled:
 *   SELECT_ACTIVE_UNIT, TOGGLE_UNIT_SELECTION, SELECT_ALL_PARTY,
 *   DESELECT_ALL_UNITS, PARTY_MEMBER_SELECTED, PARTY_MEMBER_RELEASED,
 *   STANCE_UPDATED, ALL_STANCES_UPDATED,
 *   AUTO_TARGET_SET, AUTO_TARGET_CLEARED, CLEAR_AUTO_TARGET,
 *   SELECT_TARGET, CLEAR_SELECTED_TARGET
 */

export function partyReducer(state, action) {
  switch (action.type) {
    case 'SELECT_ACTIVE_UNIT':
      return {
        ...state,
        activeUnitId: action.payload,
        selectedUnitIds: action.payload ? [action.payload] : [],
        actionMode: null,
      };

    case 'TOGGLE_UNIT_SELECTION': {
      const toggleId = action.payload;
      const currentSelected = [...state.selectedUnitIds];
      const idx = currentSelected.indexOf(toggleId);
      if (idx >= 0) {
        currentSelected.splice(idx, 1);
        const newPrimary = currentSelected.length > 0 ? currentSelected[0] : null;
        return {
          ...state,
          selectedUnitIds: currentSelected,
          activeUnitId: newPrimary,
          actionMode: null,
        };
      } else {
        currentSelected.push(toggleId);
        return {
          ...state,
          selectedUnitIds: currentSelected,
          activeUnitId: toggleId,
          actionMode: null,
        };
      }
    }

    case 'SELECT_ALL_PARTY': {
      const allIds = [state.playerId];
      for (const m of (state.partyMembers || [])) {
        const unit = state.players[m.unit_id];
        if (unit && unit.is_alive !== false) {
          allIds.push(m.unit_id);
        }
      }
      return {
        ...state,
        selectedUnitIds: allIds,
        activeUnitId: state.playerId,
        actionMode: null,
      };
    }

    case 'DESELECT_ALL_UNITS':
      return {
        ...state,
        selectedUnitIds: [],
        activeUnitId: null,
        actionMode: null,
      };

    case 'PARTY_MEMBER_SELECTED': {
      const selUnitId = action.payload.unit_id;
      const newSelected = state.selectedUnitIds.includes(selUnitId)
        ? state.selectedUnitIds
        : [...state.selectedUnitIds, selUnitId];
      return {
        ...state,
        activeUnitId: selUnitId,
        selectedUnitIds: newSelected,
        partyMembers: action.payload.party || state.partyMembers,
        partyQueues: {
          ...state.partyQueues,
          [selUnitId]: action.payload.unit_queue || [],
        },
        partyInventories: {
          ...state.partyInventories,
          ...(action.payload.unit_inventory != null ? {
            [selUnitId]: {
              inventory: action.payload.unit_inventory,
              equipment: action.payload.unit_equipment || { weapon: null, armor: null, accessory: null },
            },
          } : {}),
        },
        actionMode: null,
      };
    }

    case 'PARTY_MEMBER_RELEASED': {
      const releasedId = action.payload.unit_id;
      const filteredIds = state.selectedUnitIds.filter(id => id !== releasedId);
      const newPrimary = releasedId === state.activeUnitId
        ? (filteredIds.length > 0 ? filteredIds[0] : null)
        : state.activeUnitId;
      return {
        ...state,
        activeUnitId: newPrimary,
        selectedUnitIds: filteredIds,
        partyMembers: action.payload.party || state.partyMembers,
      };
    }

    case 'STANCE_UPDATED': {
      return {
        ...state,
        partyMembers: action.payload.party || state.partyMembers,
      };
    }

    case 'ALL_STANCES_UPDATED': {
      return {
        ...state,
        partyMembers: action.payload.party || state.partyMembers,
      };
    }

    case 'AUTO_TARGET_SET': {
      const { unit_id: atSetUnitId, target_id: atTargetId, skill_id: atSkillId } = action.payload;
      if (atSetUnitId === state.playerId || !atSetUnitId) {
        return {
          ...state,
          autoTargetId: atTargetId,
          autoSkillId: atSkillId || null,
          // Preserve selectedTargetId so it can serve as fallback when auto-target clears
        };
      }
      return {
        ...state,
        partyAutoTargets: { ...state.partyAutoTargets, [atSetUnitId]: atTargetId },
        partyAutoSkills: { ...state.partyAutoSkills, [atSetUnitId]: atSkillId || null },
      };
    }

    case 'AUTO_TARGET_CLEARED': {
      const { unit_id: atClearUnitId } = action.payload;
      if (atClearUnitId === state.playerId || !atClearUnitId) {
        return { ...state, autoTargetId: null, autoSkillId: null };
      }
      const updatedPAT = { ...state.partyAutoTargets };
      const updatedPAS = { ...state.partyAutoSkills };
      delete updatedPAT[atClearUnitId];
      delete updatedPAS[atClearUnitId];
      return { ...state, partyAutoTargets: updatedPAT, partyAutoSkills: updatedPAS };
    }

    case 'CLEAR_AUTO_TARGET':
      return { ...state, autoTargetId: null, autoSkillId: null };

    case 'SELECT_TARGET':
      return { ...state, selectedTargetId: action.payload.targetId };

    case 'CLEAR_SELECTED_TARGET':
      return { ...state, selectedTargetId: null };

    default:
      return state;
  }
}
