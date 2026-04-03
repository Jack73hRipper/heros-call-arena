"""
PVPVE Agent Mode — Copilot plays as Team A leader with 4 AI companions.

Runs the EXACT same PVPVE game logic as batch_pvpve.py, but instead of AI
controlling Team A's leader, it writes game state to a JSON file and waits
for an action response from the Copilot agent (via file I/O).

Communication protocol:
    1. Script writes  server/agent_turn/state.json   (game state + briefing)
    2. Script polls   server/agent_turn/action.json   (agent's decision)
    3. Agent (Copilot) reads state.json, analyzes, writes action.json
    4. Script picks up action, resolves the turn, repeats

Team A: 1 agent-controlled leader + 4 AI followers (follow stance)
Teams B/C/D: Full AI teams (5 each)
PVE: Monster enemies with rarity system

Usage:
    python batch_pvpve_agent.py
    python batch_pvpve_agent.py --grid-size 6 --max-turns 150
    python batch_pvpve_agent.py --team-size 3 --class crusader
    python batch_pvpve_agent.py --seed 12345
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import random
import shutil

# Windows UTF-8 console fix
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    try:
        import ctypes
        ctypes.windll.kernel32.SetConsoleOutputCP(65001)
        ctypes.windll.kernel32.SetConsoleCP(65001)
    except Exception:
        pass

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
    set_fov_cache,
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
    clear_auto_target,
    clear_player_queue,
)
from app.core.turn_resolver import resolve_turn
from app.core.map_loader import load_map, get_obstacles_with_door_states
from app.core.fov import compute_fov
from app.core.ai_behavior import run_ai_decisions, clear_ai_patrol_state
from app.core.ai_exploration import (
    get_exploration_progress,
    update_room_discovery,
    update_room_clearance,
    get_next_exploration_target,
)
from app.models.player import get_all_classes, get_class_definition
from app.core.ai_pathfinding import get_next_step_toward
from app.core.fov import has_line_of_sight

# Re-use rendering functions from batch_pvpve
from batch_pvpve import (
    render_ascii_map,
    render_team_summary,
    compact_turn_summary,
    log_turn_results,
    _team_label,
    TEAM_COLORS,
    BOLD,
    RESET,
)


# ─── Agent Communication ────────────────────────────────────────────────────

AGENT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "agent_turn")
STATE_FILE = os.path.join(AGENT_DIR, "state.json")
ACTION_FILE = os.path.join(AGENT_DIR, "action.json")
LOG_FILE = os.path.join(AGENT_DIR, "game_log.json")


def _ensure_agent_dir():
    """Create agent communication directory if needed."""
    os.makedirs(AGENT_DIR, exist_ok=True)
    # Clean up any stale files from previous runs
    for f in (STATE_FILE, ACTION_FILE):
        if os.path.exists(f):
            os.remove(f)


def _get_walkable_neighbors(x: int, y: int, obstacles: set, grid_w: int, grid_h: int) -> list[tuple[int, int]]:
    """Return all walkable cardinal + diagonal neighbors."""
    neighbors = []
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            if dx == 0 and dy == 0:
                continue
            nx, ny = x + dx, y + dy
            if 0 <= nx < grid_w and 0 <= ny < grid_h and (nx, ny) not in obstacles:
                neighbors.append((nx, ny))
    return neighbors


def _get_adjacent_doors(x: int, y: int, door_tiles: set | None) -> list[tuple[int, int]]:
    """Return all closed door tiles Chebyshev-adjacent to (x, y)."""
    if not door_tiles:
        return []
    doors = []
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            if dx == 0 and dy == 0:
                continue
            nb = (x + dx, y + dy)
            if nb in door_tiles:
                doors.append(nb)
    return doors


def _manhattan(a: tuple[int, int], b: tuple[int, int]) -> int:
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def _chebyshev(a: tuple[int, int], b: tuple[int, int]) -> int:
    return max(abs(a[0] - b[0]), abs(a[1] - b[1]))


def _render_local_ascii(
    map_data: dict,
    all_units: dict,
    door_states: dict | None,
    center_x: int,
    center_y: int,
    radius: int = 10,
) -> str:
    """Render a local ASCII map centered on the agent's position."""
    tiles = map_data.get("tiles", [])
    tile_legend = map_data.get("tile_legend", {})
    width = map_data.get("width", 0)
    height = map_data.get("height", 0)

    x_min = max(0, center_x - radius)
    x_max = min(width, center_x + radius + 1)
    y_min = max(0, center_y - radius)
    y_max = min(height, center_y + radius + 1)

    # Build tile grid
    grid = []
    for y in range(y_min, y_max):
        row = []
        for x in range(x_min, x_max):
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

    # Override door states
    if door_states:
        for key, state in door_states.items():
            parts = key.split(",")
            if len(parts) == 2:
                dx, dy = int(parts[0]), int(parts[1])
                gy = dy - y_min
                gx = dx - x_min
                if 0 <= gy < len(grid) and 0 <= gx < len(grid[0]):
                    grid[gy][gx] = "d" if state == "open" else "D"

    # Place units
    for uid, unit in all_units.items():
        ux, uy = unit.position.x, unit.position.y
        gx = ux - x_min
        gy = uy - y_min
        if 0 <= gy < len(grid) and 0 <= gx < len(grid[0]):
            team = getattr(unit, "team", "?")
            if not unit.is_alive:
                grid[gy][gx] = "*"
            elif ux == center_x and uy == center_y:
                grid[gy][gx] = "@"  # The agent
            elif team in ("a", "b", "c", "d"):
                grid[gy][gx] = team.upper()
            elif team == "pve":
                grid[gy][gx] = "e"

    # Build string with coordinate markers
    lines = []
    # Column headers
    header = "    "
    for x in range(x_min, x_max):
        if x % 5 == 0:
            header += f"{x:<2}"
        else:
            header += "  "
    lines.append(header)

    for i, y in enumerate(range(y_min, y_max)):
        row_str = f"{y:>3} "
        for j, x in enumerate(range(x_min, x_max)):
            ch = grid[i][j]
            row_str += ch + " "
        lines.append(row_str)

    lines.append("")
    lines.append("Legend: @=YOU  A/B/C/D=hero teams  e=enemy  #=wall  D=door(closed)  d=door(open)  C=chest  >=stairs  *=dead")

    return "\n".join(lines)


def build_game_state(
    agent_id: str,
    all_units: dict,
    obstacles: set,
    door_tiles: set | None,
    team_fov: set,
    grid_width: int,
    grid_height: int,
    map_data: dict,
    door_states: dict | None,
    chest_states: dict | None,
    ground_items: dict | None,
    match_id: str,
    match_state,
    turn_number: int,
    max_turns: int,
    recent_events: list[str],
) -> dict:
    """Build the complete game state JSON for the agent to read."""
    agent = all_units[agent_id]
    ax, ay = agent.position.x, agent.position.y

    # ── My unit ──
    skills_available = []
    class_skills = []
    if agent.class_id:
        from app.core.skills import load_skills_config
        config = load_skills_config()
        class_skills = config.get("class_skills", {}).get(agent.class_id, [])
        all_skills = config.get("skills", {})
        for sid in class_skills:
            sdata = all_skills.get(sid, {})
            cd_remaining = agent.cooldowns.get(sid, 0) if agent.cooldowns else 0
            skills_available.append({
                "skill_id": sid,
                "name": sdata.get("name", sid),
                "description": sdata.get("description", ""),
                "damage": sdata.get("damage", 0),
                "heal": sdata.get("heal_amount", 0),
                "range": sdata.get("range", 1),
                "cooldown": sdata.get("cooldown", 0),
                "cooldown_remaining": cd_remaining,
                "ready": cd_remaining <= 0,
                "aoe_radius": sdata.get("aoe_radius", 0),
                "buff": sdata.get("buff", None),
                "dot": sdata.get("dot", None),
                "target_type": sdata.get("target_type", "enemy"),
            })

    # Inventory summary
    inventory = []
    for idx, item in enumerate(agent.inventory or []):
        if item:
            inventory.append({
                "index": idx,
                "name": item.get("name", "Unknown"),
                "item_type": item.get("item_type", ""),
                "rarity": item.get("rarity", "common"),
                "consumable_effect": item.get("consumable_effect", None),
            })

    # Equipment summary
    equipment = {}
    for slot, item in (agent.equipment or {}).items():
        if item:
            equipment[slot] = {
                "name": item.get("name", "Unknown"),
                "rarity": item.get("rarity", "common"),
                "slot": slot,
            }

    # Active buffs
    buffs = []
    for b in (agent.active_buffs or []):
        buffs.append({
            "buff_id": b.get("buff_id", "?"),
            "stat": b.get("stat", ""),
            "magnitude": b.get("magnitude", 0),
            "turns_remaining": b.get("turns_remaining", 0),
        })

    my_unit = {
        "id": agent_id,
        "name": agent.username,
        "class": agent.class_id,
        "hp": agent.hp,
        "max_hp": agent.max_hp,
        "position": {"x": ax, "y": ay},
        "attack_damage": agent.attack_damage,
        "ranged_damage": getattr(agent, "ranged_damage", 0),
        "armor": agent.armor,
        "vision_range": agent.vision_range,
        "ranged_range": getattr(agent, "ranged_range", 5),
        "crit_chance": getattr(agent, "crit_chance", 0),
        "dodge_chance": getattr(agent, "dodge_chance", 0),
        "skills": skills_available,
        "cooldowns": dict(agent.cooldowns) if agent.cooldowns else {},
        "inventory": inventory,
        "equipment": equipment,
        "buffs": buffs,
    }

    # ── Allies ──
    allies = []
    for uid, unit in all_units.items():
        if uid == agent_id:
            continue
        if not unit.is_alive:
            continue
        if getattr(unit, "team", "") != "a":
            continue
        allies.append({
            "id": uid,
            "name": unit.username,
            "class": unit.class_id,
            "hp": unit.hp,
            "max_hp": unit.max_hp,
            "position": {"x": unit.position.x, "y": unit.position.y},
            "distance": _manhattan((ax, ay), (unit.position.x, unit.position.y)),
            "stance": getattr(unit, "ai_stance", "follow"),
        })
    allies.sort(key=lambda a: a["distance"])

    # ── Visible enemies ──
    visible_enemies = []
    for uid, unit in all_units.items():
        if not unit.is_alive:
            continue
        team = getattr(unit, "team", "")
        if team == "a":
            continue  # Skip allies
        pos = (unit.position.x, unit.position.y)
        if pos not in team_fov:
            continue  # Not visible
        dist = _manhattan((ax, ay), pos)
        cheb_dist = _chebyshev((ax, ay), pos)
        enemy_info = {
            "id": uid,
            "name": unit.username,
            "class": unit.class_id or "",
            "team": team,
            "hp": unit.hp,
            "max_hp": unit.max_hp,
            "position": {"x": unit.position.x, "y": unit.position.y},
            "manhattan_distance": dist,
            "chebyshev_distance": cheb_dist,
            "melee_reachable": cheb_dist <= 1,
            "ranged_reachable": dist <= getattr(agent, "ranged_range", 5),
            "rarity": getattr(unit, "rarity", "normal"),
        }
        # Affix info if present
        affixes = getattr(unit, "affixes", None)
        if affixes:
            enemy_info["affixes"] = affixes
        visible_enemies.append(enemy_info)
    visible_enemies.sort(key=lambda e: e["manhattan_distance"])

    # ── Hostile hero teams visible ──
    hostile_heroes = [e for e in visible_enemies if e["team"] in ("b", "c", "d")]
    pve_enemies = [e for e in visible_enemies if e["team"] == "pve"]

    # ── Available actions ──
    available_actions = {}

    # MOVE targets
    move_targets = _get_walkable_neighbors(ax, ay, obstacles, grid_width, grid_height)
    # Exclude tiles occupied by alive units
    occupied = set()
    for uid, unit in all_units.items():
        if unit.is_alive and uid != agent_id:
            occupied.add((unit.position.x, unit.position.y))
    move_targets = [t for t in move_targets if t not in occupied]
    available_actions["MOVE"] = [{"x": t[0], "y": t[1]} for t in move_targets]

    # ATTACK targets (melee — Chebyshev distance 1)
    melee_targets = [e for e in visible_enemies if e["melee_reachable"]]
    available_actions["ATTACK"] = [{"id": e["id"], "name": e["name"], "hp": e["hp"]} for e in melee_targets]

    # RANGED_ATTACK targets
    ranged_range = getattr(agent, "ranged_range", 5)
    ranged_targets = [e for e in visible_enemies if e["manhattan_distance"] <= ranged_range and not e["melee_reachable"]]
    available_actions["RANGED_ATTACK"] = [{"id": e["id"], "name": e["name"], "hp": e["hp"], "distance": e["manhattan_distance"]} for e in ranged_targets]

    # SKILL options (off cooldown)
    ready_skills = [s for s in skills_available if s["ready"] and s["skill_id"] not in ("auto_attack_melee", "auto_attack_ranged")]
    available_actions["SKILL"] = ready_skills

    # INTERACT (adjacent doors)
    adj_doors = _get_adjacent_doors(ax, ay, door_tiles)
    available_actions["INTERACT"] = [{"x": d[0], "y": d[1], "type": "door"} for d in adj_doors]

    # USE_ITEM (potions in inventory)
    potions = [it for it in inventory if it.get("consumable_effect")]
    available_actions["USE_ITEM"] = potions

    # LOOT (ground items at current position)
    loot_here = []
    pos_key = f"{ax},{ay}"
    if ground_items and pos_key in ground_items:
        for item in ground_items[pos_key]:
            loot_here.append({
                "name": item.get("name", "Unknown"),
                "rarity": item.get("rarity", "common"),
            })
    available_actions["LOOT"] = loot_here

    # WAIT always available
    available_actions["WAIT"] = True

    # ── Nearby chests ──
    nearby_chests = []
    if chest_states:
        for key, state in chest_states.items():
            parts = key.split(",")
            if len(parts) == 2:
                cx, cy = int(parts[0]), int(parts[1])
                dist = _manhattan((ax, ay), (cx, cy))
                if dist <= 12:
                    nearby_chests.append({
                        "position": {"x": cx, "y": cy},
                        "state": state,
                        "distance": dist,
                    })
    nearby_chests.sort(key=lambda c: c["distance"])

    # ── Exploration progress ──
    exploration = get_exploration_progress(match_id, "a")
    explore_target = get_next_exploration_target(match_id, "a", (ax, ay))
    exploration_info = {
        "discovered_rooms": exploration.get("discovered_rooms", 0),
        "total_rooms": exploration.get("total_rooms", 0),
        "cleared_rooms": exploration.get("cleared_rooms", 0),
        "exploration_pct": exploration.get("exploration_pct", 0),
        "clearance_pct": exploration.get("clearance_pct", 0),
    }
    if explore_target:
        exploration_info["next_target"] = {
            "room_id": explore_target["room_id"],
            "entrance": {"x": explore_target["entrance"][0], "y": explore_target["entrance"][1]},
            "distance": _manhattan((ax, ay), explore_target["entrance"]),
        }

    # ── Local ASCII map ──
    local_map = _render_local_ascii(map_data, all_units, door_states, ax, ay, radius=10)

    # ── Team health summary ──
    team_summary = {}
    for tk in ("a", "b", "c", "d", "pve"):
        members = [u for u in all_units.values() if getattr(u, "team", "") == tk]
        alive = [u for u in members if u.is_alive]
        team_summary[tk] = {
            "alive": len(alive),
            "total": len(members),
            "total_hp": sum(u.hp for u in alive),
        }

    # ── Text briefing (human-readable summary) ──
    briefing_lines = []
    briefing_lines.append(f"═══ TURN {turn_number}/{max_turns} ═══")
    briefing_lines.append(f"You are {agent.username} ({agent.class_id}) at ({ax},{ay})")
    briefing_lines.append(f"HP: {agent.hp}/{agent.max_hp} | Armor: {agent.armor} | ATK: {agent.attack_damage} | RATK: {getattr(agent, 'ranged_damage', 0)}")
    briefing_lines.append("")

    if allies:
        briefing_lines.append(f"ALLIES ({len(allies)} alive, following you):")
        for a in allies:
            briefing_lines.append(f"  {a['name']} ({a['class']}) HP:{a['hp']}/{a['max_hp']} at ({a['position']['x']},{a['position']['y']}) dist:{a['distance']}")
    else:
        briefing_lines.append("ALLIES: None alive!")

    briefing_lines.append("")

    if visible_enemies:
        briefing_lines.append(f"VISIBLE ENEMIES ({len(visible_enemies)}):")
        for e in visible_enemies[:10]:
            threat = "MELEE RANGE!" if e["melee_reachable"] else (f"ranged range ({e['manhattan_distance']})" if e["ranged_reachable"] else f"dist:{e['manhattan_distance']}")
            rarity_tag = f" [{e['rarity']}]" if e.get("rarity", "normal") != "normal" else ""
            affix_tag = f" affixes:{e.get('affixes', [])}" if e.get("affixes") else ""
            briefing_lines.append(f"  {e['name']}{rarity_tag} ({e['team']}) HP:{e['hp']}/{e['max_hp']} — {threat}{affix_tag}")
        if len(visible_enemies) > 10:
            briefing_lines.append(f"  ... and {len(visible_enemies)-10} more")
    else:
        briefing_lines.append("VISIBLE ENEMIES: None")

    briefing_lines.append("")

    briefing_lines.append("READY SKILLS:")
    for s in skills_available:
        status = "READY" if s["ready"] else f"CD:{s['cooldown_remaining']}"
        desc = s.get("description", "")[:60]
        briefing_lines.append(f"  {s['skill_id']}: {s['name']} — {desc} [{status}]")

    briefing_lines.append("")

    briefing_lines.append("AVAILABLE ACTIONS:")
    if melee_targets:
        briefing_lines.append(f"  ATTACK: {', '.join(e['name'] for e in melee_targets)}")
    if ranged_targets:
        ra_parts = [f"{e['name']}(d:{e['manhattan_distance']})" for e in ranged_targets]
        briefing_lines.append(f"  RANGED_ATTACK: {', '.join(ra_parts)}")
    if ready_skills:
        briefing_lines.append(f"  SKILL: {', '.join(s['skill_id'] for s in ready_skills)}")
    if adj_doors:
        briefing_lines.append(f"  INTERACT: doors at {adj_doors}")
    if potions:
        briefing_lines.append(f"  USE_ITEM: {', '.join(p['name'] for p in potions)}")
    if loot_here:
        briefing_lines.append(f"  LOOT: {', '.join(it['name'] for it in loot_here)}")
    briefing_lines.append(f"  MOVE: {len(move_targets)} walkable tiles nearby")
    briefing_lines.append("  WAIT: always available")

    briefing_lines.append("")
    briefing_lines.append(f"EXPLORATION: {exploration_info['discovered_rooms']}/{exploration_info['total_rooms']} rooms discovered ({exploration_info['exploration_pct']:.0f}%)")
    if exploration_info.get("next_target"):
        nt = exploration_info["next_target"]
        briefing_lines.append(f"  Next unexplored room: {nt['room_id']} — entrance at ({nt['entrance']['x']},{nt['entrance']['y']}) dist:{nt['distance']}")

    briefing_lines.append("")
    briefing_lines.append("SCOREBOARD:")
    for tk in ("a", "b", "c", "d"):
        ts = team_summary.get(tk, {})
        briefing_lines.append(f"  Team {tk.upper()}: {ts.get('alive', 0)}/{ts.get('total', 0)} alive, {ts.get('total_hp', 0)} HP")
    pve_s = team_summary.get("pve", {})
    briefing_lines.append(f"  PVE: {pve_s.get('alive', 0)}/{pve_s.get('total', 0)} alive")

    if recent_events:
        briefing_lines.append("")
        briefing_lines.append("RECENT EVENTS:")
        for ev in recent_events[-8:]:
            briefing_lines.append(f"  {ev}")

    briefing = "\n".join(briefing_lines)

    return {
        "turn": turn_number,
        "max_turns": max_turns,
        "my_unit": my_unit,
        "allies": allies,
        "visible_enemies": visible_enemies,
        "hostile_heroes": hostile_heroes,
        "pve_enemies": pve_enemies,
        "available_actions": available_actions,
        "nearby_chests": nearby_chests,
        "exploration": exploration_info,
        "team_summary": team_summary,
        "local_map": local_map,
        "briefing": briefing,
        "recent_events": recent_events[-8:],
    }


def write_state(state: dict):
    """Write game state for the agent to read."""
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)


def wait_for_action(turn: int, timeout: int = 300) -> dict | None:
    """Poll for the agent's action file. Returns parsed action or None on timeout."""
    # Remove stale action file
    if os.path.exists(ACTION_FILE):
        os.remove(ACTION_FILE)

    print(f"\n  ⏳ Waiting for agent action... (write to agent_turn/action.json)")
    print(f"     State written to agent_turn/state.json")

    start = time.time()
    dots = 0
    while time.time() - start < timeout:
        if os.path.exists(ACTION_FILE):
            time.sleep(0.2)  # Brief delay to ensure file is fully written
            try:
                with open(ACTION_FILE, "r", encoding="utf-8") as f:
                    action = json.load(f)
                os.remove(ACTION_FILE)  # Clean up
                return action
            except (json.JSONDecodeError, IOError) as e:
                print(f"  ⚠ Error reading action file: {e} — retrying...")
                time.sleep(0.5)
                continue
        time.sleep(0.5)
        dots += 1
        if dots % 10 == 0:  # Print reminder every 5 seconds
            elapsed = int(time.time() - start)
            print(f"  ⏳ Still waiting... ({elapsed}s / {timeout}s timeout)")

    print(f"  ⏰ Timeout after {timeout}s — using WAIT action")
    return None


def parse_agent_action(agent_id: str, action_data: dict | None) -> PlayerAction:
    """Convert the agent's JSON action into a PlayerAction."""
    if not action_data:
        return PlayerAction(
            player_id=agent_id,
            action_type=ActionType.WAIT,
            reason="agent_timeout",
        )

    action_type_str = action_data.get("action", "WAIT").upper()
    reasoning = action_data.get("reasoning", "")

    if action_type_str == "MOVE":
        return PlayerAction(
            player_id=agent_id,
            action_type=ActionType.MOVE,
            target_x=action_data.get("target_x"),
            target_y=action_data.get("target_y"),
            reason=f"agent: {reasoning}" if reasoning else "agent_move",
        )
    elif action_type_str == "ATTACK":
        return PlayerAction(
            player_id=agent_id,
            action_type=ActionType.ATTACK,
            target_id=action_data.get("target_id"),
            reason=f"agent: {reasoning}" if reasoning else "agent_attack",
        )
    elif action_type_str == "RANGED_ATTACK":
        return PlayerAction(
            player_id=agent_id,
            action_type=ActionType.RANGED_ATTACK,
            target_id=action_data.get("target_id"),
            reason=f"agent: {reasoning}" if reasoning else "agent_ranged",
        )
    elif action_type_str == "SKILL":
        return PlayerAction(
            player_id=agent_id,
            action_type=ActionType.SKILL,
            skill_id=action_data.get("skill_id"),
            target_x=action_data.get("target_x"),
            target_y=action_data.get("target_y"),
            target_id=action_data.get("target_id"),
            reason=f"agent: {reasoning}" if reasoning else "agent_skill",
        )
    elif action_type_str == "INTERACT":
        return PlayerAction(
            player_id=agent_id,
            action_type=ActionType.INTERACT,
            target_x=action_data.get("target_x"),
            target_y=action_data.get("target_y"),
            reason=f"agent: {reasoning}" if reasoning else "agent_interact",
        )
    elif action_type_str == "USE_ITEM":
        return PlayerAction(
            player_id=agent_id,
            action_type=ActionType.USE_ITEM,
            target_x=action_data.get("index", action_data.get("target_x")),
            reason=f"agent: {reasoning}" if reasoning else "agent_use_item",
        )
    elif action_type_str == "LOOT":
        return PlayerAction(
            player_id=agent_id,
            action_type=ActionType.LOOT,
            target_x=action_data.get("target_x"),
            target_y=action_data.get("target_y"),
            reason=f"agent: {reasoning}" if reasoning else "agent_loot",
        )
    else:
        return PlayerAction(
            player_id=agent_id,
            action_type=ActionType.WAIT,
            reason=f"agent: {reasoning}" if reasoning else "agent_wait",
        )


# ─── Game Log ────────────────────────────────────────────────────────────────

class GameLog:
    """Records every turn's state, decision, and outcome for post-game analysis."""

    def __init__(self):
        self.turns: list[dict] = []
        self.match_info: dict = {}

    def record_turn(self, turn: int, state_briefing: str, action: dict,
                    outcome_events: list[str]):
        self.turns.append({
            "turn": turn,
            "briefing": state_briefing,
            "action": action,
            "outcome": outcome_events,
        })

    def save(self):
        data = {
            "match_info": self.match_info,
            "total_turns": len(self.turns),
            "turns": self.turns,
        }
        with open(LOG_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)


# ─── Copilot Embedded Brain ──────────────────────────────────────────────────

def copilot_decide(
    agent_id: str,
    all_units: dict,
    state: dict,
    obstacles: set,
    door_tiles: set | None,
    grid_width: int,
    grid_height: int,
    match_id: str,
) -> PlayerAction:
    """Copilot's strategic brain — makes instant decisions each turn.

    Priority ladder:
        1. Use potion if low HP (<35%)
        2. Retreat if critically low HP and enemies adjacent
        3. Loot items at feet
        4. Use offensive/healing skills when appropriate
        5. Melee attack adjacent enemies (prefer lowest HP)
        6. Ranged attack distant enemies
        7. Approach visible enemies if nearby (≤6 tiles)
        8. Open adjacent doors
        9. Move toward next exploration target
       10. Wander randomly
       11. Wait (no moves possible)
    """
    agent = all_units[agent_id]
    ax, ay = agent.position.x, agent.position.y
    hp_pct = agent.hp / agent.max_hp if agent.max_hp > 0 else 0

    available = state["available_actions"]
    visible_enemies = state["visible_enemies"]
    allies = state["allies"]
    exploration = state["exploration"]

    # Build occupied set for pathfinding
    occupied = set()
    for uid, unit in all_units.items():
        if unit.is_alive and uid != agent_id:
            occupied.add((unit.position.x, unit.position.y))

    # ── PRIORITY 1: Survival — use potion if low HP ──
    if hp_pct < 0.35:
        potions = available.get("USE_ITEM", [])
        if potions:
            return PlayerAction(
                player_id=agent_id, action_type=ActionType.USE_ITEM,
                target_x=potions[0]["index"],
                reason="copilot: low HP, using potion",
            )

    # ── PRIORITY 2: Retreat if critically low and enemies adjacent ──
    melee_enemies = [e for e in visible_enemies if e.get("melee_reachable")]
    if hp_pct < 0.25 and melee_enemies:
        move_targets = available.get("MOVE", [])
        if move_targets:
            best = None
            best_dist = -1
            for t in move_targets:
                min_d = min(
                    _chebyshev((t["x"], t["y"]),
                               (e["position"]["x"], e["position"]["y"]))
                    for e in melee_enemies
                )
                if min_d > best_dist:
                    best_dist = min_d
                    best = t
            if best and best_dist > 1:
                return PlayerAction(
                    player_id=agent_id, action_type=ActionType.MOVE,
                    target_x=best["x"], target_y=best["y"],
                    reason=f"copilot: retreating, HP {hp_pct*100:.0f}%",
                )

    # ── PRIORITY 3: Loot items at feet ──
    loot = available.get("LOOT", [])
    if loot:
        return PlayerAction(
            player_id=agent_id, action_type=ActionType.LOOT,
            target_x=ax, target_y=ay,
            reason=f"copilot: looting {loot[0]['name']}",
        )

    # ── PRIORITY 4: Skills ──
    ready_skills = [s for s in available.get("SKILL", []) if s.get("ready")]
    if ready_skills:
        for skill in ready_skills:
            skill_range = skill.get("range", 1)
            damage = skill.get("damage", 0)
            heal = skill.get("heal", 0)
            target_type = skill.get("target_type", "enemy")

            # Offensive skill on nearest enemy in range
            if damage > 0 and target_type == "enemy" and visible_enemies:
                for enemy in visible_enemies:
                    ex, ey = enemy["position"]["x"], enemy["position"]["y"]
                    dist = _chebyshev((ax, ay), (ex, ey))
                    if dist <= skill_range:
                        # Verify LOS for ranged skills
                        if skill_range > 1 and not has_line_of_sight(ax, ay, ex, ey, obstacles):
                            continue
                        return PlayerAction(
                            player_id=agent_id, action_type=ActionType.SKILL,
                            skill_id=skill["skill_id"],
                            target_x=ex, target_y=ey, target_id=enemy["id"],
                            reason=f"copilot: {skill['name']} → {enemy['name']}",
                        )

            # Self-heal when hurt
            if heal > 0 and target_type in ("self", "ally") and hp_pct < 0.6:
                return PlayerAction(
                    player_id=agent_id, action_type=ActionType.SKILL,
                    skill_id=skill["skill_id"],
                    target_x=ax, target_y=ay, target_id=agent_id,
                    reason=f"copilot: self-heal {skill['name']}",
                )

            # Heal hurt allies in range
            if heal > 0 and target_type == "ally":
                hurt = [a for a in allies
                        if a["hp"] / max(a["max_hp"], 1) < 0.5]
                for ally in hurt:
                    ad = _chebyshev(
                        (ax, ay),
                        (ally["position"]["x"], ally["position"]["y"]),
                    )
                    if ad <= skill_range:
                        return PlayerAction(
                            player_id=agent_id, action_type=ActionType.SKILL,
                            skill_id=skill["skill_id"],
                            target_x=ally["position"]["x"],
                            target_y=ally["position"]["y"],
                            target_id=ally["id"],
                            reason=f"copilot: heal {ally['name']} {skill['name']}",
                        )

            # Buff before combat
            if skill.get("buff") and visible_enemies:
                return PlayerAction(
                    player_id=agent_id, action_type=ActionType.SKILL,
                    skill_id=skill["skill_id"],
                    target_x=ax, target_y=ay, target_id=agent_id,
                    reason=f"copilot: buff {skill['name']}",
                )

    # ── PRIORITY 5: Melee attack (pick lowest HP) ──
    melee_targets = available.get("ATTACK", [])
    if melee_targets:
        target = min(melee_targets, key=lambda e: e["hp"])
        return PlayerAction(
            player_id=agent_id, action_type=ActionType.ATTACK,
            target_id=target["id"],
            reason=f"copilot: melee {target['name']} HP:{target['hp']}",
        )

    # ── PRIORITY 6: Ranged attack ──
    ranged_targets = available.get("RANGED_ATTACK", [])
    if ranged_targets:
        target = min(ranged_targets, key=lambda e: e["hp"])
        return PlayerAction(
            player_id=agent_id, action_type=ActionType.RANGED_ATTACK,
            target_id=target["id"],
            reason=f"copilot: ranged {target['name']} HP:{target['hp']}",
        )

    # ── PRIORITY 7: Approach visible enemy if nearby ──
    if visible_enemies:
        nearest = visible_enemies[0]  # sorted by manhattan_distance
        if nearest["manhattan_distance"] <= 6:
            ex, ey = nearest["position"]["x"], nearest["position"]["y"]
            step = get_next_step_toward(
                (ax, ay), (ex, ey),
                grid_width, grid_height, obstacles, occupied,
                door_tiles=door_tiles,
            )
            if step:
                return PlayerAction(
                    player_id=agent_id, action_type=ActionType.MOVE,
                    target_x=step[0], target_y=step[1],
                    reason=f"copilot: approach {nearest['name']} ({ex},{ey})",
                )

    # ── PRIORITY 8: Open adjacent door ──
    doors = available.get("INTERACT", [])
    if doors:
        return PlayerAction(
            player_id=agent_id, action_type=ActionType.INTERACT,
            target_x=doors[0]["x"], target_y=doors[0]["y"],
            reason="copilot: opening door",
        )

    # ── PRIORITY 9: Move toward exploration target ──
    next_target = exploration.get("next_target")
    if next_target:
        tx = next_target["entrance"]["x"]
        ty = next_target["entrance"]["y"]
        step = get_next_step_toward(
            (ax, ay), (tx, ty),
            grid_width, grid_height, obstacles, occupied,
            door_tiles=door_tiles,
        )
        if step:
            return PlayerAction(
                player_id=agent_id, action_type=ActionType.MOVE,
                target_x=step[0], target_y=step[1],
                reason=f"copilot: explore → {next_target['room_id']} ({tx},{ty})",
            )

    # ── PRIORITY 10: Wander ──
    move_targets = available.get("MOVE", [])
    if move_targets:
        pick = random.choice(move_targets)
        return PlayerAction(
            player_id=agent_id, action_type=ActionType.MOVE,
            target_x=pick["x"], target_y=pick["y"],
            reason="copilot: wander",
        )

    # ── FALLBACK: Wait ──
    return PlayerAction(
        player_id=agent_id, action_type=ActionType.WAIT,
        reason="copilot: no actions available",
    )


# ─── Main Simulation ─────────────────────────────────────────────────────────

def run_agent_pvpve(
    team_size: int = 5,
    grid_size: int = 8,
    pve_density: float = 0.5,
    max_turns: int = 300,
    seed: int | None = None,
    agent_class: str | None = None,
    action_timeout: int = 300,
    copilot_mode: bool = True,
    turn_delay: float = 0.3,
) -> dict | None:
    """Run a PVPVE match with Copilot as Team A leader."""

    _ensure_agent_dir()

    if seed is not None:
        random.seed(seed)

    config = MatchConfig(
        match_type=MatchType.PVPVE,
        pvpve_team_count=4,
        pvpve_ai_team_count=3,
        pvpve_ai_team_sizes=[team_size, team_size, team_size],
        pvpve_grid_size=grid_size,
        pvpve_pve_density=pve_density,
        pvpve_boss_enabled=True,
        pvpve_loot_density=0.5,
        tick_rate=1.0,
        max_players=team_size * 4 + 100,
        ai_allies=team_size,
    )

    match, host = create_match("AgentPVPVE", config=config)
    match_id = match.match_id
    host.is_ready = True

    started = start_match(match_id)
    if not started:
        print(f"  [ERROR] Failed to start PVPVE match {match_id}")
        remove_match(match_id)
        return None

    # Remove dummy host
    host_id = host.player_id
    all_units = get_match_players(match_id)
    all_units.pop(host_id, None)
    if host_id in match.player_ids:
        match.player_ids.remove(host_id)
    if host_id in match.team_a:
        match.team_a.remove(host_id)

    # Find/promote Team A leader — this is the AGENT
    agent_id = None
    for uid in match.team_a:
        unit = all_units.get(uid)
        if unit and unit.is_alive and getattr(unit, "is_team_leader", False):
            agent_id = uid
            break

    if not agent_id:
        for uid in match.team_a:
            unit = all_units.get(uid)
            if unit and unit.is_alive:
                unit.is_team_leader = True
                unit.hero_id = None
                unit.ai_stance = None
                unit.ai_behavior = "aggressive"
                agent_id = uid
                break

    if not agent_id:
        print(f"  [ERROR] No Team A units found!")
        remove_match(match_id)
        return None

    # Apply agent's class preference if specified
    if agent_class:
        agent_unit = all_units[agent_id]
        class_def = get_class_definition(agent_class)
        if class_def:
            agent_unit.class_id = agent_class
            agent_unit.username = class_def.get("name", agent_class.title())
            agent_unit.max_hp = class_def.get("hp", agent_unit.max_hp)
            agent_unit.hp = agent_unit.max_hp
            agent_unit.attack_damage = class_def.get("attack_damage", agent_unit.attack_damage)
            agent_unit.ranged_damage = class_def.get("ranged_damage", 0)
            agent_unit.armor = class_def.get("armor", agent_unit.armor)
            agent_unit.vision_range = class_def.get("vision_range", 7)
            agent_unit.ranged_range = class_def.get("ranged_range", 5)
            print(f"  Agent class set to: {agent_class}")

    # Re-parent Team A followers
    for uid in match.team_a:
        if uid == agent_id:
            unit = all_units.get(uid)
            if unit:
                unit.hero_id = None
                unit.ai_stance = None
                unit.ai_behavior = "aggressive"  # Doesn't matter — we intercept
                unit.is_team_leader = True
            continue
        unit = all_units.get(uid)
        if unit and unit.hero_id:
            unit.hero_id = agent_id
            unit.ai_stance = "follow"

    # Load map
    map_id = match.config.map_id
    map_data = load_map(map_id)
    grid_width = map_data.get("width", 15)
    grid_height = map_data.get("height", 15)

    all_units = get_match_players(match_id)
    hero_count = sum(1 for u in all_units.values()
                     if u.is_alive and getattr(u, "team", "") in ("a", "b", "c", "d"))
    pve_count = sum(1 for u in all_units.values()
                    if u.is_alive and getattr(u, "team", "") == "pve")

    agent_unit = all_units[agent_id]

    print(f"\n{'═' * 70}")
    print(f"  🎮 PVPVE AGENT MODE — COPILOT PLAYS")
    print(f"{'═' * 70}")
    print(f"  Match: {match_id}")
    print(f"  Grid: {grid_size}x{grid_size} | Map: {grid_width}x{grid_height}")
    print(f"  Theme: {match.theme_id}")
    print(f"  YOU: {agent_unit.username} ({agent_unit.class_id}) — Team A Leader")
    print(f"  Heroes: {hero_count} across 4 teams | PVE: {pve_count} enemies")
    print(f"  Max turns: {max_turns} | Timeout: {action_timeout}s per turn")
    print(f"{'═' * 70}")

    # Print all teams
    teams_display = {"a": match.team_a, "b": match.team_b, "c": match.team_c, "d": match.team_d}
    for team_key, team_ids in teams_display.items():
        members = [all_units.get(uid) for uid in team_ids if all_units.get(uid)]
        if members:
            classes = []
            for m in members:
                tag = " ← YOU" if m.player_id == agent_id else ""
                classes.append(f"{m.username}{tag}")
            print(f"  {_team_label(team_key)}: {', '.join(classes)}")
    print()

    # Game log
    game_log = GameLog()
    game_log.match_info = {
        "match_id": match_id,
        "agent_id": agent_id,
        "agent_class": agent_unit.class_id,
        "grid_size": grid_size,
        "theme": match.theme_id,
        "team_size": team_size,
        "pve_count": pve_count,
        "seed": seed,
    }

    recent_events: list[str] = []
    winner = None
    turn_number = 0

    # Show initial map
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

        # Check if agent is still alive
        agent_alive = agent_id in all_units and all_units[agent_id].is_alive
        if not agent_alive:
            recent_events.append(f"T{turn_number}: YOUR CHARACTER HAS DIED!")

        # Dungeon state
        dungeon_state = get_dungeon_state(match_id)
        door_states = dungeon_state["door_states"] if dungeon_state else None
        chest_states = dungeon_state["chest_states"] if dungeon_state else None
        ground_items = dungeon_state["ground_items"] if dungeon_state else None

        obstacles = get_obstacles_with_door_states(map_id, door_states)

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

        # Compute FOV for all units
        for uid, unit in all_units.items():
            if unit.is_alive and not unit.extracted:
                fov = compute_fov(
                    unit.position.x, unit.position.y,
                    unit.vision_range,
                    grid_width, grid_height,
                    obstacles,
                )
                set_fov_cache(match_id, uid, fov)

        # Build team FOV
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

        # Update room discovery
        for team_letter, team_fov_set in ai_team_fov_map.items():
            if team_fov_set:
                update_room_discovery(match_id, team_letter, team_fov_set)
                update_room_clearance(match_id, team_letter, all_units, chest_states)

        # ── Agent decision (BEFORE follower AI so they see our intent) ──
        agent_action_data = None
        agent_action = None
        state = None
        if agent_alive:
            state = build_game_state(
                agent_id=agent_id,
                all_units=all_units,
                obstacles=obstacles,
                door_tiles=door_tiles,
                team_fov=pre_team_a_fov,
                grid_width=grid_width,
                grid_height=grid_height,
                map_data=map_data,
                door_states=door_states,
                chest_states=chest_states,
                ground_items=ground_items,
                match_id=match_id,
                match_state=match,
                turn_number=turn_number,
                max_turns=max_turns,
                recent_events=recent_events,
            )

            if copilot_mode:
                # ── Copilot embedded brain — instant decision ──
                agent_action = copilot_decide(
                    agent_id, all_units, state, obstacles,
                    door_tiles, grid_width, grid_height, match_id,
                )
                agent_action_data = {
                    "action": agent_action.action_type.value,
                    "reasoning": agent_action.reason or "",
                }

                # Compact status line (not full briefing — too noisy)
                agent_unit_now = all_units[agent_id]
                enemies_str = f" | {len(state['visible_enemies'])} enemies visible" if state["visible_enemies"] else ""
                print(f"\n  T{turn_number}: {agent_unit_now.username} ({agent_unit_now.class_id}) "
                      f"HP:{agent_unit_now.hp}/{agent_unit_now.max_hp} "
                      f"@ ({agent_unit_now.position.x},{agent_unit_now.position.y})"
                      f"{enemies_str}")
                print(f"  🎯 {agent_action.action_type.value.upper()}: {agent_action.reason}")

                # Show local map every turn so user can watch movement
                print(state["local_map"])

            else:
                # ── File I/O agent mode (original) ──
                write_state(state)

                # Print briefing to console
                print(f"\n{'─' * 70}")
                print(state["briefing"])
                print(f"{'─' * 70}")
                print(state["local_map"])

                agent_action_data = wait_for_action(turn_number, timeout=action_timeout)
                agent_action = parse_agent_action(agent_id, agent_action_data)

                act_str = agent_action_data.get("action", "WAIT") if agent_action_data else "WAIT(timeout)"
                reasoning = agent_action_data.get("reasoning", "") if agent_action_data else "timeout"
                print(f"\n  🎯 AGENT ACTION: {act_str} — {reasoning}")

        # Temporarily project agent's intended position so followers see
        # where we're heading and yield the path (mirrors pending_moves
        # behavior in the normal AI pipeline)
        original_agent_pos = None
        agent_unit_ref = all_units.get(agent_id)
        if agent_action and agent_action.action_type == ActionType.MOVE and agent_unit_ref:
            if agent_action.target_x is not None and agent_action.target_y is not None:
                original_agent_pos = (agent_unit_ref.position.x, agent_unit_ref.position.y)
                agent_unit_ref.position.x = agent_action.target_x
                agent_unit_ref.position.y = agent_action.target_y

        # Remove agent from AI list so run_ai_decisions doesn't control them
        non_agent_ai_ids = [uid for uid in ai_ids if uid != agent_id]

        # Run AI for everyone else — followers now see agent at intended position
        ai_actions = run_ai_decisions(
            non_agent_ai_ids, all_units, grid_width, grid_height, obstacles,
            team_fov_map=ai_team_fov_map,
            match_id=match_id,
            controlled_ids=get_controlled_unit_ids(match_id),
            door_tiles=door_tiles,
            portal=match.portal,
            match_state=match,
            ground_items=ground_items,
            chest_states=chest_states,
        )

        # Restore agent's original position before turn resolution
        if original_agent_pos and agent_unit_ref:
            agent_unit_ref.position.x, agent_unit_ref.position.y = original_agent_pos

        action_list = list(ai_actions)

        if agent_action:
            action_list.insert(0, agent_action)
        else:
            # Agent is dead, just add WAIT
            action_list.insert(0, PlayerAction(
                player_id=agent_id,
                action_type=ActionType.WAIT,
                reason="agent_dead",
            ))

        # Resolve turn
        stairs_info = get_stairs_info(match_id)
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
            team_a=team_a,
            team_b=team_b,
            team_c=team_c,
            team_d=team_d,
            door_states=door_states,
            chest_states=chest_states,
            ground_items=ground_items,
            is_dungeon=True,
            match_channeling=match.channeling,
            match_portal=match.portal,
            stairs_positions=stairs_positions,
            stairs_unlocked=stairs_unlocked,
            floor_number=getattr(match, "current_floor", 1),
            match_state=match,
        )

        # Persist channeling/portal state (same as batch_pvpve.py)
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

        # Track stats
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

        record_turn_events(match_id, turn_number, turn_result, all_units)

        # Collect events for recent_events list
        turn_events = []
        for death_pid in turn_result.deaths:
            unit = all_units.get(death_pid)
            name = getattr(unit, "username", death_pid[:12]) if unit else death_pid[:12]
            team = getattr(unit, "team", "?") if unit else "?"
            turn_events.append(f"T{turn_number}: {name} (Team {team.upper()}) DIED")
        for act in turn_result.actions:
            if getattr(act, "damage_dealt", 0) and act.damage_dealt > 0:
                attacker = all_units.get(act.player_id)
                target = all_units.get(act.target_id) if act.target_id else None
                a_name = getattr(attacker, "username", "?") if attacker else "?"
                t_name = getattr(target, "username", "?") if target else "?"
                turn_events.append(f"T{turn_number}: {a_name} hit {t_name} for {act.damage_dealt} dmg")
            if getattr(act, "heal_amount", 0) and act.heal_amount > 0:
                healer = all_units.get(act.player_id)
                h_name = getattr(healer, "username", "?") if healer else "?"
                turn_events.append(f"T{turn_number}: {h_name} healed for {act.heal_amount}")
        for dc in turn_result.door_changes:
            turn_events.append(f"T{turn_number}: Door at ({dc.get('x','?')},{dc.get('y','?')}) {dc.get('state','?')}")
        recent_events.extend(turn_events)
        # Keep recent events from growing too large
        if len(recent_events) > 50:
            recent_events = recent_events[-30:]

        # Print turn results
        result_lines = log_turn_results(turn_result, all_units, turn_number)
        if result_lines:
            for line in result_lines:
                print(line)

        summary = compact_turn_summary(turn_number, action_list, turn_result, all_units)
        print(summary)

        # Game log entry
        game_log.record_turn(
            turn=turn_number,
            state_briefing=state["briefing"] if agent_alive and state else "",
            action=agent_action_data or {"action": "WAIT", "reasoning": "dead/timeout"},
            outcome_events=turn_events,
        )

        # Recompute FOV
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

        # Show ASCII map every 5 turns (or every turn in copilot mode)
        show_map = copilot_mode or (turn_number % 5 == 0)
        if show_map and turn_number % 3 == 0:  # Every 3 turns in copilot mode
            full_map = render_ascii_map(map_data, all_units, door_states, turn_number)
            print(full_map)
            print(render_team_summary(all_units))
        elif not copilot_mode and turn_number % 5 == 0:
            full_map = render_ascii_map(map_data, all_units, door_states, turn_number)
            print(full_map)
            print(render_team_summary(all_units))

        # Turn delay for watchability
        if turn_delay > 0:
            time.sleep(turn_delay)

        # Check winner
        if turn_result.winner:
            winner = turn_result.winner
            save_match_report(match_id, winner, turn_number)
            end_match(match_id)
            clear_ai_patrol_state()
            break

    # ─── Post-match ──────────────────────────────────────────────────────────
    if not winner:
        winner = "draw"
        save_match_report(match_id, "draw", max_turns)
        end_match(match_id)
        clear_ai_patrol_state()

    # Final map
    all_units = get_match_players(match_id) or all_units
    dungeon_state = get_dungeon_state(match_id)
    ds = dungeon_state["door_states"] if dungeon_state else door_states
    print(f"\n{'═' * 70}")
    print(f"  GAME OVER — {winner.upper()} WINS in {turn_number} turns")
    print(f"{'═' * 70}")
    final_map = render_ascii_map(map_data, all_units, ds, turn_number)
    print(final_map)
    print(render_team_summary(all_units))

    # Save game log
    game_log.match_info["winner"] = winner
    game_log.match_info["total_turns"] = turn_number
    game_log.save()
    print(f"\n  Game log saved to: {LOG_FILE}")

    # Clean up
    result = {
        "match_id": match_id,
        "winner": winner,
        "turns": turn_number,
        "agent_class": all_units.get(agent_id, {}) and getattr(all_units.get(agent_id), "class_id", "?"),
    }
    remove_match(match_id)
    return result


def main():
    parser = argparse.ArgumentParser(description="PVPVE Agent Mode — Copilot plays the dungeon")
    parser.add_argument("--grid-size", type=int, default=6, help="WFC grid size (4=Small, 6=Large, 8=XL)")
    parser.add_argument("--team-size", type=int, default=5, help="Heroes per team (1-5)")
    parser.add_argument("--pve-density", type=float, default=0.5, help="PVE enemy density (0.0-1.0)")
    parser.add_argument("--max-turns", type=int, default=300, help="Turn limit")
    parser.add_argument("--seed", type=int, default=None, help="RNG seed for reproducibility")
    parser.add_argument("--class", dest="agent_class", type=str, default=None,
                        help="Class for agent (crusader, confessor, mage, etc.)")
    parser.add_argument("--timeout", type=int, default=300, help="Seconds to wait for agent action per turn")
    parser.add_argument("--file-io", action="store_true", default=False,
                        help="Use file I/O mode instead of embedded copilot brain")
    parser.add_argument("--delay", type=float, default=0.3,
                        help="Seconds between turns for watchability (default 0.3)")

    args = parser.parse_args()

    copilot_mode = not args.file_io

    print(f"\n{'═' * 70}")
    print(f"  🎮 HERO'S CALL ARENA — AGENT PVPVE MODE")
    if copilot_mode:
        print(f"  Mode: COPILOT BRAIN (embedded AI) — {args.delay}s delay")
    else:
        print(f"  Mode: FILE I/O (external agent) — {args.timeout}s timeout")
    print(f"  Copilot will play as Team A leader with {args.team_size - 1} AI companions")
    print(f"  Grid: {args.grid_size} | PVE: {args.pve_density} | Max turns: {args.max_turns}")
    if args.agent_class:
        print(f"  Agent class: {args.agent_class}")
    if args.seed:
        print(f"  Seed: {args.seed}")
    print(f"{'═' * 70}\n")

    result = run_agent_pvpve(
        team_size=args.team_size,
        grid_size=args.grid_size,
        pve_density=args.pve_density,
        max_turns=args.max_turns,
        seed=args.seed,
        agent_class=args.agent_class,
        action_timeout=args.timeout,
        copilot_mode=copilot_mode,
        turn_delay=args.delay,
    )

    if result:
        print(f"\n  Result: {result['winner']} wins in {result['turns']} turns")


if __name__ == "__main__":
    main()
