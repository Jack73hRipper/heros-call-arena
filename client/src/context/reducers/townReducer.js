/**
 * Town sub-reducer — handles town hub, hero management, merchant, and match transitions.
 *
 * Action types handled:
 *   SET_PROFILE, SET_TAVERN, HIRE_HERO, SELECT_HERO,
 *   HERO_DIED, SET_POST_MATCH_SUMMARY, CLEAR_POST_MATCH,
 *   MERCHANT_BUY, MERCHANT_SELL,
 *   HERO_EQUIP, HERO_UNEQUIP, HERO_TRANSFER,
 *   BANK_DEPOSIT, BANK_WITHDRAW,
 *   DISMISS_HERO,
 *   LEAVE_MATCH
 */

import { initialState } from '../GameStateContext';

export function townReducer(state, action) {
  switch (action.type) {
    case 'SET_PROFILE':
      return {
        ...state,
        gold: action.payload.gold ?? state.gold,
        heroes: action.payload.heroes ?? state.heroes,
        bank: action.payload.bank ?? state.bank,
      };

    case 'SET_TAVERN':
      return {
        ...state,
        tavernHeroes: action.payload.heroes || [],
        gold: action.payload.gold ?? state.gold,
      };

    case 'HIRE_HERO': {
      const { hero, gold: newGold } = action.payload;
      return {
        ...state,
        gold: newGold ?? state.gold,
        heroes: [...state.heroes, hero],
        tavernHeroes: state.tavernHeroes.filter(h => h.hero_id !== hero.hero_id),
      };
    }

    case 'SELECT_HERO': {
      const heroId = action.payload;
      const current = state.selectedHeroIds || [];
      if (current.includes(heroId)) {
        return { ...state, selectedHeroIds: current.filter(id => id !== heroId) };
      } else if (current.length < 4) {
        return { ...state, selectedHeroIds: [...current, heroId] };
      }
      return state;
    }

    case 'HERO_DIED': {
      const deadHeroId = action.payload.hero_id;
      return {
        ...state,
        heroes: state.heroes.map(h =>
          h.hero_id === deadHeroId
            ? { ...h, is_alive: false, equipment: {}, inventory: [] }
            : h
        ),
        heroDeaths: [...state.heroDeaths, action.payload],
      };
    }

    case 'SET_POST_MATCH_SUMMARY':
      return { ...state, postMatchSummary: action.payload };

    case 'CLEAR_POST_MATCH':
      return {
        ...state,
        postMatchSummary: null,
        heroDeaths: [],
        heroOutcomes: null,
      };

    case 'MERCHANT_BUY': {
      const { gold: newGold, hero_id, item } = action.payload;
      return {
        ...state,
        gold: newGold ?? state.gold,
        heroes: state.heroes.map(h =>
          h.hero_id === hero_id
            ? { ...h, inventory: [...(h.inventory || []), item] }
            : h
        ),
      };
    }

    case 'MERCHANT_SELL': {
      const { gold: newGold, hero_id, item_index } = action.payload;
      return {
        ...state,
        gold: newGold ?? state.gold,
        heroes: state.heroes.map(h =>
          h.hero_id === hero_id
            ? { ...h, inventory: (h.inventory || []).filter((_, i) => i !== item_index) }
            : h
        ),
      };
    }

    case 'HERO_EQUIP':
    case 'HERO_UNEQUIP': {
      const { hero_id, equipment: newEquip, inventory: newInv } = action.payload;
      return {
        ...state,
        heroes: state.heroes.map(h =>
          h.hero_id === hero_id
            ? { ...h, equipment: newEquip, inventory: newInv }
            : h
        ),
      };
    }

    case 'HERO_TRANSFER': {
      const { from_hero_id, to_hero_id, from_inventory, to_inventory } = action.payload;
      return {
        ...state,
        heroes: state.heroes.map(h => {
          if (h.hero_id === from_hero_id) return { ...h, inventory: from_inventory };
          if (h.hero_id === to_hero_id) return { ...h, inventory: to_inventory };
          return h;
        }),
      };
    }

    case 'BANK_DEPOSIT': {
      const { hero_id, inventory: depInv, bank: depBank } = action.payload;
      return {
        ...state,
        bank: depBank,
        heroes: state.heroes.map(h =>
          h.hero_id === hero_id
            ? { ...h, inventory: depInv }
            : h
        ),
      };
    }

    case 'BANK_WITHDRAW': {
      const { hero_id: wHeroId, inventory: wInv, bank: wBank } = action.payload;
      return {
        ...state,
        bank: wBank,
        heroes: state.heroes.map(h =>
          h.hero_id === wHeroId
            ? { ...h, inventory: wInv }
            : h
        ),
      };
    }

    case 'DISMISS_HERO': {
      const { hero_id: dismissedId, heroes: updatedHeroes } = action.payload;
      return {
        ...state,
        heroes: updatedHeroes ?? state.heroes.filter(h => h.hero_id !== dismissedId),
        selectedHeroIds: (state.selectedHeroIds || []).filter(id => id !== dismissedId),
      };
    }

    case 'LEAVE_MATCH':
      return {
        ...initialState,
        username: state.username,
        gold: state.gold,
        heroes: state.heroes,
        bank: state.bank,
        availableClasses: state.availableClasses,
      };

    default:
      return state;
  }
}
