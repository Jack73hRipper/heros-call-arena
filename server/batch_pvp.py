"""
Batch PvP Simulator — Headless 5v5 match runner for class balance testing.

Runs the EXACT same game logic as live matches (same maps, FOV, AI decisions,
turn resolution, skills, buffs, pathfinding) but without WebSocket broadcasting.
Produces match reports in the same JSON format that Arena Analyst reads.

Usage:
    python batch_pvp.py --matches 20 --map open_arena_large
    python batch_pvp.py --matches 50 --team-a crusader,confessor,ranger,hexblade,mage --team-b blood_knight,bard,inquisitor,revenant,shaman
    python batch_pvp.py --matches 100 --round-robin --map open_arena
    python batch_pvp.py --matches 30 --mirror --map open_arena_large

Options:
    --matches N         Number of matches to run (default: 100)
    --map MAP_ID        Map to fight on (default: open_arena_large)
    --team-a CLASSES    Comma-separated class IDs for Team A
    --team-b CLASSES    Comma-separated class IDs for Team B
    --max-turns N       Turn limit before declaring a draw (default: 200)
    --round-robin       Run every possible 5v5 comp vs every other (ignores --team-a/b)
    --mirror            Both teams use same random comp each match (tests map balance)
    --randomize         Random comps each match (broad balance sampling)
    --list-classes      Show available class IDs and exit
    --list-maps         Show available map IDs and exit

Match reports are saved to server/data/match_history/ and immediately
visible in Arena Analyst (start-arena-analyst.bat).
"""

from __future__ import annotations

import argparse
import os
import sys
import time
import random
from itertools import combinations

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
from app.core.map_loader import get_obstacles_with_door_states, load_map, is_dungeon_map
from app.core.fov import compute_fov
from app.core.ai_behavior import run_ai_decisions, clear_ai_patrol_state
from app.models.player import get_all_classes


def list_available_classes() -> list[str]:
    """Return sorted list of all class IDs."""
    return sorted(get_all_classes().keys())


def list_available_maps() -> list[str]:
    """Return list of map IDs from configs/maps/."""
    maps_dir = os.path.join(os.path.dirname(__file__), "configs", "maps")
    maps = []
    for f in os.listdir(maps_dir):
        if f.endswith(".json"):
            maps.append(f.replace(".json", ""))
    return sorted(maps)


def run_headless_match(
    team_a_classes: list[str],
    team_b_classes: list[str],
    map_id: str = "open_arena_large",
    max_turns: int = 200,
) -> dict | None:
    """Run a single headless 5v5 match and save the report.

    Uses the exact same game systems as a live match:
    - Real map geometry and obstacles
    - Real FOV computation with shared team vision
    - Real AI decision engine (pathfinding, skills, targeting, stances)
    - Real turn resolution (movement, combat, skills, buffs, deaths)
    - Real combat stats tracking and timeline recording

    Returns the match summary dict, or None on failure.
    """
    team_size_a = len(team_a_classes)
    team_size_b = len(team_b_classes)

    # Create match with all AI units
    config = MatchConfig(
        map_id=map_id,
        match_type=MatchType.PVP,
        tick_rate=1.0,
        max_players=team_size_a + team_size_b + 1,
        ai_opponents=team_size_b,
        ai_allies=team_size_a,
        ai_opponent_classes=list(team_b_classes),
        ai_ally_classes=list(team_a_classes),
    )

    # Create match with a dummy host (required by match_manager)
    match, host = create_match("BatchSim", config=config)
    match_id = match.match_id

    # The host is a required dummy for match creation — remove it before start
    # so it never appears in match data or reports.
    host.is_ready = True

    # Start the match (resolves spawns, applies stats, sets IN_PROGRESS)
    started = start_match(match_id)
    if not started:
        print(f"  [ERROR] Failed to start match {match_id}")
        remove_match(match_id)
        return None

    # Remove the dummy host from all match state so it doesn't appear in reports
    host_id = host.player_id
    all_units = get_match_players(match_id)
    all_units.pop(host_id, None)
    if host_id in match.player_ids:
        match.player_ids.remove(host_id)
    if host_id in match.team_a:
        match.team_a.remove(host_id)

    # Convert ai_allies (Team A) from stance-based hero AI to independent AI.
    # ai_allies are created with hero_id + ai_stance="follow" (designed to
    # follow a human owner), but in headless batch mode the dummy host was
    # removed above — leaving them with no owner.  Without this conversion
    # they return WAIT every turn because _find_owner() returns None.
    for uid in list(match.team_a):
        unit = all_units.get(uid)
        if unit and unit.hero_id:
            unit.hero_id = None
            unit.ai_stance = None
            unit.ai_behavior = "aggressive"

    # Load map data once
    map_data = load_map(map_id)
    grid_width = map_data.get("width", 15)
    grid_height = map_data.get("height", 15)

    winner = None

    # --- Main tick loop (synchronous, no WebSocket) ---
    for turn in range(1, max_turns + 1):
        match = get_match(match_id)
        if not match or match.status != "in_progress":
            break

        turn_number = increment_turn(match_id)
        all_units = get_match_players(match_id)
        team_a, team_b, team_c, team_d = get_match_teams(match_id)
        ai_ids = get_ai_ids(match_id)

        # Dungeon state (None for arena maps)
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
        )

        # Step 3: No human actions to pop (all AI match)
        action_list = list(ai_actions)

        # Step 4: Resolve the turn (PURE game logic)
        use_teams = bool(team_a or team_b or team_c or team_d)
        match_is_dungeon = is_dungeon_map(map_id) or (match.config.match_type in ("dungeon", "pvpve"))

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
            floor_number=getattr(match, 'current_floor', 1),
            match_state=match,
        )

        # Step 4.5: Track combat stats
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

        # Step 4.6: Record timeline events for Arena Analyst
        record_turn_events(match_id, turn_number, turn_result, all_units)

        # Step 5: Recompute FOV after movement
        for uid, unit in all_units.items():
            if unit.is_alive and not unit.extracted:
                fov = compute_fov(
                    unit.position.x, unit.position.y,
                    unit.vision_range,
                    grid_width, grid_height,
                    obstacles,
                )
                set_fov_cache(match_id, uid, fov)

        # Clear dead players' queues and auto-targets
        for death_pid in turn_result.deaths:
            clear_player_queue(match_id, death_pid)
            clear_auto_target(match_id, death_pid)
            for uid, unit in all_units.items():
                if unit.auto_target_id == death_pid:
                    clear_auto_target(match_id, uid)

        # Check for winner
        if turn_result.winner:
            winner = turn_result.winner
            save_match_report(match_id, winner, turn_number)
            end_match(match_id)
            clear_ai_patrol_state()
            break

    # If max turns reached without winner, declare draw
    if not winner:
        winner = "draw"
        save_match_report(match_id, "draw", max_turns)
        end_match(match_id)
        clear_ai_patrol_state()

    # Build result summary
    result = {
        "match_id": match_id,
        "winner": winner,
        "turns": turn_number if winner != "draw" else max_turns,
        "team_a": team_a_classes,
        "team_b": team_b_classes,
        "map": map_id,
    }

    # Clean up in-memory state for this match
    remove_match(match_id)

    return result


def generate_round_robin_matchups(classes: list[str], team_size: int = 5) -> list[tuple[list[str], list[str]]]:
    """Generate all unique team composition matchups.

    For 11 classes with 5v5, this creates all (11 choose 5) = 462 possible
    team compositions, paired against each other. That's 462*461/2 = 106,491
    unique matchups — far too many. Instead, we generate every comp paired
    against every OTHER comp, but deduplicated (A vs B == B vs A).

    For practical use, we limit to each unique comp vs a reasonable sample.
    """
    all_comps = list(combinations(classes, team_size))
    matchups = []
    for i, comp_a in enumerate(all_comps):
        for comp_b in all_comps[i:]:  # Include mirror matches (i, not i+1)
            matchups.append((sorted(comp_a), sorted(comp_b)))
    return matchups


def print_results_table(results: list[dict], classes: list[str]) -> None:
    """Print a summary table of batch results."""
    # Aggregate per-class stats
    class_wins = {c: 0 for c in classes}
    class_losses = {c: 0 for c in classes}
    class_draws = {c: 0 for c in classes}
    class_appearances = {c: 0 for c in classes}

    team_a_wins = 0
    team_b_wins = 0
    draws = 0

    for r in results:
        winner = r["winner"]
        if winner == "team_a":
            team_a_wins += 1
            for c in r["team_a"]:
                class_wins[c] = class_wins.get(c, 0) + 1
            for c in r["team_b"]:
                class_losses[c] = class_losses.get(c, 0) + 1
        elif winner == "team_b":
            team_b_wins += 1
            for c in r["team_b"]:
                class_wins[c] = class_wins.get(c, 0) + 1
            for c in r["team_a"]:
                class_losses[c] = class_losses.get(c, 0) + 1
        else:
            draws += 1
            for c in r["team_a"] + r["team_b"]:
                class_draws[c] = class_draws.get(c, 0) + 1

        for c in r["team_a"] + r["team_b"]:
            class_appearances[c] = class_appearances.get(c, 0) + 1

    total = len(results)
    avg_turns = sum(r["turns"] for r in results) / total if total else 0

    print("\n" + "=" * 70)
    print(f"  BATCH PVP RESULTS — {total} matches on {results[0]['map']}")
    print("=" * 70)
    print(f"  Team A wins: {team_a_wins:>4}  ({team_a_wins/total*100:.1f}%)")
    print(f"  Team B wins: {team_b_wins:>4}  ({team_b_wins/total*100:.1f}%)")
    print(f"  Draws:       {draws:>4}  ({draws/total*100:.1f}%)")
    print(f"  Avg turns:   {avg_turns:.1f}")
    print()

    # Per-class win rates
    active_classes = [c for c in classes if class_appearances.get(c, 0) > 0]
    if active_classes:
        print(f"  {'Class':<16} {'Games':>6} {'Wins':>6} {'Losses':>6} {'Win%':>7}")
        print(f"  {'-'*16} {'-'*6} {'-'*6} {'-'*6} {'-'*7}")
        for c in sorted(active_classes, key=lambda x: class_wins.get(x, 0) / max(class_appearances.get(x, 1), 1), reverse=True):
            apps = class_appearances[c]
            wins = class_wins[c]
            losses = class_losses[c]
            wr = (wins / apps * 100) if apps > 0 else 0
            print(f"  {c:<16} {apps:>6} {wins:>6} {losses:>6} {wr:>6.1f}%")

    print("=" * 70)
    print(f"  Reports saved to server/data/match_history/")
    print(f"  View detailed stats in Arena Analyst (start-arena-analyst.bat)")
    print("=" * 70)


def main():
    parser = argparse.ArgumentParser(
        description="Batch PvP Simulator — Run headless 5v5 matches for class balance testing.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python batch_pvp.py --matches 20
  python batch_pvp.py --matches 50 --team-a crusader,confessor,ranger,hexblade,mage --team-b blood_knight,bard,inquisitor,revenant,shaman
  python batch_pvp.py --matches 100 --randomize --map open_arena
  python batch_pvp.py --matches 30 --mirror
  python batch_pvp.py --round-robin --map open_arena_large

Available classes: %(classes)s
Available maps: %(maps)s
        """ % {
            "classes": ", ".join(list_available_classes()),
            "maps": ", ".join(list_available_maps()),
        }
    )

    parser.add_argument("--matches", type=int, default=100, help="Number of matches to run (default: 100)")
    parser.add_argument("--map", type=str, default="open_arena_large", help="Map ID (default: open_arena_large)")
    parser.add_argument("--team-a", type=str, default=None, help="Comma-separated class IDs for Team A")
    parser.add_argument("--team-b", type=str, default=None, help="Comma-separated class IDs for Team B")
    parser.add_argument("--max-turns", type=int, default=200, help="Turn limit before draw (default: 200)")
    parser.add_argument("--round-robin", action="store_true", help="Run every comp vs every comp")
    parser.add_argument("--mirror", action="store_true", help="Both teams use same random comp each match")
    parser.add_argument("--randomize", action="store_true", help="Random comps each match")
    parser.add_argument("--list-classes", action="store_true", help="Show available classes and exit")
    parser.add_argument("--list-maps", action="store_true", help="Show available maps and exit")

    args = parser.parse_args()

    all_classes = list_available_classes()

    if args.list_classes:
        print("Available classes:")
        for c in all_classes:
            print(f"  {c}")
        return

    if args.list_maps:
        print("Available maps:")
        for m in list_available_maps():
            print(f"  {m}")
        return

    # Validate map
    available_maps = list_available_maps()
    if args.map not in available_maps:
        print(f"Error: Unknown map '{args.map}'. Available: {', '.join(available_maps)}")
        sys.exit(1)

    # Build matchup list
    matchups: list[tuple[list[str], list[str]]] = []

    if args.round_robin:
        print(f"Generating round-robin matchups for {len(all_classes)} classes...")
        all_matchups = generate_round_robin_matchups(all_classes, 5)
        # If --matches specified, sample that many; otherwise run all
        if args.matches and args.matches < len(all_matchups):
            matchups = random.sample(all_matchups, args.matches)
        else:
            matchups = all_matchups
        print(f"  {len(matchups)} matchups selected")

    elif args.team_a and args.team_b:
        # Fixed composition
        team_a = [c.strip() for c in args.team_a.split(",")]
        team_b = [c.strip() for c in args.team_b.split(",")]

        # Validate classes
        for c in team_a + team_b:
            if c not in all_classes:
                print(f"Error: Unknown class '{c}'. Available: {', '.join(all_classes)}")
                sys.exit(1)

        matchups = [(team_a, team_b)] * args.matches

    elif args.mirror:
        # Mirror mode: same random comp on both sides
        for _ in range(args.matches):
            comp = sorted(random.sample(all_classes, 5))
            matchups.append((comp, comp))

    elif args.randomize:
        # Random comps each match
        for _ in range(args.matches):
            team_a = sorted(random.sample(all_classes, 5))
            team_b = sorted(random.sample(all_classes, 5))
            matchups.append((team_a, team_b))

    else:
        # Default: random comps
        for _ in range(args.matches):
            team_a = sorted(random.sample(all_classes, 5))
            team_b = sorted(random.sample(all_classes, 5))
            matchups.append((team_a, team_b))

    total = len(matchups)
    print(f"\n{'='*70}")
    print(f"  BATCH PVP SIMULATOR")
    print(f"  {total} matches on {args.map} | Max {args.max_turns} turns each")
    print(f"{'='*70}\n")

    results = []
    start_time = time.time()

    for i, (team_a, team_b) in enumerate(matchups, 1):
        a_str = ",".join(team_a)
        b_str = ",".join(team_b)
        print(f"  [{i}/{total}] {a_str}  vs  {b_str}", end="", flush=True)

        match_start = time.time()
        result = run_headless_match(team_a, team_b, args.map, args.max_turns)
        elapsed = time.time() - match_start

        if result:
            winner_label = result["winner"].replace("team_", "Team ").title()
            print(f"  → {winner_label} in {result['turns']} turns ({elapsed:.1f}s)")
            results.append(result)
        else:
            print(f"  → FAILED")

    total_time = time.time() - start_time

    if results:
        print_results_table(results, all_classes)
        print(f"\n  Completed in {total_time:.1f}s ({total_time/len(results):.1f}s per match)")
    else:
        print("\n  No matches completed successfully.")


if __name__ == "__main__":
    main()
