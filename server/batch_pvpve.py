"""
Batch PVPVE Simulator — Headless 4-team dungeon match runner with ASCII replay.

Runs the EXACT same PVPVE game logic as live matches: WFC dungeon generation,
4 AI hero parties, PVE enemies, doors, chests, room leashing, pathfinding,
turn resolution, combat, skills — everything. No WebSocket, no rendering.

Outputs a turn-by-turn ASCII map and movement log so you can visually diagnose
behavioral problems (stuck units, oscillation, hallway deadlocks, etc.).

Usage:
    python batch_pvpve.py
    python batch_pvpve.py --grid-size 6 --max-turns 150
    python batch_pvpve.py --team-size 3 --pve-density 0.8 --verbose
    python batch_pvpve.py --matches 10 --no-ascii
    python batch_pvpve.py --seed 12345 --verbose
    python batch_pvpve.py --verbose --trace-team a

Options:
    --matches N         Number of PVPVE matches to run (default: 1)
    --grid-size N       WFC grid size — 4=Small, 6=Large, 8=XL (default: 8)
    --team-size N       Heroes per team, 1-5 (default: 5)
    --pve-density F     PVE enemy density 0.0-1.0 (default: 0.5)
    --max-turns N       Turn limit before declaring a draw (default: 300)
    --seed N            Fixed RNG seed for reproducibility (default: random)
    --verbose           Print detailed movement decisions per turn
    --trace-team T      Filter verbose output to team a/b/c/d/pve only
    --no-ascii          Skip ASCII map rendering (faster for batch runs)
    --ascii-every N     Print ASCII map every N turns (default: 5)
    --log FILE          Write full movement log to file

Match reports are saved to server/data/match_history/ and visible in
Arena Analyst (start-arena-analyst.bat).
"""

from __future__ import annotations

import argparse
import os
import sys
import time
import random

# Fix Windows console encoding for Unicode box-drawing chars
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# Add the server directory to the Python path so app.* imports work
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.models.match import MatchConfig, MatchType
from app.models.actions import PlayerAction, ActionType
from app.core.match_manager import (
    create_match,
    start_match,
    get_match,
    get_match_players,
    get_match_teams,
    get_ai_ids,
    increment_turn,
    pop_next_actions,
    set_fov_cache,
    get_fov_cache,
    get_team_fov,
    get_dungeon_state,
    get_stairs_info,
    get_controlled_unit_ids,
    end_match,
    remove_match,
    track_damage_dealt,
    track_damage_taken,
    track_healing_done,
    track_items_looted,
    track_turn_survived,
    record_turn_events,
    save_match_report,
    generate_auto_target_action,
    clear_auto_target,
    clear_player_queue,
)
from app.core.turn_resolver import resolve_turn
from app.core.map_loader import load_map, get_obstacles_with_door_states, is_dungeon_map
from app.core.fov import compute_fov
from app.core.ai_behavior import run_ai_decisions, clear_ai_patrol_state
from app.models.player import get_all_classes


# ─── Team display ────────────────────────────────────────────────────────────

TEAM_COLORS = {
    "a": "\033[94m",   # Blue
    "b": "\033[91m",   # Red
    "c": "\033[93m",   # Yellow
    "d": "\033[95m",   # Magenta
    "pve": "\033[90m", # Gray
}
RESET = "\033[0m"
BOLD = "\033[1m"

TEAM_SYMBOLS = {
    "a": "A",
    "b": "B",
    "c": "C",
    "d": "D",
    "pve": "e",
}


def _team_label(team: str) -> str:
    """Colored team label for console output."""
    color = TEAM_COLORS.get(team, "")
    return f"{color}Team {team.upper()}{RESET}"


# ─── ASCII Map Renderer ─────────────────────────────────────────────────────

def render_ascii_map(
    map_data: dict,
    all_units: dict,
    door_states: dict | None = None,
    turn_number: int = 0,
) -> str:
    """Render the dungeon as an ASCII map with unit positions marked.

    Legend:
        # = Wall    . = Floor    D = Door (closed)    d = door (open)
        C = Chest   A/B/C/D = Hero team units    e = PVE enemy
        * = Dead unit (any team)
    """
    tiles = map_data.get("tiles", [])
    tile_legend = map_data.get("tile_legend", {})
    width = map_data.get("width", 0)
    height = map_data.get("height", 0)

    if not tiles:
        return "(no tile data)"

    # Build base map from tiles
    grid = []
    for y in range(height):
        row = []
        for x in range(width):
            if y < len(tiles) and x < len(tiles[y]):
                ch = tiles[y][x]
                tile_type = tile_legend.get(ch, "wall")
                if tile_type in ("wall",):
                    row.append("#")
                elif tile_type in ("floor", "spawn", "corridor"):
                    row.append(".")
                elif tile_type == "door":
                    row.append("D")
                elif tile_type == "chest":
                    row.append("C")
                elif tile_type == "stairs":
                    row.append(">")
                else:
                    row.append(".")
            else:
                row.append("#")
        grid.append(row)

    # Override door tiles with open/closed state
    if door_states:
        for key, state in door_states.items():
            parts = key.split(",")
            if len(parts) == 2:
                dx, dy = int(parts[0]), int(parts[1])
                if 0 <= dy < height and 0 <= dx < width:
                    grid[dy][dx] = "d" if state == "open" else "D"

    # Place units on the map
    for uid, unit in all_units.items():
        x, y = unit.position.x, unit.position.y
        if 0 <= y < height and 0 <= x < width:
            team = getattr(unit, "team", "?")
            if not unit.is_alive:
                grid[y][x] = "*"
            else:
                symbol = TEAM_SYMBOLS.get(team, "?")
                grid[y][x] = symbol

    # Build output string
    lines = []
    lines.append(f"+== Turn {turn_number} {'=' * max(1, width * 2 - 12)}+")

    for y in range(height):
        row_str = ""
        for x in range(width):
            ch = grid[y][x]
            if ch in TEAM_SYMBOLS.values():
                # Find the team for this symbol
                team = [t for t, s in TEAM_SYMBOLS.items() if s == ch]
                color = TEAM_COLORS.get(team[0], "") if team else ""
                row_str += f"{color}{BOLD}{ch}{RESET} "
            elif ch == "*":
                row_str += f"\033[31m*{RESET} "
            elif ch == "#":
                row_str += f"\033[90m#{RESET} "
            elif ch == "D":
                row_str += f"\033[33mD{RESET} "
            elif ch == "d":
                row_str += f"\033[32md{RESET} "
            elif ch == "C":
                row_str += f"\033[33mC{RESET} "
            elif ch == ">":
                row_str += f"\033[36m>{RESET} "
            else:
                row_str += f"\033[90m.{RESET} "
        lines.append(f"|{row_str}|")

    lines.append(f"+{'=' * (width * 2 + 1)}+")

    return "\n".join(lines)


def render_team_summary(all_units: dict) -> str:
    """Render a 1-line summary per team: alive/total HP, positions."""
    teams: dict[str, list] = {}
    for uid, unit in all_units.items():
        team = getattr(unit, "team", "?")
        if team not in teams:
            teams[team] = []
        teams[team].append(unit)

    lines = []
    for team_key in sorted(teams.keys()):
        members = teams[team_key]
        alive = [u for u in members if u.is_alive]
        total_hp = sum(u.hp for u in alive)
        max_hp = sum(u.max_hp for u in alive)
        positions = [(u.position.x, u.position.y) for u in alive]

        label = _team_label(team_key)
        hp_str = f"{total_hp}/{max_hp} HP" if alive else "ELIMINATED"
        count_str = f"{len(alive)}/{len(members)} alive"
        pos_str = ", ".join(f"({x},{y})" for x, y in positions[:5])
        if len(positions) > 5:
            pos_str += f" +{len(positions)-5} more"

        lines.append(f"  {label}: {count_str} | {hp_str} | {pos_str}")

    return "\n".join(lines)


# ─── Movement Logger ─────────────────────────────────────────────────────────

def log_movement_decisions(
    actions: list,
    all_units: dict,
    turn_number: int,
    verbose: bool = False,
    trace_team: str | None = None,
) -> list[str]:
    """Extract movement-related decisions from action list.

    Returns a list of human-readable movement log lines.
    """
    lines = []

    for act in actions:
        pid = act.player_id if hasattr(act, "player_id") else str(act)
        unit = all_units.get(pid)
        if not unit:
            continue

        team = getattr(unit, "team", "?")
        # Skip if filtering by team and this unit doesn't match
        if trace_team and team != trace_team:
            continue

        name = getattr(unit, "username", pid[:12])
        action_type = act.action_type if hasattr(act, "action_type") else None
        reason = getattr(act, "reason", None) or ""
        reason_tag = f" [{reason}]" if reason else ""

        if action_type == ActionType.MOVE:
            from_pos = f"({unit.position.x},{unit.position.y})"
            to_x = act.target_x if hasattr(act, "target_x") else "?"
            to_y = act.target_y if hasattr(act, "target_y") else "?"
            to_pos = f"({to_x},{to_y})"
            lines.append(f"  [T{turn_number}] {_team_label(team)} {name}: MOVE {from_pos} → {to_pos}{reason_tag}")

        elif action_type == ActionType.ATTACK:
            target = all_units.get(act.target_id, None) if hasattr(act, "target_id") and act.target_id else None
            target_name = getattr(target, "username", act.target_id[:12]) if target else "?"
            lines.append(f"  [T{turn_number}] {_team_label(team)} {name}: ATTACK → {target_name}{reason_tag}")

        elif action_type == ActionType.RANGED_ATTACK:
            target = all_units.get(act.target_id, None) if hasattr(act, "target_id") and act.target_id else None
            target_name = getattr(target, "username", act.target_id[:12]) if target else "?"
            lines.append(f"  [T{turn_number}] {_team_label(team)} {name}: RANGED → {target_name}{reason_tag}")

        elif action_type == ActionType.SKILL:
            skill_id = getattr(act, "skill_id", "?")
            lines.append(f"  [T{turn_number}] {_team_label(team)} {name}: SKILL {skill_id}{reason_tag}")

        elif action_type == ActionType.INTERACT:
            lines.append(f"  [T{turn_number}] {_team_label(team)} {name}: INTERACT (door/chest){reason_tag}")

        elif action_type == ActionType.WAIT:
            if verbose:
                lines.append(f"  [T{turn_number}] {_team_label(team)} {name}: WAIT{reason_tag}")

        elif verbose:
            lines.append(f"  [T{turn_number}] {_team_label(team)} {name}: {action_type}{reason_tag}")

    return lines


def log_turn_results(turn_result, all_units: dict, turn_number: int) -> list[str]:
    """Extract important events from the resolved turn."""
    lines = []

    # Deaths
    for death_pid in turn_result.deaths:
        unit = all_units.get(death_pid)
        if unit:
            team = getattr(unit, "team", "?")
            name = getattr(unit, "username", death_pid[:12])
            lines.append(f"  {BOLD}\033[31m☠ {name} ({_team_label(team)}) DIED{RESET}")

    # Door changes
    for dc in turn_result.door_changes:
        dx = dc.get("x", "?")
        dy = dc.get("y", "?")
        state = dc.get("state", "?")
        lines.append(f"  Door at ({dx},{dy}) → {state}")

    # Failed INTERACT actions (door adjacency failures, etc.)
    for act in turn_result.actions:
        if act.action_type == ActionType.INTERACT and not act.success:
            unit = all_units.get(act.player_id)
            name = getattr(unit, "username", act.player_id[:12]) if unit else act.player_id[:12]
            team = getattr(unit, "team", "?") if unit else "?"
            lines.append(f"  \033[33m⚠ {name} ({_team_label(team)}) INTERACT FAILED: {act.message}{RESET}")

    # Chest opened
    for co in turn_result.chest_opened:
        cx = co.get("x", co.get("position", "?"))
        cy = co.get("y", "")
        pos_str = f"({cx},{cy})" if cy != "" else str(cx)
        lines.append(f"  Chest opened at {pos_str}")

    # Combat damage (summarize)
    damage_events = []
    for act in turn_result.actions:
        if hasattr(act, "damage_dealt") and act.damage_dealt and act.damage_dealt > 0:
            attacker = all_units.get(act.player_id)
            target = all_units.get(act.target_id) if hasattr(act, "target_id") and act.target_id else None
            a_name = getattr(attacker, "username", "?") if attacker else "?"
            t_name = getattr(target, "username", "?") if target else "?"
            damage_events.append(f"{a_name} → {t_name} for {act.damage_dealt}")

    if damage_events:
        lines.append(f"  ⚔ Combat: {', '.join(damage_events[:8])}")
        if len(damage_events) > 8:
            lines.append(f"    ... and {len(damage_events)-8} more hits")

    # Healing
    heal_events = []
    for act in turn_result.actions:
        if hasattr(act, "heal_amount") and act.heal_amount and act.heal_amount > 0:
            healer = all_units.get(act.player_id)
            h_name = getattr(healer, "username", "?") if healer else "?"
            heal_events.append(f"{h_name} healed {act.heal_amount}")

    if heal_events:
        lines.append(f"  💚 Healing: {', '.join(heal_events[:5])}")

    return lines


def compact_turn_summary(
    turn_number: int,
    actions: list,
    turn_result,
    all_units: dict,
) -> str:
    """Build a single-line per-turn summary for quick scanning.

    Format: T005 | A:5/5 250hp | B:4/5 180hp | ... | 3⚔ 1☠ 2💚
    """
    # Team HP snapshot
    team_info: dict[str, dict] = {}
    for uid, unit in all_units.items():
        t = getattr(unit, "team", "?")
        if t not in team_info:
            team_info[t] = {"alive": 0, "total": 0, "hp": 0}
        team_info[t]["total"] += 1
        if unit.is_alive:
            team_info[t]["alive"] += 1
            team_info[t]["hp"] += unit.hp

    parts = [f"T{turn_number:03d}"]
    for tk in ("a", "b", "c", "d"):
        info = team_info.get(tk)
        if info:
            color = TEAM_COLORS.get(tk, "")
            parts.append(f"{color}{tk.upper()}:{info['alive']}/{info['total']} {info['hp']}hp{RESET}")

    # Count PVE alive
    pve = team_info.get("pve")
    if pve and pve["alive"] > 0:
        parts.append(f"\033[90mPVE:{pve['alive']}{RESET}")

    # Event counters from turn result
    n_hits = sum(1 for a in turn_result.actions if getattr(a, "damage_dealt", 0) and a.damage_dealt > 0)
    n_deaths = len(turn_result.deaths)
    n_heals = sum(1 for a in turn_result.actions if getattr(a, "heal_amount", 0) and a.heal_amount > 0)
    n_skills = sum(1 for a in actions if hasattr(a, "action_type") and a.action_type == ActionType.SKILL)

    event_parts = []
    if n_hits:
        event_parts.append(f"{n_hits}\u2694")
    if n_deaths:
        event_parts.append(f"\033[31m{n_deaths}\u2620{RESET}")
    if n_heals:
        event_parts.append(f"\033[32m{n_heals}\U0001f49a{RESET}")
    if n_skills:
        event_parts.append(f"\033[36m{n_skills}\u2728{RESET}")

    if event_parts:
        parts.append(" ".join(event_parts))

    return "  " + " | ".join(parts)


# ─── Core Simulation ─────────────────────────────────────────────────────────

def run_headless_pvpve(
    team_size: int = 5,
    grid_size: int = 8,
    pve_density: float = 0.5,
    max_turns: int = 300,
    seed: int | None = None,
    verbose: bool = False,
    show_ascii: bool = True,
    ascii_every: int = 5,
    log_file: str | None = None,
    trace_team: str | None = None,
) -> dict | None:
    """Run a single headless 4-team PVPVE dungeon match.

    Uses the exact same PVPVE initialization path as live matches:
    - _start_pvpve_match() → WFC dungeon generation
    - _spawn_pvpve_ai_teams() → 4 AI hero parties
    - _spawn_pvpve_enemies() → PVE enemies with monster rarity
    - Full AI decision engine + turn resolver

    Returns the match summary dict, or None on failure.
    """
    if seed is not None:
        random.seed(seed)

    # Configure a PVPVE match with 4 AI hero teams
    config = MatchConfig(
        match_type=MatchType.PVPVE,
        pvpve_team_count=4,
        pvpve_ai_team_count=3,  # Teams B, C, D are AI
        pvpve_ai_team_sizes=[team_size, team_size, team_size],
        pvpve_grid_size=grid_size,
        pvpve_pve_density=pve_density,
        pvpve_boss_enabled=True,
        pvpve_loot_density=0.5,
        tick_rate=1.0,
        max_players=team_size * 4 + 100,  # Room for heroes + enemies
        # Team A: spawn via ai_allies so they exist before _start_pvpve_match
        ai_allies=team_size,
    )

    # Create match with a dummy host
    match, host = create_match("PVPVESim", config=config)
    match_id = match.match_id

    host.is_ready = True

    # Start the match — this triggers _start_pvpve_match() which:
    #   1. Spawns AI hero teams for B, C, D
    #   2. Generates WFC dungeon
    #   3. Resolves spawns
    #   4. Applies class stats
    #   5. Inits dungeon state (doors, chests)
    #   6. Spawns PVE enemies
    started = start_match(match_id)
    if not started:
        print(f"  [ERROR] Failed to start PVPVE match {match_id}")
        remove_match(match_id)
        return None

    # Remove the dummy host from match state
    host_id = host.player_id
    all_units = get_match_players(match_id)
    all_units.pop(host_id, None)
    if host_id in match.player_ids:
        match.player_ids.remove(host_id)
    if host_id in match.team_a:
        match.team_a.remove(host_id)

    # Fix Team A: the dummy host was removed, so ai_ally followers referencing
    # the host as their owner would WAIT every turn.  Find (or promote) a Team A
    # leader and re-parent the followers to that leader so they use the normal
    # follow-stance AI — matching live PVPVE behavior.
    team_a_leader_id = None
    for uid in match.team_a:
        unit = all_units.get(uid)
        if unit and unit.is_alive and getattr(unit, "is_team_leader", False):
            team_a_leader_id = uid
            break

    # If no leader exists yet, promote the first alive unit
    if not team_a_leader_id:
        for uid in match.team_a:
            unit = all_units.get(uid)
            if unit and unit.is_alive:
                unit.is_team_leader = True
                unit.hero_id = None
                unit.ai_stance = None
                unit.ai_behavior = "aggressive"
                team_a_leader_id = uid
                break

    # Re-parent Team A followers to the team leader (instead of removed host)
    for uid in match.team_a:
        if uid == team_a_leader_id:
            # Ensure leader has aggressive independent AI
            unit = all_units.get(uid)
            if unit:
                unit.hero_id = None
                unit.ai_stance = None
                unit.ai_behavior = "aggressive"
                unit.is_team_leader = True
            continue
        unit = all_units.get(uid)
        if unit and unit.hero_id:
            # Point follower at the team leader so follow-stance AI works
            unit.hero_id = team_a_leader_id
            unit.ai_stance = "follow"

    # Teams B, C, D: leave as-is.  _spawn_pvpve_ai_teams() already set up
    # leaders (aggressive, hero_id=None) and followers (hero_id=leader,
    # ai_stance="follow") — this matches live PVPVE match behavior.

    # Load map data
    map_id = match.config.map_id
    map_data = load_map(map_id)
    grid_width = map_data.get("width", 15)
    grid_height = map_data.get("height", 15)

    # Count units
    all_units = get_match_players(match_id)
    hero_count = sum(1 for u in all_units.values()
                     if u.is_alive and getattr(u, "team", "") in ("a", "b", "c", "d"))
    pve_count = sum(1 for u in all_units.values()
                    if u.is_alive and getattr(u, "team", "") == "pve")

    print(f"\n{'═' * 70}")
    print(f"  PVPVE DUNGEON SIMULATION")
    print(f"  Match: {match_id} | Grid: {grid_size}x{grid_size} | Map: {grid_width}x{grid_height} tiles")
    print(f"  Teams: 4 x {team_size} heroes = {hero_count} hero units")
    print(f"  PVE enemies: {pve_count} | Max turns: {max_turns}")
    print(f"  Theme: {match.theme_id}")
    print(f"{'═' * 70}")

    # Print initial team compositions
    teams_display = {"a": match.team_a, "b": match.team_b, "c": match.team_c, "d": match.team_d}
    for team_key, team_ids in teams_display.items():
        members = [all_units.get(uid) for uid in team_ids if all_units.get(uid)]
        if members:
            classes = [getattr(m, "username", "?") for m in members]
            print(f"  {_team_label(team_key)}: {', '.join(classes)}")
    print()

    # Open log file if requested
    log_fh = None
    if log_file:
        log_fh = open(log_file, "w", encoding="utf-8")
        log_fh.write(f"PVPVE Simulation Log — Match {match_id}\n")
        log_fh.write(f"Grid: {grid_size}x{grid_size} | Map: {grid_width}x{grid_height}\n")
        log_fh.write(f"Theme: {match.theme_id}\n\n")

    winner = None
    turn_number = 0
    movement_log_lines: list[str] = []

    # Show initial map
    if show_ascii:
        dungeon_state = get_dungeon_state(match_id)
        door_states = dungeon_state["door_states"] if dungeon_state else None
        ascii_map = render_ascii_map(map_data, all_units, door_states, turn_number=0)
        print(ascii_map)
        print(render_team_summary(all_units))
        print()

    # ─── Main tick loop ──────────────────────────────────────────────────────
    for turn in range(1, max_turns + 1):
        match = get_match(match_id)
        if not match or match.status != "in_progress":
            break

        turn_number = increment_turn(match_id)
        all_units = get_match_players(match_id)
        team_a, team_b, team_c, team_d = get_match_teams(match_id)
        ai_ids = get_ai_ids(match_id)

        # Dungeon state
        dungeon_state = get_dungeon_state(match_id)
        door_states = dungeon_state["door_states"] if dungeon_state else None
        chest_states = dungeon_state["chest_states"] if dungeon_state else None
        ground_items = dungeon_state["ground_items"] if dungeon_state else None

        obstacles = get_obstacles_with_door_states(map_id, door_states)

        # Door tiles for AI pathfinding
        door_tiles = None
        if door_states:
            door_tiles = set()
            for key, state in door_states.items():
                if state == "closed":
                    parts = key.split(",")
                    if len(parts) == 2:
                        door_tiles.add((int(parts[0]), int(parts[1])))
            if not door_tiles:
                door_tiles = None

        # Step 1: Compute FOV
        for uid, unit in all_units.items():
            if unit.is_alive and not unit.extracted:
                fov = compute_fov(
                    unit.position.x, unit.position.y,
                    unit.vision_range,
                    grid_width, grid_height,
                    obstacles,
                )
                set_fov_cache(match_id, uid, fov)

        # Step 2: Run AI decisions with shared team FOV
        pre_team_a_fov = get_team_fov(match_id, team_a) if team_a else set()
        pre_team_b_fov = get_team_fov(match_id, team_b) if team_b else set()
        pre_team_c_fov = get_team_fov(match_id, team_c) if team_c else set()
        pre_team_d_fov = get_team_fov(match_id, team_d) if team_d else set()
        ai_team_fov_map = {
            "a": pre_team_a_fov,
            "b": pre_team_b_fov,
            "c": pre_team_c_fov,
            "d": pre_team_d_fov,
        }

        ai_actions = run_ai_decisions(
            ai_ids, all_units, grid_width, grid_height, obstacles,
            team_fov_map=ai_team_fov_map,
            match_id=match_id,
            controlled_ids=get_controlled_unit_ids(match_id),
            door_tiles=door_tiles,
            portal=match.portal,
            match_state=match,
            ground_items=ground_items,
            chest_states=chest_states,
        )

        action_list = list(ai_actions)

        # Log movement decisions (before resolution)
        move_lines = log_movement_decisions(action_list, all_units, turn_number, verbose, trace_team)
        movement_log_lines.extend(move_lines)

        if verbose and move_lines:
            for line in move_lines:
                print(line)

        # Step 3: Resolve the turn
        use_teams = bool(team_a or team_b or team_c or team_d)
        match_is_dungeon = True  # PVPVE is always a dungeon

        stairs_info = get_stairs_info(match_id) if match_is_dungeon else None
        stairs_positions = stairs_info["positions"] if stairs_info else None
        stairs_unlocked = stairs_info["unlocked"] if stairs_info else False

        turn_result = resolve_turn(
            match_id=match_id,
            turn_number=turn_number,
            players=all_units,
            actions=action_list,
            grid_width=grid_width,
            grid_height=grid_height,
            obstacles=obstacles,
            team_a=team_a if use_teams else None,
            team_b=team_b if use_teams else None,
            team_c=team_c if use_teams else None,
            team_d=team_d if use_teams else None,
            door_states=door_states,
            chest_states=chest_states,
            ground_items=ground_items,
            is_dungeon=match_is_dungeon,
            match_channeling=match.channeling,
            match_portal=match.portal,
            stairs_positions=stairs_positions,
            stairs_unlocked=stairs_unlocked,
            floor_number=getattr(match, "current_floor", 1),
            match_state=match,
        )

        # Phase 12C: Persist channeling/portal state back to MatchState
        # (mirrors tick_loop.py logic — without this, channeling and portals
        # are invisible to subsequent turns in headless simulation)
        if turn_result.channeling_started and not turn_result.portal_spawned:
            match.channeling = {
                "player_id": turn_result.channeling_started["player_id"],
                "action": "portal",
                "turns_remaining": turn_result.channeling_started["turns_remaining"],
                "tile_x": turn_result.channeling_started["tile_x"],
                "tile_y": turn_result.channeling_started["tile_y"],
            }
        elif turn_result.channeling_tick:
            if match.channeling:
                match.channeling["turns_remaining"] = turn_result.channeling_tick["turns_remaining"]
            else:
                match.channeling = None
        elif turn_result.portal_spawned:
            match.channeling = None
        elif match.channeling and not turn_result.channeling_tick and not turn_result.channeling_started:
            match.channeling = None

        if turn_result.portal_spawned:
            match.portal = {
                "active": True,
                "x": turn_result.portal_spawned["x"],
                "y": turn_result.portal_spawned["y"],
                "turns_remaining": turn_result.portal_spawned["turns_remaining"],
                "owner_id": turn_result.portal_spawned["owner_id"],
            }
        elif turn_result.portal_tick:
            if match.portal:
                match.portal["turns_remaining"] = turn_result.portal_tick["turns_remaining"]
        elif turn_result.portal_expired:
            match.portal = None

        # Track combat stats
        for act in turn_result.actions:
            if act.damage_dealt and act.damage_dealt > 0:
                track_damage_dealt(match_id, act.player_id, act.damage_dealt)
                if act.target_id:
                    track_damage_taken(match_id, act.target_id, act.damage_dealt)
            if act.heal_amount and act.heal_amount > 0:
                track_healing_done(match_id, act.player_id, act.heal_amount)
        for iu in turn_result.items_used:
            eff = iu.get("effect", {})
            if eff.get("type") == "heal" and eff.get("actual_healed", 0) > 0:
                track_healing_done(match_id, iu["player_id"], eff["actual_healed"])
        for ip in turn_result.items_picked_up:
            item_count = len(ip.get("items", []))
            if item_count > 0:
                track_items_looted(match_id, ip["player_id"], item_count)
        for uid, unit in all_units.items():
            if unit.is_alive:
                track_turn_survived(match_id, uid, turn_number)

        # Record timeline for Arena Analyst
        record_turn_events(match_id, turn_number, turn_result, all_units)

        # Log turn results (deaths, combat, doors)
        result_lines = log_turn_results(turn_result, all_units, turn_number)
        if result_lines:
            for line in result_lines:
                print(line)
            if log_fh:
                for line in result_lines:
                    # Strip ANSI codes for file output
                    import re
                    clean = re.sub(r'\033\[[0-9;]*m', '', line)
                    log_fh.write(clean + "\n")

        # Compact per-turn summary (always printed — 1 line per turn)
        summary = compact_turn_summary(turn_number, action_list, turn_result, all_units)
        print(summary)

        # Recompute FOV after movement
        for uid, unit in all_units.items():
            if unit.is_alive and not unit.extracted:
                fov = compute_fov(
                    unit.position.x, unit.position.y,
                    unit.vision_range,
                    grid_width, grid_height,
                    obstacles,
                )
                set_fov_cache(match_id, uid, fov)

        # Clear dead players
        for death_pid in turn_result.deaths:
            clear_player_queue(match_id, death_pid)
            clear_auto_target(match_id, death_pid)
            for uid, unit in all_units.items():
                if unit.auto_target_id == death_pid:
                    clear_auto_target(match_id, uid)

        # Show ASCII map periodically
        if show_ascii and turn_number % ascii_every == 0:
            ascii_map = render_ascii_map(map_data, all_units, door_states, turn_number)
            print(ascii_map)
            print(render_team_summary(all_units))
            print()

        # Write movement log to file
        if log_fh and move_lines:
            import re
            for line in move_lines:
                clean = re.sub(r'\033\[[0-9;]*m', '', line)
                log_fh.write(clean + "\n")

        # Check for winner
        if turn_result.winner:
            winner = turn_result.winner
            save_match_report(match_id, winner, turn_number)
            end_match(match_id)
            clear_ai_patrol_state()
            break

    # If max turns reached without winner
    if not winner:
        winner = "draw"
        save_match_report(match_id, "draw", max_turns)
        end_match(match_id)
        clear_ai_patrol_state()

    # Show final map
    if show_ascii:
        all_units = get_match_players(match_id) or all_units
        dungeon_state = get_dungeon_state(match_id)
        ds = dungeon_state["door_states"] if dungeon_state else door_states
        print(f"\n{'═' * 70}")
        print(f"  FINAL STATE — Turn {turn_number}")
        print(f"{'═' * 70}")
        ascii_map = render_ascii_map(map_data, all_units, ds, turn_number)
        print(ascii_map)
        print(render_team_summary(all_units))

    # Build result summary
    result = {
        "match_id": match_id,
        "winner": winner,
        "turns": turn_number if winner != "draw" else max_turns,
        "map": map_id,
        "grid_size": grid_size,
        "theme": match.theme_id,
        "team_a": [getattr(all_units.get(uid), "username", uid) for uid in match.team_a],
        "team_b": [getattr(all_units.get(uid), "username", uid) for uid in match.team_b],
        "team_c": [getattr(all_units.get(uid), "username", uid) for uid in match.team_c],
        "team_d": [getattr(all_units.get(uid), "username", uid) for uid in match.team_d],
        "pve_count": pve_count,
        "movement_decisions": len(movement_log_lines),
    }

    if log_fh:
        log_fh.write(f"\n{'='*60}\n")
        log_fh.write(f"RESULT: {winner} wins in {result['turns']} turns\n")
        log_fh.close()
        print(f"\n  Movement log saved to: {log_file}")

    # Clean up
    remove_match(match_id)

    return result


# ─── Batch Results ───────────────────────────────────────────────────────────

def print_batch_results(results: list[dict]) -> None:
    """Print a summary table of multiple PVPVE match results."""
    total = len(results)
    if not total:
        return

    # Win counts by team
    team_wins = {"team_a": 0, "team_b": 0, "team_c": 0, "team_d": 0, "draw": 0}
    total_turns = 0

    for r in results:
        w = r["winner"]
        team_wins[w] = team_wins.get(w, 0) + 1
        total_turns += r["turns"]

    avg_turns = total_turns / total

    print(f"\n{'═' * 70}")
    print(f"  PVPVE BATCH RESULTS — {total} matches")
    print(f"{'═' * 70}")
    for team_key in ["team_a", "team_b", "team_c", "team_d"]:
        wins = team_wins.get(team_key, 0)
        pct = wins / total * 100
        label = _team_label(team_key.replace("team_", ""))
        print(f"  {label} wins: {wins:>4}  ({pct:.1f}%)")
    draws = team_wins.get("draw", 0)
    print(f"  Draws:         {draws:>4}  ({draws / total * 100:.1f}%)")
    print(f"  Avg turns:     {avg_turns:.1f}")
    print(f"{'═' * 70}")
    print(f"  Reports saved to server/data/match_history/")
    print(f"  View detailed stats in Arena Analyst (start-arena-analyst.bat)")
    print(f"{'═' * 70}")


# ─── CLI Entry Point ─────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Batch PVPVE Simulator — Run headless 4-team dungeon matches with ASCII replay.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python batch_pvpve.py                              # Single XL match with ASCII map
  python batch_pvpve.py --verbose                    # Show every movement decision
  python batch_pvpve.py --grid-size 6 --team-size 3  # Smaller dungeon, 3 per team
  python batch_pvpve.py --matches 10 --no-ascii      # Batch 10 matches, stats only
  python batch_pvpve.py --seed 42 --verbose --log movement.txt
  python batch_pvpve.py --ascii-every 1              # ASCII map every single turn

Grid sizes:
  4  = Small   (32x32 tiles)    — fast, tight corridors
  6  = Large   (48x48 tiles)    — medium, good room variety
  8  = XL      (64x64 tiles)    — full-scale PVPVE dungeon
        """
    )

    parser.add_argument("--matches", type=int, default=1, help="Number of matches to run (default: 1)")
    parser.add_argument("--grid-size", type=int, default=8, help="WFC grid size: 4=S, 6=L, 8=XL (default: 8)")
    parser.add_argument("--team-size", type=int, default=5, help="Heroes per team, 1-5 (default: 5)")
    parser.add_argument("--pve-density", type=float, default=0.5, help="PVE enemy density 0.0-1.0 (default: 0.5)")
    parser.add_argument("--max-turns", type=int, default=300, help="Turn limit (default: 300)")
    parser.add_argument("--seed", type=int, default=None, help="Fixed RNG seed for reproducibility")
    parser.add_argument("--verbose", action="store_true", help="Show every AI decision per turn")
    parser.add_argument("--no-ascii", action="store_true", help="Skip ASCII map (faster for batch runs)")
    parser.add_argument("--ascii-every", type=int, default=5, help="ASCII map interval (default: every 5 turns)")
    parser.add_argument("--log", type=str, default=None, help="Write movement log to file")
    parser.add_argument("--trace-team", type=str, default=None, choices=["a", "b", "c", "d", "pve"],
                        help="Only show verbose decisions for this team")

    args = parser.parse_args()

    # Validate inputs
    args.team_size = max(1, min(5, args.team_size))
    args.grid_size = max(3, min(10, args.grid_size))
    args.pve_density = max(0.0, min(1.0, args.pve_density))

    total = args.matches
    show_ascii = not args.no_ascii

    # For batch runs (>1 match), disable ASCII by default unless --ascii-every was explicitly set
    if total > 1 and not args.no_ascii:
        show_ascii = False

    print(f"\n{'═' * 70}")
    print(f"  BATCH PVPVE DUNGEON SIMULATOR")
    print(f"  {total} match{'es' if total > 1 else ''} | {args.grid_size}x{args.grid_size} grid (XL)")
    print(f"  {args.team_size} heroes per team | PVE density: {args.pve_density}")
    print(f"  Max {args.max_turns} turns | Seed: {args.seed or 'random'}")
    print(f"{'═' * 70}\n")

    results = []
    start_time = time.time()

    for i in range(1, total + 1):
        match_seed = args.seed + i - 1 if args.seed else None

        if total > 1:
            print(f"\n  ── Match {i}/{total} {'─' * 50}")

        result = run_headless_pvpve(
            team_size=args.team_size,
            grid_size=args.grid_size,
            pve_density=args.pve_density,
            max_turns=args.max_turns,
            seed=match_seed,
            verbose=args.verbose,
            show_ascii=show_ascii,
            ascii_every=args.ascii_every,
            log_file=f"{args.log}.{i}" if args.log and total > 1 else args.log,
            trace_team=args.trace_team,
        )

        if result:
            winner_label = result["winner"].replace("team_", "Team ").title()
            elapsed = time.time() - start_time
            print(f"\n  ✓ {winner_label} wins in {result['turns']} turns | {result['movement_decisions']} movement decisions")
            results.append(result)
        else:
            print(f"\n  ✗ Match {i} FAILED")

    total_time = time.time() - start_time

    if results:
        if len(results) > 1:
            print_batch_results(results)
        print(f"\n  Completed in {total_time:.1f}s ({total_time / len(results):.1f}s per match)")
    else:
        print("\n  No matches completed successfully.")


if __name__ == "__main__":
    main()
