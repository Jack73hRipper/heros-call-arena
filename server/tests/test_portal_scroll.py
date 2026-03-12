"""
Tests for Phase 12C — Portal Scroll mechanic.

Covers: channeling start, channeling tick, caster death cancellation,
portal spawn, portal tick/expiry, extraction, AI auto-extraction,
match end conditions, extracted heroes skip phases, channeling blocks actions.
"""

from app.models.player import PlayerState, Position
from app.models.actions import PlayerAction, ActionType
from app.core.turn_resolver import resolve_turn
from app.core.turn_phases.portal_phase import PORTAL_CHANNEL_TURNS, PORTAL_DURATION_TURNS
from app.core.combat import load_combat_config


def setup_module():
    load_combat_config()


def make_player(
    pid, username, x, y, hp=100, damage=15, armor=0,
    team="a", unit_type="human", inventory=None,
) -> PlayerState:
    p = PlayerState(
        player_id=pid,
        username=username,
        position=Position(x=x, y=y),
        hp=hp,
        max_hp=100,
        attack_damage=damage,
        armor=armor,
        unit_type=unit_type,
    )
    p.team = team
    if inventory is not None:
        p.inventory = inventory
    return p


def make_portal_item():
    """Return a portal_scroll inventory item dict."""
    return {
        "item_id": "portal_scroll",
        "name": "Portal Scroll",
        "item_type": "consumable",
        "consumable_effect": {"type": "portal"},
    }


# ---------------------------------------------------------------------------
# Channeling Tests
# ---------------------------------------------------------------------------


class TestChannelingStart:
    """Using a portal scroll should start 3-turn channeling."""

    def test_portal_scroll_starts_channeling(self):
        players = {
            "p1": make_player("p1", "Alice", 5, 5, inventory=[make_portal_item()]),
        }
        actions = [
            PlayerAction(
                player_id="p1",
                action_type=ActionType.USE_ITEM,
                target_x=0,  # inventory slot 0
            ),
        ]
        result = resolve_turn(
            "m1", 1, players, actions, 15, 15, set(),
            team_a=["p1"], is_dungeon=True,
        )
        # Channeling should be started
        assert result.channeling_started is not None
        assert result.channeling_started["player_id"] == "p1"
        # Portal scroll consumed from inventory
        assert len(players["p1"].inventory) == 0
        # Portal should not be spawned yet
        assert result.portal_spawned is None

    def test_channeling_tick_count_matches_constant(self):
        players = {
            "p1": make_player("p1", "Alice", 5, 5, inventory=[make_portal_item()]),
        }
        actions = [
            PlayerAction(
                player_id="p1",
                action_type=ActionType.USE_ITEM,
                target_x=0,
            ),
        ]
        result = resolve_turn(
            "m1", 1, players, actions, 15, 15, set(),
            team_a=["p1"], is_dungeon=True,
        )
        # After the first turn, channeling_tick should show turns remaining
        # The scroll sets 3 turns, then _resolve_channeling decrements to 2
        assert result.channeling_tick is not None
        assert result.channeling_tick["turns_remaining"] == PORTAL_CHANNEL_TURNS - 1


class TestChannelingTick:
    """Channeling should tick down each turn and spawn portal when done."""

    def _run_channeling_turns(self, players, team_a, n_turns):
        """Simulate n_turns of ongoing channeling, returning the last result."""
        # Initial state: channeling already active from previous scroll use
        channeling = {
            "player_id": "p1",
            "action": "portal",
            "turns_remaining": PORTAL_CHANNEL_TURNS,
            "tile_x": players["p1"].position.x,
            "tile_y": players["p1"].position.y,
        }
        portal = None
        result = None
        for _ in range(n_turns):
            result = resolve_turn(
                "m1", 1, players, [], 15, 15, set(),
                team_a=team_a, is_dungeon=True,
                match_channeling=channeling, match_portal=portal,
            )
            # Update channeling state for next turn
            if result.portal_spawned:
                channeling = None
                portal = {
                    "active": True,
                    "x": result.portal_spawned["x"],
                    "y": result.portal_spawned["y"],
                    "turns_remaining": result.portal_spawned["turns_remaining"],
                    "owner_id": result.portal_spawned["owner_id"],
                }
            elif result.channeling_tick:
                channeling["turns_remaining"] = result.channeling_tick["turns_remaining"]
            elif result.channeling_started:
                pass  # Initial setup
            else:
                channeling = None
        return result, channeling, portal

    def test_channeling_completes_after_3_turns(self):
        players = {"p1": make_player("p1", "Alice", 5, 5)}
        result, chan, portal = self._run_channeling_turns(players, ["p1"], PORTAL_CHANNEL_TURNS)
        # Portal should have spawned after 3 ticks
        assert result.portal_spawned is not None
        assert result.portal_spawned["x"] == 5
        assert result.portal_spawned["y"] == 5
        assert result.portal_spawned["turns_remaining"] == PORTAL_DURATION_TURNS
        assert chan is None  # Channeling cleared

    def test_channeling_produces_tick_events(self):
        players = {"p1": make_player("p1", "Alice", 5, 5)}
        # Run just 1 tick (not completing)
        result, chan, portal = self._run_channeling_turns(players, ["p1"], 1)
        assert result.channeling_tick is not None
        assert result.channeling_tick["turns_remaining"] == PORTAL_CHANNEL_TURNS - 1
        assert result.portal_spawned is None  # Not yet complete


class TestChannelingCancellation:
    """Channeling should cancel if the caster dies."""

    def test_caster_death_cancels_channel(self):
        players = {
            "p1": make_player("p1", "Alice", 5, 5, hp=1),
        }
        # Mark caster as dead before resolve
        players["p1"].is_alive = False
        players["p1"].hp = 0

        channeling = {
            "player_id": "p1",
            "action": "portal",
            "turns_remaining": 2,
            "tile_x": 5,
            "tile_y": 5,
        }
        result = resolve_turn(
            "m1", 1, players, [], 15, 15, set(),
            team_a=["p1"], is_dungeon=True,
            match_channeling=channeling,
        )
        # Channeling should have been cancelled (no tick, no spawn)
        assert result.channeling_tick is None
        assert result.portal_spawned is None


# ---------------------------------------------------------------------------
# Portal Entity Tests
# ---------------------------------------------------------------------------


class TestPortalTick:
    """Portal entity should tick down and expire."""

    def test_portal_ticks_down(self):
        players = {"p1": make_player("p1", "Alice", 5, 5)}
        portal = {
            "active": True,
            "x": 5,
            "y": 5,
            "turns_remaining": 10,
            "owner_id": "p1",
        }
        result = resolve_turn(
            "m1", 1, players, [], 15, 15, set(),
            team_a=["p1"], is_dungeon=True,
            match_portal=portal,
        )
        assert result.portal_tick is not None
        assert result.portal_tick["turns_remaining"] == 9

    def test_portal_expires_at_zero(self):
        players = {"p1": make_player("p1", "Alice", 5, 5)}
        portal = {
            "active": True,
            "x": 5,
            "y": 5,
            "turns_remaining": 1,
            "owner_id": "p1",
        }
        result = resolve_turn(
            "m1", 1, players, [], 15, 15, set(),
            team_a=["p1"], is_dungeon=True,
            match_portal=portal,
        )
        assert result.portal_expired is True
        assert result.portal_tick is None


# ---------------------------------------------------------------------------
# Extraction Tests
# ---------------------------------------------------------------------------


class TestExtraction:
    """Heroes should be able to enter an active portal to extract."""

    def test_hero_extracts_on_portal_tile(self):
        players = {"p1": make_player("p1", "Alice", 5, 5)}
        portal = {
            "active": True,
            "x": 5,
            "y": 5,
            "turns_remaining": 15,
            "owner_id": "p1",
        }
        actions = [
            PlayerAction(
                player_id="p1",
                action_type=ActionType.INTERACT,
                target_id="enter_portal",
            ),
        ]
        result = resolve_turn(
            "m1", 1, players, actions, 15, 15, set(),
            team_a=["p1"], is_dungeon=True,
            match_portal=portal,
        )
        assert len(result.extractions) == 1
        assert result.extractions[0]["player_id"] == "p1"
        assert players["p1"].extracted is True

    def test_hero_cannot_extract_off_portal(self):
        players = {"p1": make_player("p1", "Alice", 3, 3)}
        portal = {
            "active": True,
            "x": 5,
            "y": 5,
            "turns_remaining": 15,
            "owner_id": "p1",
        }
        actions = [
            PlayerAction(
                player_id="p1",
                action_type=ActionType.INTERACT,
                target_id="enter_portal",
            ),
        ]
        result = resolve_turn(
            "m1", 1, players, actions, 15, 15, set(),
            team_a=["p1"], is_dungeon=True,
            match_portal=portal,
        )
        assert len(result.extractions) == 0
        assert players["p1"].extracted is False

    def test_ai_ally_auto_extracts_on_portal(self):
        players = {
            "p1": make_player("p1", "Alice", 5, 5, unit_type="ai", team="a"),
        }
        players["p1"].controlled_by = "human1"
        portal = {
            "active": True,
            "x": 5,
            "y": 5,
            "turns_remaining": 15,
            "owner_id": "human1",
        }
        result = resolve_turn(
            "m1", 1, players, [], 15, 15, set(),
            team_a=["p1"], is_dungeon=True,
            match_portal=portal,
        )
        assert len(result.extractions) == 1
        assert players["p1"].extracted is True


# ---------------------------------------------------------------------------
# Extracted Hero Guard Tests
# ---------------------------------------------------------------------------


class TestExtractedGuards:
    """Extracted heroes should skip movement, attacks, skills."""

    def test_extracted_hero_cannot_move(self):
        players = {"p1": make_player("p1", "Alice", 5, 5)}
        players["p1"].extracted = True
        actions = [
            PlayerAction(player_id="p1", action_type=ActionType.MOVE, target_x=6, target_y=5),
        ]
        result = resolve_turn(
            "m1", 1, players, actions, 15, 15, set(),
            team_a=["p1"], is_dungeon=True,
        )
        # Player should not have moved
        assert players["p1"].position.x == 5

    def test_extracted_hero_cannot_attack(self):
        players = {
            "p1": make_player("p1", "Alice", 5, 5, team="a"),
            "e1": make_player("e1", "Enemy", 6, 5, team="b"),
        }
        players["p1"].extracted = True
        actions = [
            PlayerAction(player_id="p1", action_type=ActionType.ATTACK, target_x=6, target_y=5),
        ]
        result = resolve_turn(
            "m1", 1, players, actions, 15, 15, set(),
            team_a=["p1"], team_b=["e1"], is_dungeon=True,
        )
        # Enemy should not have taken damage
        assert players["e1"].hp == 100


# ---------------------------------------------------------------------------
# Match End Condition Tests
# ---------------------------------------------------------------------------


class TestDungeonVictory:
    """Dungeon match end conditions based on extraction state."""

    def test_all_extracted_is_dungeon_extract(self):
        players = {
            "p1": make_player("p1", "Alice", 5, 5, team="a"),
            "e1": make_player("e1", "Enemy", 10, 10, team="b"),
        }
        players["p1"].extracted = True  # Pre-set as extracted
        result = resolve_turn(
            "m1", 1, players, [], 15, 15, set(),
            team_a=["p1"], team_b=["e1"], is_dungeon=True,
        )
        assert result.winner == "dungeon_extract"

    def test_all_dead_is_party_wipe(self):
        players = {
            "p1": make_player("p1", "Alice", 5, 5, hp=0, team="a"),
            "e1": make_player("e1", "Enemy", 10, 10, team="b"),
        }
        players["p1"].is_alive = False
        result = resolve_turn(
            "m1", 1, players, [], 15, 15, set(),
            team_a=["p1"], team_b=["e1"], is_dungeon=True,
        )
        assert result.winner == "party_wipe"

    def test_mixed_extracted_and_dead_is_extract(self):
        players = {
            "p1": make_player("p1", "Alice", 5, 5, team="a"),
            "p2": make_player("p2", "Bob", 6, 5, hp=0, team="a"),
            "e1": make_player("e1", "Enemy", 10, 10, team="b"),
        }
        players["p1"].extracted = True
        players["p2"].is_alive = False
        result = resolve_turn(
            "m1", 1, players, [], 15, 15, set(),
            team_a=["p1", "p2"], team_b=["e1"], is_dungeon=True,
        )
        assert result.winner == "dungeon_extract"

    def test_alive_hero_remaining_no_winner(self):
        players = {
            "p1": make_player("p1", "Alice", 5, 5, team="a"),
            "p2": make_player("p2", "Bob", 6, 5, team="a"),
            "e1": make_player("e1", "Enemy", 10, 10, team="b"),
        }
        players["p1"].extracted = True
        # p2 is still alive and in play
        result = resolve_turn(
            "m1", 1, players, [], 15, 15, set(),
            team_a=["p1", "p2"], team_b=["e1"], is_dungeon=True,
        )
        assert result.winner is None  # Match continues


class TestChannelingBlocksActions:
    """Channeling heroes should not be able to move or attack."""

    def test_channeling_blocks_movement(self):
        players = {"p1": make_player("p1", "Alice", 5, 5)}
        channeling = {
            "player_id": "p1",
            "action": "portal",
            "turns_remaining": 2,
            "tile_x": 5,
            "tile_y": 5,
        }
        actions = [
            PlayerAction(player_id="p1", action_type=ActionType.MOVE, target_x=6, target_y=5),
        ]
        result = resolve_turn(
            "m1", 1, players, actions, 15, 15, set(),
            team_a=["p1"], is_dungeon=True,
            match_channeling=channeling,
        )
        # Should not have moved (channeling blocks movement)
        assert players["p1"].position.x == 5

    def test_channeling_blocks_melee(self):
        players = {
            "p1": make_player("p1", "Alice", 5, 5, team="a"),
            "e1": make_player("e1", "Enemy", 6, 5, team="b"),
        }
        channeling = {
            "player_id": "p1",
            "action": "portal",
            "turns_remaining": 2,
            "tile_x": 5,
            "tile_y": 5,
        }
        actions = [
            PlayerAction(player_id="p1", action_type=ActionType.ATTACK, target_x=6, target_y=5),
        ]
        result = resolve_turn(
            "m1", 1, players, actions, 15, 15, set(),
            team_a=["p1"], team_b=["e1"], is_dungeon=True,
            match_channeling=channeling,
        )
        # Enemy should not have taken damage
        assert players["e1"].hp == 100


class TestPortalConstants:
    """Verify the constants match design spec."""

    def test_channel_turns(self):
        assert PORTAL_CHANNEL_TURNS == 3

    def test_portal_duration(self):
        assert PORTAL_DURATION_TURNS == 20
