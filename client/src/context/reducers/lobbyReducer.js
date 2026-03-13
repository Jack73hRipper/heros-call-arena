/**
 * Lobby sub-reducer — handles lobby/pre-match actions.
 *
 * Action types handled:
 *   SET_USERNAME, JOIN_MATCH, PLAYER_JOINED, PLAYER_READY,
 *   PLAYER_DISCONNECTED, TEAM_CHANGED, CLASS_CHANGED,
 *   SET_AVAILABLE_CLASSES, CHAT_MESSAGE, CONFIG_CHANGED,
 *   SET_LOBBY_ERROR, HERO_SELECTED
 */

export function lobbyReducer(state, action) {
  switch (action.type) {
    case 'SET_USERNAME':
      return { ...state, username: action.payload };

    case 'JOIN_MATCH':
      return {
        ...state,
        matchId: action.payload.matchId,
        playerId: action.payload.playerId,
        matchStatus: 'waiting',
        lobbyPlayers: action.payload.players || {},
        lobbyConfig: action.payload.config || null,
        lobbyChat: action.payload.chat || [],
        lobbyError: null,
      };

    case 'PLAYER_JOINED': {
      const { player_id, username, position } = action.payload;
      return {
        ...state,
        lobbyPlayers: {
          ...state.lobbyPlayers,
          [player_id]: {
            username,
            position,
            hp: 100,
            max_hp: 100,
            is_alive: true,
            is_ready: false,
          },
        },
      };
    }

    case 'PLAYER_READY': {
      if (action.payload.players) {
        return {
          ...state,
          lobbyPlayers: action.payload.players,
        };
      }
      return state;
    }

    case 'PLAYER_DISCONNECTED': {
      const { player_id, username: dcUsername } = action.payload;
      const { [player_id]: _, ...remaining } = state.lobbyPlayers;
      const updatedPlayers = { ...state.players };
      if (updatedPlayers[player_id]) {
        updatedPlayers[player_id] = { ...updatedPlayers[player_id], is_alive: false };
      }
      return {
        ...state,
        lobbyPlayers: remaining,
        players: updatedPlayers,
        combatLog: [
          ...state.combatLog,
          { message: `${dcUsername || 'A player'} disconnected`, type: 'system' },
        ],
      };
    }

    case 'TEAM_CHANGED': {
      if (action.payload.players) {
        return {
          ...state,
          lobbyPlayers: action.payload.players,
        };
      }
      return state;
    }

    case 'CLASS_CHANGED': {
      if (action.payload.players) {
        return {
          ...state,
          lobbyPlayers: action.payload.players,
        };
      }
      return state;
    }

    case 'SET_AVAILABLE_CLASSES': {
      return {
        ...state,
        availableClasses: action.payload,
      };
    }

    case 'CHAT_MESSAGE': {
      return {
        ...state,
        lobbyChat: [
          ...state.lobbyChat,
          {
            sender: action.payload.sender,
            sender_id: action.payload.sender_id,
            message: action.payload.message,
            timestamp: action.payload.timestamp,
          },
        ],
      };
    }

    case 'CONFIG_CHANGED': {
      return {
        ...state,
        lobbyConfig: action.payload.config
          ? { ...state.lobbyConfig, ...action.payload.config }
          : state.lobbyConfig,
        lobbyPlayers: action.payload.players || state.lobbyPlayers,
      };
    }

    case 'SET_LOBBY_ERROR':
      return { ...state, lobbyError: action.payload };

    case 'HERO_SELECTED': {
      return {
        ...state,
        lobbyPlayers: action.payload.players || state.lobbyPlayers,
        lobbyError: null,
      };
    }

    default:
      return state;
  }
}
