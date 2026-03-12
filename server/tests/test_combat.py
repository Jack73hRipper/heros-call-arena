"""
Tests for combat engine — damage calculation, adjacency, victory checks.
"""

from app.models.player import PlayerState, Position
from app.core.combat import (
    calculate_damage_simple as calculate_damage,
    apply_damage,
    is_adjacent,
    is_valid_move,
    check_victory,
    load_combat_config,
)


def setup_module():
    """Load combat config before tests."""
    load_combat_config()


def make_player(pid="p1", username="Alice", x=0, y=0, hp=100, damage=15, armor=0) -> PlayerState:
    return PlayerState(
        player_id=pid,
        username=username,
        position=Position(x=x, y=y),
        hp=hp,
        max_hp=100,
        attack_damage=damage,
        armor=armor,
    )


class TestDamageCalculation:
    def test_basic_damage(self):
        attacker = make_player(damage=15)
        defender = make_player(armor=0)
        assert calculate_damage(attacker, defender) == 15

    def test_armor_reduces_damage(self):
        attacker = make_player(damage=15)
        defender = make_player(armor=5)
        dmg = calculate_damage(attacker, defender)
        assert dmg == 10  # 15 - (5 * 1)

    def test_minimum_damage_is_one(self):
        attacker = make_player(damage=1)
        defender = make_player(armor=100)
        assert calculate_damage(attacker, defender) == 1


class TestApplyDamage:
    def test_damage_reduces_hp(self):
        defender = make_player(hp=100)
        died = apply_damage(defender, 30)
        assert defender.hp == 70
        assert died is False

    def test_lethal_damage(self):
        defender = make_player(hp=20)
        died = apply_damage(defender, 20)
        assert defender.hp == 0
        assert died is True
        assert defender.is_alive is False

    def test_overkill(self):
        defender = make_player(hp=10)
        died = apply_damage(defender, 50)
        assert defender.hp == 0
        assert died is True


class TestAdjacency:
    def test_adjacent_cardinal(self):
        assert is_adjacent(Position(x=5, y=5), Position(x=5, y=6)) is True
        assert is_adjacent(Position(x=5, y=5), Position(x=6, y=5)) is True

    def test_adjacent_diagonal(self):
        assert is_adjacent(Position(x=5, y=5), Position(x=6, y=6)) is True

    def test_not_adjacent(self):
        assert is_adjacent(Position(x=5, y=5), Position(x=7, y=5)) is False

    def test_same_position_not_adjacent(self):
        assert is_adjacent(Position(x=5, y=5), Position(x=5, y=5)) is False


class TestVictory:
    def test_one_alive_wins(self):
        players = [
            make_player(pid="p1", hp=50),
            make_player(pid="p2", hp=0),
        ]
        players[1].is_alive = False
        assert check_victory(players) == "p1"

    def test_multiple_alive_no_winner(self):
        players = [
            make_player(pid="p1", hp=50),
            make_player(pid="p2", hp=50),
        ]
        assert check_victory(players) is None

    def test_all_dead_is_draw(self):
        players = [
            make_player(pid="p1", hp=0),
            make_player(pid="p2", hp=0),
        ]
        players[0].is_alive = False
        players[1].is_alive = False
        assert check_victory(players) == "draw"
