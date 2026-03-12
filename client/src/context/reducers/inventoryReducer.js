/**
 * Inventory sub-reducer — handles in-match inventory & equipment operations.
 *
 * Action types handled:
 *   ITEM_EQUIPPED, ITEM_UNEQUIPPED, ITEM_TRANSFERRED, PARTY_INVENTORY
 */

export function inventoryReducer(state, action) {
  switch (action.type) {
    case 'ITEM_EQUIPPED': {
      const eqUnitId = action.payload.player_id;
      const isPartyMember = eqUnitId && eqUnitId !== state.playerId;
      if (isPartyMember) {
        return {
          ...state,
          partyInventories: {
            ...state.partyInventories,
            [eqUnitId]: {
              inventory: action.payload.inventory ?? state.partyInventories[eqUnitId]?.inventory ?? [],
              equipment: action.payload.equipment ?? state.partyInventories[eqUnitId]?.equipment ?? {},
            },
          },
        };
      }
      return {
        ...state,
        inventory: action.payload.inventory ?? state.inventory,
        equipment: action.payload.equipment ?? state.equipment,
      };
    }

    case 'ITEM_UNEQUIPPED': {
      const unUnitId = action.payload.player_id;
      const isPartyMemberUn = unUnitId && unUnitId !== state.playerId;
      if (isPartyMemberUn) {
        return {
          ...state,
          partyInventories: {
            ...state.partyInventories,
            [unUnitId]: {
              inventory: action.payload.inventory ?? state.partyInventories[unUnitId]?.inventory ?? [],
              equipment: action.payload.equipment ?? state.partyInventories[unUnitId]?.equipment ?? {},
            },
          },
        };
      }
      return {
        ...state,
        inventory: action.payload.inventory ?? state.inventory,
        equipment: action.payload.equipment ?? state.equipment,
      };
    }

    case 'ITEM_TRANSFERRED': {
      const { from_unit_id: xFrom, to_unit_id: xTo, from_inventory: xFromInv, to_inventory: xToInv,
              from_equipment: xFromEquip, to_equipment: xToEquip } = action.payload;
      const updatedPartyInvs = { ...state.partyInventories };
      let newInv = state.inventory;
      let newEquip = state.equipment;
      // Update source
      if (xFrom === state.playerId) {
        newInv = xFromInv;
        newEquip = xFromEquip || state.equipment;
      } else {
        updatedPartyInvs[xFrom] = { inventory: xFromInv, equipment: xFromEquip || updatedPartyInvs[xFrom]?.equipment || {} };
      }
      // Update destination
      if (xTo === state.playerId) {
        newInv = xToInv;
        newEquip = xToEquip || state.equipment;
      } else {
        updatedPartyInvs[xTo] = { inventory: xToInv, equipment: xToEquip || updatedPartyInvs[xTo]?.equipment || {} };
      }
      return {
        ...state,
        inventory: newInv,
        equipment: newEquip,
        partyInventories: updatedPartyInvs,
      };
    }

    case 'PARTY_INVENTORY':
      return {
        ...state,
        partyInventories: {
          ...state.partyInventories,
          [action.payload.unit_id]: {
            inventory: action.payload.inventory,
            equipment: action.payload.equipment || { weapon: null, armor: null, accessory: null },
          },
        },
      };

    default:
      return state;
  }
}
