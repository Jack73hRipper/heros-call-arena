"""
Wave Spawner — Manages wave-based enemy spawning for wave arena maps.

Extracted from match_manager.py during P2 refactoring.
Handles wave state initialization, wave-clear checks, and enemy spawning per wave.

Phase 18C: Rarity rolling integrated — later waves produce higher-rarity enemies,
with wave_number used as a pseudo-floor for spawn chance scaling.
"""

from __future__ import annotations

import random as _random_mod
import uuid

from app.models.player import PlayerState, Position, apply_enemy_stats, get_enemy_definition
from app.core.map_loader import get_wave_spawner_config

# Wave spawner state: match_id -> {current_wave, total_waves, wave_config, spawning_active}
# Imported from match_manager at module level to share state
from app.core.match_manager import (
    _wave_state,
    _active_matches,
    _player_states,
)


def _init_wave_state(match_id: str) -> dict | None:
    """Initialize wave spawner state if the map has a wave_spawner config.

    Reads the wave_spawner config from the map JSON and stores it in _wave_state.
    Also spawns the first wave immediately.

    Returns wave info dict for the first wave (for broadcast), or None.
    """
    match = _active_matches.get(match_id)
    if not match:
        return None

    wave_config = get_wave_spawner_config(match.config.map_id)
    if not wave_config:
        return None  # Not a wave map — skip

    waves = wave_config.get("waves", [])
    if not waves:
        return None

    # Log wave config at load time for debugging
    print(f"[Wave] Match {match_id} — Loading {len(waves)} waves from {match.config.map_id}:")
    for w in waves:
        enemies = [e['enemy_type'] for e in w.get('enemies', [])]
        print(f"[Wave]   Wave {w['wave_number']}: {w['name']} ({len(enemies)} enemies: {', '.join(enemies)})")

    _wave_state[match_id] = {
        "current_wave": 0,               # 0 = no wave spawned yet
        "total_waves": len(waves),
        "wave_config": wave_config,
        "spawning_active": True,
        "wave_enemies": [],               # track enemy IDs for current wave
    }

    # Spawn first wave immediately
    wave_info = _spawn_next_wave(match_id)
    if wave_info:
        print(f"[Wave] Match {match_id} — Wave {wave_info['wave_number']}/{wave_info['total_waves']}: {wave_info['wave_name']} ({wave_info['enemy_count']} enemies)")
    return wave_info


def get_wave_state(match_id: str) -> dict | None:
    """Return the current wave state for a match, or None if not a wave map."""
    return _wave_state.get(match_id)


def check_wave_clear(match_id: str) -> bool:
    """Check if all enemies from the current wave are dead.

    Returns True if the current wave is cleared and there are more waves remaining.
    Returns False if the wave isn't cleared, there are no more waves, or this isn't a wave map.
    """
    state = _wave_state.get(match_id)
    if not state or not state["spawning_active"]:
        return False

    players = _player_states.get(match_id, {})
    wave_enemy_ids = state.get("wave_enemies", [])

    # Check if ALL enemies from current wave are dead
    all_dead = all(
        (eid not in players) or (not players[eid].is_alive)
        for eid in wave_enemy_ids
    )

    if not all_dead:
        return False

    # Wave is cleared — check if there are more waves
    return state["current_wave"] < state["total_waves"]


def _spawn_next_wave(match_id: str) -> dict | None:
    """Spawn the next wave of enemies. Returns wave info dict or None.

    Enemies are spawned free-roaming (no room leashing) with aggressive AI.
    They are placed at the spawner room's spawn points, cycling through positions
    if there are more enemies than spawn points.

    Phase 18C: Wave enemies can receive rarity upgrades. wave_number is used as a
    pseudo-floor for spawn chance scaling. Enemies may also specify force_rarity
    in the wave config to guarantee a specific rarity tier.

    Rarity Balance: Enforces difficulty budget and max_enhanced_per_wave caps
    (ported from dungeon map_exporter). Respects floor_overrides for affix count
    limits and per-wave max_rarity caps from wave config.
    """
    from app.core.monster_rarity import (
        roll_monster_rarity,
        roll_champion_type,
        get_champion_type_name,
        roll_affixes,
        generate_rare_name,
        apply_rarity_to_player,
        load_monster_rarity_config,
        get_floor_override,
        get_room_budget,
        get_rarity_cost,
    )

    state = _wave_state.get(match_id)
    if not state or not state["spawning_active"]:
        return None

    match = _active_matches.get(match_id)
    if not match:
        return None

    players = _player_states.get(match_id, {})
    wave_config = state["wave_config"]
    waves = wave_config.get("waves", [])
    spawn_points = wave_config.get("spawn_points", [])

    if not spawn_points:
        return None

    next_wave_idx = state["current_wave"]  # 0-indexed
    if next_wave_idx >= len(waves):
        state["spawning_active"] = False
        return None

    wave_def = waves[next_wave_idx]
    wave_number = wave_def.get("wave_number", next_wave_idx + 1)
    wave_name = wave_def.get("name", f"Wave {wave_number}")
    enemy_defs = wave_def.get("enemies", [])

    # Phase 18C: RNG for rarity rolling, seeded by match + wave for determinism
    rarity_rng = _random_mod.Random(hash(match_id) + wave_number * 7919)
    rarity_config = load_monster_rarity_config()

    # --- Rarity budget & cap enforcement (ported from map_exporter) ---
    floor_override = get_floor_override(wave_number)
    spawn_chances = rarity_config.get("spawn_chances", {})
    max_enhanced = floor_override.get(
        "max_enhanced_per_room",
        spawn_chances.get("max_enhanced_per_room", 2),
    )
    # Per-wave max_rarity cap from wave config (e.g. "champion" blocks rares)
    wave_max_rarity = wave_def.get("max_rarity")
    _rarity_rank = {"normal": 0, "champion": 1, "rare": 2, "super_unique": 3}
    max_rarity_rank = _rarity_rank.get(wave_max_rarity, 3)

    enemy_count = len(enemy_defs)
    wave_budget = get_room_budget(wave_number, enemy_count)
    wave_budget_remaining = wave_budget
    wave_enhanced_count = 0

    # Track enemy name counters for this wave
    name_counters: dict[str, int] = {}
    wave_enemy_ids: list[str] = []

    # Compute occupied tiles to avoid spawning on top of units
    occupied = set()
    for p in players.values():
        if p.is_alive:
            occupied.add((p.position.x, p.position.y))

    for i, enemy_spec in enumerate(enemy_defs):
        enemy_type = enemy_spec.get("enemy_type")
        if not enemy_type:
            continue

        enemy_def = get_enemy_definition(enemy_type)
        if not enemy_def:
            continue

        ai_id = f"wave-{wave_number}-{str(uuid.uuid4())[:6]}"

        # Determine spawn point — cycle through available points, skip occupied
        spawn_pos = None
        for attempt in range(len(spawn_points)):
            sp = spawn_points[(i + attempt) % len(spawn_points)]
            if (sp["x"], sp["y"]) not in occupied:
                spawn_pos = sp
                break
        if not spawn_pos:
            # All spawn points occupied — use the designated one anyway
            spawn_pos = spawn_points[i % len(spawn_points)]

        # Phase 18C: Determine monster rarity
        force_rarity = enemy_spec.get("force_rarity")
        is_boss = enemy_spec.get("is_boss", enemy_def.is_boss)

        monster_rarity = "normal"
        champion_type = None
        affixes = []
        rarity_display_name = None

        if force_rarity and force_rarity != "normal":
            # Forced rarity from wave config
            monster_rarity = force_rarity
        elif not is_boss and getattr(enemy_def, "allow_rarity_upgrade", True):
            # Enforce max_enhanced cap before rolling
            if wave_enhanced_count >= max_enhanced:
                monster_rarity = "normal"
            else:
                # Roll rarity using wave_number as pseudo-floor
                monster_rarity = roll_monster_rarity(wave_number, rarity_rng)

        # Enforce per-wave max_rarity cap (e.g. waves 1-5 capped at "champion")
        if _rarity_rank.get(monster_rarity, 0) > max_rarity_rank:
            if max_rarity_rank >= 1:
                monster_rarity = "champion"
            else:
                monster_rarity = "normal"

        # Budget-aware downgrade — if rolled rarity exceeds remaining budget
        if monster_rarity != "normal":
            cost = get_rarity_cost(monster_rarity)
            if cost > wave_budget_remaining:
                if monster_rarity == "rare" and get_rarity_cost("champion") <= wave_budget_remaining:
                    monster_rarity = "champion"
                else:
                    monster_rarity = "normal"

        if monster_rarity == "champion":
            champion_type = roll_champion_type(rarity_rng)
            ct_name = get_champion_type_name(champion_type)
            rarity_display_name = f"{ct_name} {enemy_def.name}"
        elif monster_rarity == "rare":
            rare_tier = rarity_config.get("rarity_tiers", {}).get("rare", {})
            # Use floor override for affix count if available (early floors = fewer affixes)
            affix_range = floor_override.get(
                "rare_affix_count",
                rare_tier.get("affix_count", [2, 3]),
            )
            if isinstance(affix_range, list) and len(affix_range) == 2:
                affix_count = rarity_rng.randint(affix_range[0], affix_range[1])
            else:
                affix_count = 2
            affixes = roll_affixes(enemy_def, affix_count, rarity_rng)
            rarity_display_name = generate_rare_name(enemy_def.name, affixes, rarity_rng)

        # Track budget and enhanced count
        rarity_cost = get_rarity_cost(monster_rarity)
        wave_budget_remaining -= rarity_cost
        if monster_rarity != "normal":
            wave_enhanced_count += 1

        # Generate name
        if rarity_display_name:
            display_name = rarity_display_name
        elif is_boss:
            display_name = enemy_def.name
        else:
            name_counters[enemy_type] = name_counters.get(enemy_type, 0) + 1
            display_name = f"{enemy_def.name}-{name_counters[enemy_type]}"

        enemy_unit = PlayerState(
            player_id=ai_id,
            username=display_name,
            position=Position(x=spawn_pos["x"], y=spawn_pos["y"]),
            unit_type="ai",
            team="b",
            is_ready=True,
        )

        # Apply enemy stats (no room_id = free-roaming, no leashing)
        apply_enemy_stats(enemy_unit, enemy_type)

        if is_boss:
            enemy_unit.is_boss = True

        # Phase 18C: Apply rarity upgrade
        if monster_rarity != "normal":
            apply_rarity_to_player(
                enemy_unit,
                rarity=monster_rarity,
                champion_type=champion_type,
                affixes=affixes,
                display_name=display_name,
            )

        occupied.add((spawn_pos["x"], spawn_pos["y"]))

        players[ai_id] = enemy_unit
        match.ai_ids.append(ai_id)
        match.player_ids.append(ai_id)
        match.team_b.append(ai_id)
        wave_enemy_ids.append(ai_id)

    _player_states[match_id] = players
    state["current_wave"] = next_wave_idx + 1
    state["wave_enemies"] = wave_enemy_ids

    return {
        "wave_number": wave_number,
        "wave_name": wave_name,
        "enemy_count": len(wave_enemy_ids),
        "total_waves": state["total_waves"],
    }


def advance_wave_if_cleared(match_id: str) -> dict | None:
    """Check if current wave is cleared and spawn the next one if so.

    Called from match_tick after resolve_turn. Returns wave info dict if a new
    wave was spawned, or None if no wave advancement occurred.
    """
    if not check_wave_clear(match_id):
        return None
    return _spawn_next_wave(match_id)


def is_wave_map(match_id: str) -> bool:
    """Check if a match is using a wave spawner map."""
    return match_id in _wave_state


def all_waves_complete(match_id: str) -> bool:
    """Check if all waves have been spawned and cleared.

    Returns True only when all waves have been spawned AND all wave enemies are dead.
    This is used to suppress the standard team_victory check until the final wave is cleared.
    """
    state = _wave_state.get(match_id)
    if not state:
        return True  # Not a wave map — defer to standard victory

    # If waves are still spawning and there are more waves, not complete
    if state["current_wave"] < state["total_waves"]:
        return False

    # All waves spawned — check if final wave enemies are all dead
    players = _player_states.get(match_id, {})
    wave_enemy_ids = state.get("wave_enemies", [])
    return all(
        (eid not in players) or (not players[eid].is_alive)
        for eid in wave_enemy_ids
    )
