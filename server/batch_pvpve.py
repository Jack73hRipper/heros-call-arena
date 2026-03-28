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

# Fix Windows console encoding for Unicode box-drawing chars.
# Three layers needed because different hosts read Python's stdout differently:
#   1. sys.stdout.reconfigure — makes Python's internal encoder use UTF-8.
#   2. SetConsoleOutputCP(65001) — tells cmd.exe to interpret bytes as UTF-8.
#   3. PYTHONIOENCODING / -X utf8 — ensures pipes/redirects also use UTF-8.
# PowerShell additionally needs [Console]::OutputEncoding = UTF8 on the
# caller side; the bat launcher handles this via chcp 65001.
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    try:
        import ctypes
        ctypes.windll.kernel32.SetConsoleOutputCP(65001)
        ctypes.windll.kernel32.SetConsoleCP(65001)
    except Exception:
        pass

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
from app.core.ai_behavior import run_ai_decisions, clear_ai_patrol_state, _explore_suppressed, _position_history, _explore_total_turns
from app.models.player import get_all_classes, get_class_definition
from app.core.equipment_manager import score_item_for_role, _CLASS_ROLE_MAP
from app.core.ai_exploration import get_exploration_progress, get_room_discovery, update_room_discovery, update_room_clearance, get_next_exploration_target, _skipped_rooms, _skip_count, _door_rooms, get_room_info


# ─── Exploration Report Tracker ──────────────────────────────────────────────

class ExplorationTracker:
    """Tracks per-team exploration coverage, door interactions, and oscillation
    patterns for diagnosing AI exploration stalling."""

    def __init__(self, match_id: str, grid_width: int, grid_height: int):
        self.match_id = match_id
        self.grid_width = grid_width
        self.grid_height = grid_height

        # Per-team tile coverage: {team: set((x,y), ...)}
        self.tiles_visited: dict[str, set[tuple[int, int]]] = {
            "a": set(), "b": set(), "c": set(), "d": set(),
        }
        # Per-unit tile coverage (for leaders vs followers breakdown)
        self.unit_tiles: dict[str, set[tuple[int, int]]] = {}
        # Per-unit position history for cycle detection
        self._unit_positions: dict[str, list[tuple[int, int]]] = {}

        # Door interaction tracking
        self.door_opens: dict[str, int] = {"a": 0, "b": 0, "c": 0, "d": 0}
        self.door_approach_failures: dict[str, int] = {"a": 0, "b": 0, "c": 0, "d": 0}
        # Per-unit: turns spent with explore_room targeting a door entrance
        # but not opening it
        self._explore_door_target_turns: dict[str, int] = {}

        # Oscillation / cycle detection
        # {unit_id: {cycle_len: count}} — how many times each cycle length detected
        self.cycles_detected: dict[str, dict[int, int]] = {}
        # Per-team total oscillation turns (turns spent in detected cycles)
        self.oscillation_turns: dict[str, int] = {"a": 0, "b": 0, "c": 0, "d": 0}

        # Per-unit reason counters (for leaders)
        self.leader_reasons: dict[str, dict[str, int]] = {}
        # Leader IDs per team
        self.team_leaders: dict[str, str] = {}

        # Phase 32D/E: Global reason counters — ALL hero actions, not just leaders.
        # {reason_string: total_count} aggregated across all hero units.
        self.all_reason_counts: dict[str, int] = {}

        # Exploration progress snapshots per team {team: [{turn, discovered, cleared, pct}]}
        self.progress_snapshots: dict[str, list[dict]] = {
            "a": [], "b": [], "c": [], "d": [],
        }

        # Total walkable tiles (computed once)
        self.total_walkable: int = 0

        # --- NEW: Leader stall diagnostics ---
        # Per-team: turns leader spent suppressed from exploration
        self.suppression_turns: dict[str, int] = {"a": 0, "b": 0, "c": 0, "d": 0}
        # Per-team: exploration target room_id each turn (to detect re-targeting)
        self._leader_target_history: dict[str, list[str | None]] = {
            "a": [], "b": [], "c": [], "d": [],
        }
        # Per-team: unique rooms targeted across the match
        self.unique_targets: dict[str, set[str]] = {
            "a": set(), "b": set(), "c": set(), "d": set(),
        }
        # Per-team: how many times the target switched to a different room
        self.target_switches: dict[str, int] = {"a": 0, "b": 0, "c": 0, "d": 0}
        # Follower vs leader oscillation split
        self.follower_oscillation_turns: dict[str, int] = {"a": 0, "b": 0, "c": 0, "d": 0}
        self.leader_oscillation_turns: dict[str, int] = {"a": 0, "b": 0, "c": 0, "d": 0}

        # --- Enhancement: Door approach detail log ---
        # List of {turn, team, leader_pos, door_pos, next_step, target_entrance}
        self.door_approach_details: list[dict] = []

        # --- Enhancement: Per-class oscillation counters ---
        # {class_id: total_oscillation_turns}
        self.class_oscillation_turns: dict[str, int] = {}
        # {class_id: unit_count} for averaging
        self.class_unit_count: dict[str, int] = {}

        # --- Enhancement: Leader distance-to-target per turn ---
        # {team: [manhattan_distance_per_turn]}
        self.leader_distance_to_target: dict[str, list[int | None]] = {
            "a": [], "b": [], "c": [], "d": [],
        }

        # --- Root Cause #1 fix tracking: rooms skipped ---
        self.rooms_skipped: dict[str, int] = {"a": 0, "b": 0, "c": 0, "d": 0}

        # --- RC#3 diagnostics: enhanced stall tracking ---
        # Per-team: last turn a leader made forward exploration progress
        # (distance-to-target decreased compared to previous turn)
        self.last_progress_turn: dict[str, int] = {"a": 0, "b": 0, "c": 0, "d": 0}
        # Per-team: turns where get_next_exploration_target returned None
        self.no_target_turns: dict[str, int] = {"a": 0, "b": 0, "c": 0, "d": 0}
        # Per-team: per-room skip details {team: [(turn, room_id, reason, skip_count)]}
        self.room_skip_log: dict[str, list[tuple]] = {"a": [], "b": [], "c": [], "d": []}
        # Per-team: rooms that hit permanent skip (count >= 4)
        self.permanently_skipped: dict[str, set[str]] = {"a": set(), "b": set(), "c": set(), "d": set()}
        # Snapshot of _skip_count per turn for detecting permanent skips
        self._prev_skip_counts: dict[str, dict[str, int]] = {"a": {}, "b": {}, "c": {}, "d": {}}

    def set_walkable_count(self, obstacles: set[tuple[int, int]]):
        """Compute total walkable tiles for coverage percentage."""
        total = self.grid_width * self.grid_height
        self.total_walkable = total - len(obstacles)

    def register_leaders(self, all_units: dict):
        """Identify team leaders for per-leader tracking."""
        for uid, unit in all_units.items():
            team = getattr(unit, "team", "")
            if team in ("a", "b", "c", "d") and getattr(unit, "is_team_leader", False):
                self.team_leaders[team] = uid
            # Track class counts for per-class oscillation averaging
            if team in ("a", "b", "c", "d"):
                cls = getattr(unit, "class_id", "unknown")
                self.class_unit_count[cls] = self.class_unit_count.get(cls, 0) + 1

    def collect_turn(self, turn_number: int, actions: list, all_units: dict,
                     door_tiles: set[tuple[int, int]] | None, match_id: str):
        """Process one turn of actions for exploration diagnostics."""
        for act in actions:
            pid = act.player_id if hasattr(act, "player_id") else None
            if not pid:
                continue
            unit = all_units.get(pid)
            if not unit:
                continue
            team = getattr(unit, "team", "")
            if team not in ("a", "b", "c", "d"):
                continue

            reason = getattr(act, "reason", "") or ""
            action_type = act.action_type if hasattr(act, "action_type") else None
            cur_pos = (unit.position.x, unit.position.y)

            # Track tile coverage
            self.tiles_visited[team].add(cur_pos)
            if pid not in self.unit_tiles:
                self.unit_tiles[pid] = set()
            self.unit_tiles[pid].add(cur_pos)

            # Track position history for cycle detection
            if pid not in self._unit_positions:
                self._unit_positions[pid] = []
            self._unit_positions[pid].append(cur_pos)
            if len(self._unit_positions[pid]) > 60:
                self._unit_positions[pid] = self._unit_positions[pid][-60:]

            # Track leader reasons
            if pid in self.team_leaders.values() and reason:
                if pid not in self.leader_reasons:
                    self.leader_reasons[pid] = {}
                self.leader_reasons[pid][reason] = self.leader_reasons[pid].get(reason, 0) + 1

            # Track ALL hero reasons (global aggregate)
            if reason:
                self.all_reason_counts[reason] = self.all_reason_counts.get(reason, 0) + 1

            # Door interaction tracking
            if reason == "open_door":
                self.door_opens[team] = self.door_opens.get(team, 0) + 1

            # Door approach failure: explore_room targets a door entrance
            # but the leader moves AWAY instead of opening it
            if pid in self.team_leaders.values():
                if reason == "explore_room" and action_type == ActionType.MOVE:
                    target_x = getattr(act, "target_x", None)
                    target_y = getattr(act, "target_y", None)
                    if target_x is not None and target_y is not None:
                        target_pos = (target_x, target_y)
                        # Check if the exploration target has a door nearby
                        # that we're approaching but not opening
                        if door_tiles and self._is_adjacent_to_door(cur_pos, door_tiles):
                            if target_pos not in door_tiles:
                                # Moving away from door despite being adjacent
                                self.door_approach_failures[team] += 1
                                # Log details for diagnostics
                                adj_doors = self._get_adjacent_doors(cur_pos, door_tiles)
                                # Get current exploration target entrance
                                leader_target = get_next_exploration_target(match_id, team, cur_pos)
                                entrance = leader_target["entrance"] if leader_target else None
                                self.door_approach_details.append({
                                    "turn": turn_number,
                                    "team": team,
                                    "leader_pos": cur_pos,
                                    "door_pos": adj_doors,
                                    "next_step": target_pos,
                                    "target_entrance": entrance,
                                })

            # Detect multi-tile oscillation cycles (length 2-8)
            self._detect_cycles(pid, team, unit)

        # Snapshot exploration progress periodically
        if turn_number % 25 == 0 or turn_number == 1:
            for team_key in ("a", "b", "c", "d"):
                progress = get_exploration_progress(match_id, team_key)
                self.progress_snapshots[team_key].append({
                    "turn": turn_number,
                    "discovered": progress["discovered_rooms"],
                    "cleared": progress["cleared_rooms"],
                    "total": progress["total_rooms"],
                    "pct": progress["exploration_pct"],
                })

        # --- NEW: Per-turn leader stall diagnostics ---
        for team_key in ("a", "b", "c", "d"):
            leader_id = self.team_leaders.get(team_key)
            if not leader_id:
                continue
            leader_unit = all_units.get(leader_id)
            if not leader_unit or not leader_unit.is_alive:
                # Check if a new leader was promoted (succession)
                new_leader_id = None
                for uid, unit in all_units.items():
                    if (
                        getattr(unit, 'is_team_leader', False)
                        and getattr(unit, 'team', '') == team_key
                        and unit.is_alive
                        and uid != leader_id
                    ):
                        new_leader_id = uid
                        break
                if new_leader_id:
                    self.team_leaders[team_key] = new_leader_id
                    leader_id = new_leader_id
                    leader_unit = all_units[new_leader_id]
                else:
                    self._leader_target_history[team_key].append(None)
                    continue

            # Track suppression state
            if leader_id in _explore_suppressed:
                self.suppression_turns[team_key] += 1

            # Track exploration target
            leader_pos = (leader_unit.position.x, leader_unit.position.y)
            target = get_next_exploration_target(match_id, team_key, leader_pos)
            target_rid = target["room_id"] if target else None
            self._leader_target_history[team_key].append(target_rid)
            if target_rid:
                self.unique_targets[team_key].add(target_rid)

            # Track leader distance to target entrance
            if target:
                ent = target["entrance"]
                dist = abs(leader_pos[0] - ent[0]) + abs(leader_pos[1] - ent[1])
                self.leader_distance_to_target[team_key].append(dist)

                # RC#3: Track forward progress (distance decreasing)
                prev_dists = self.leader_distance_to_target[team_key]
                if len(prev_dists) >= 2 and prev_dists[-2] is not None:
                    if dist < prev_dists[-2]:
                        self.last_progress_turn[team_key] = turn_number
            else:
                self.leader_distance_to_target[team_key].append(None)
                # RC#3: No exploration target available
                self.no_target_turns[team_key] += 1

            # Track rooms currently skipped
            team_skips = _skipped_rooms.get(match_id, {}).get(team_key, {})
            self.rooms_skipped[team_key] = max(
                self.rooms_skipped[team_key], len(team_skips),
            )

            # RC#3: Detect new room skips by comparing skip counts
            cur_skip_counts = dict(_skip_count.get(match_id, {}).get(team_key, {}))
            prev_counts = self._prev_skip_counts[team_key]
            for rid, cnt in cur_skip_counts.items():
                prev_cnt = prev_counts.get(rid, 0)
                if cnt > prev_cnt:
                    reason = "stagnation" if cnt == 1 and not team_skips.get(rid) else "pathfind_fail"
                    self.room_skip_log[team_key].append((turn_number, rid, reason, cnt))
                    if cnt >= 4:
                        self.permanently_skipped[team_key].add(rid)
            self._prev_skip_counts[team_key] = cur_skip_counts

            # Detect target switches
            hist = self._leader_target_history[team_key]
            if len(hist) >= 2 and hist[-1] != hist[-2] and hist[-1] is not None and hist[-2] is not None:
                self.target_switches[team_key] += 1

    def _is_adjacent_to_door(self, pos: tuple[int, int], door_tiles: set[tuple[int, int]]) -> bool:
        """Check if pos is Chebyshev distance 1 from any closed door."""
        x, y = pos
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                if dx == 0 and dy == 0:
                    continue
                if (x + dx, y + dy) in door_tiles:
                    return True
        return False

    def _get_adjacent_doors(self, pos: tuple[int, int], door_tiles: set[tuple[int, int]]) -> list[tuple[int, int]]:
        """Return all closed-door tiles adjacent (Chebyshev 1) to pos."""
        x, y = pos
        doors = []
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                if dx == 0 and dy == 0:
                    continue
                nb = (x + dx, y + dy)
                if nb in door_tiles:
                    doors.append(nb)
        return doors

    def _detect_cycles(self, pid: str, team: str, unit=None):
        """Detect repeating position sequences of length 2-8 in recent history."""
        history = self._unit_positions.get(pid, [])
        if len(history) < 6:
            return

        # Check for cycles of length 2 through 8
        for cycle_len in range(2, 9):
            if len(history) < cycle_len * 3:
                continue
            # Check if the last cycle_len*3 positions form a repeating pattern
            recent = history[-(cycle_len * 3):]
            pattern = recent[:cycle_len]
            is_cycle = True
            for i in range(cycle_len, len(recent)):
                if recent[i] != pattern[i % cycle_len]:
                    is_cycle = False
                    break
            if is_cycle:
                if pid not in self.cycles_detected:
                    self.cycles_detected[pid] = {}
                self.cycles_detected[pid][cycle_len] = \
                    self.cycles_detected[pid].get(cycle_len, 0) + 1
                self.oscillation_turns[team] += 1
                # Split into leader vs follower oscillation
                if pid == self.team_leaders.get(team):
                    self.leader_oscillation_turns[team] += 1
                else:
                    self.follower_oscillation_turns[team] += 1
                # Per-class oscillation tracking
                if unit:
                    cls = getattr(unit, "class_id", "unknown")
                    self.class_oscillation_turns[cls] = \
                        self.class_oscillation_turns.get(cls, 0) + 1
                break  # Only count the shortest matching cycle per turn

    def get_final_progress(self) -> dict[str, dict]:
        """Get final exploration progress for all teams."""
        result = {}
        for team_key in ("a", "b", "c", "d"):
            result[team_key] = get_exploration_progress(self.match_id, team_key)
        return result


def render_exploration_report(tracker: ExplorationTracker, all_units: dict, max_turns: int) -> str:
    """Build a comprehensive exploration diagnostics report."""
    lines: list[str] = []
    lines.append(f"\n{'=' * 70}")
    lines.append(f"  EXPLORATION DIAGNOSTICS REPORT")
    lines.append(f"{'=' * 70}")

    # --- Tile Coverage ---
    lines.append(f"\n  +- TILE COVERAGE (unique tiles visited per team) ---------------+")
    walkable = tracker.total_walkable
    for team_key in ("a", "b", "c", "d"):
        visited = len(tracker.tiles_visited.get(team_key, set()))
        pct = visited / walkable * 100 if walkable else 0
        bar_len = int(pct / 5)  # 20 char bar = 100%
        bar = "\033[32m" + "█" * bar_len + "\033[90m" + "░" * (20 - bar_len) + "\033[0m"
        status = "\033[32mGOOD\033[0m" if pct >= 30 else ("\033[33mLOW\033[0m" if pct >= 15 else "\033[31mSTALLED\033[0m")
        lines.append(f"  | {_team_label(team_key):35s}  {bar}  {visited:>4}/{walkable} tiles ({pct:>5.1f}%)  {status}")

        # Leader vs followers breakdown
        leader_id = tracker.team_leaders.get(team_key)
        if leader_id:
            leader_tiles = len(tracker.unit_tiles.get(leader_id, set()))
            leader_unit = all_units.get(leader_id)
            leader_name = getattr(leader_unit, "username", "?") if leader_unit else "?"
            lines.append(f"  |   Leader ({leader_name}): {leader_tiles} unique tiles")
    lines.append(f"  +--------------------------------------------------------------+")

    # --- Room Discovery ---
    final_progress = tracker.get_final_progress()
    lines.append(f"\n  +- ROOM DISCOVERY (rooms found / total) -----------------------+")
    for team_key in ("a", "b", "c", "d"):
        prog = final_progress.get(team_key, {})
        total_rooms = prog.get("total_rooms", 0)
        discovered = prog.get("discovered_rooms", 0)
        cleared = prog.get("cleared_rooms", 0)
        exp_pct = prog.get("exploration_pct", 0)
        clear_pct = prog.get("clearance_pct", 0)
        lines.append(f"  | {_team_label(team_key):35s}  discovered: {discovered}/{total_rooms} ({exp_pct:.0f}%)  cleared: {cleared}/{total_rooms} ({clear_pct:.0f}%)")
    lines.append(f"  +--------------------------------------------------------------+")

    # --- Exploration Timeline ---
    lines.append(f"\n  +- EXPLORATION TIMELINE (rooms discovered over time) ----------+")
    for team_key in ("a", "b", "c", "d"):
        snapshots = tracker.progress_snapshots.get(team_key, [])
        if not snapshots:
            continue
        timeline_parts = []
        for snap in snapshots:
            timeline_parts.append(f"T{snap['turn']}:{snap['discovered']}/{snap['total']}")
        lines.append(f"  | {_team_label(team_key):35s}  {' → '.join(timeline_parts)}")
    lines.append(f"  +--------------------------------------------------------------+")

    # --- Door Interactions ---
    lines.append(f"\n  +- DOOR INTERACTIONS -----------------------------------------+")
    for team_key in ("a", "b", "c", "d"):
        opens = tracker.door_opens.get(team_key, 0)
        failures = tracker.door_approach_failures.get(team_key, 0)
        status = "\033[32m✓\033[0m" if opens > 0 else "\033[31m✗ NEVER OPENED A DOOR\033[0m"
        fail_str = f"  \033[33m({failures} approach failures)\033[0m" if failures > 0 else ""
        lines.append(f"  | {_team_label(team_key):35s}  doors opened: {opens}  {status}{fail_str}")
    lines.append(f"  +--------------------------------------------------------------+")

    # --- Leader Decision Breakdown ---
    lines.append(f"\n  +- LEADER DECISION BREAKDOWN ---------------------------------+")
    for team_key in ("a", "b", "c", "d"):
        leader_id = tracker.team_leaders.get(team_key)
        if not leader_id:
            continue
        reasons = tracker.leader_reasons.get(leader_id, {})
        if not reasons:
            continue
        leader_unit = all_units.get(leader_id)
        leader_name = getattr(leader_unit, "username", "?") if leader_unit else "?"
        leader_class = getattr(leader_unit, "class_id", "?") if leader_unit else "?"
        total_decisions = sum(reasons.values())

        # Calculate explore↔patrol alternation rate from position data
        reason_list = []
        # We need to reconstruct the per-turn reason sequence; use the reason
        # counts as a proxy — the ratio of explore+patrol+directed to total
        explore_count = reasons.get("explore_room", 0)
        patrol_count = reasons.get("patrol_move", 0)
        directed_count = reasons.get("directed_adjacent_move", 0)
        osc_suppressed = reasons.get("oscillation_suppressed", 0)
        productive = total_decisions - explore_count - patrol_count - directed_count - osc_suppressed

        lines.append(f"  | {_team_label(team_key)} leader: {leader_name} ({leader_class})  —  {total_decisions} decisions")

        # Sort by count descending, show top 8
        sorted_reasons = sorted(reasons.items(), key=lambda kv: kv[1], reverse=True)
        for reason, count in sorted_reasons[:8]:
            pct = count / total_decisions * 100 if total_decisions else 0
            bar_len = int(pct / 5)
            bar = "█" * bar_len
            lines.append(f"  |     {reason:30s} {count:>4} ({pct:>5.1f}%)  {bar}")

        # Flag problematic patterns
        wander_pct = (explore_count + patrol_count + directed_count) / total_decisions * 100 if total_decisions else 0
        if wander_pct > 70 and productive < total_decisions * 0.2:
            lines.append(f"  |     \033[31m⚠ {wander_pct:.0f}% of decisions are explore/patrol shuffling — likely stuck\033[0m")
    lines.append(f"  +--------------------------------------------------------------+")

    # --- All-Hero Reason Summary (Phase 32D/E) ---
    if tracker.all_reason_counts:
        total_all = sum(tracker.all_reason_counts.values())
        lines.append(f"\n  +- AI BEHAVIOR REASON SUMMARY (all heroes, {total_all} total) --------+")
        sorted_all = sorted(tracker.all_reason_counts.items(), key=lambda kv: kv[1], reverse=True)
        for reason, count in sorted_all[:20]:
            pct = count / total_all * 100 if total_all else 0
            bar_len = int(pct / 2)
            bar = "█" * bar_len
            lines.append(f"  |  {reason:35s} {count:>5} ({pct:>5.1f}%)  {bar}")
        if len(sorted_all) > 20:
            remaining = sum(c for _, c in sorted_all[20:])
            lines.append(f"  |  {'... +' + str(len(sorted_all) - 20) + ' more reasons':35s} {remaining:>5}")
        # Dynamic stance breakdowns — auto-discovers all reasons by prefix
        _stance_sections = [
            ("FOLLOW STANCE", "follow_"),
            ("AGGRESSIVE STANCE", "agg_"),
            ("DEFENSIVE STANCE", "def_"),
            ("HOLD STANCE", "hold_"),
        ]
        # Extra diagnostic reasons appended to the follow section
        _follow_extras = ("oscillation_suppressed", "stall_breaker_yield")
        for section_label, prefix in _stance_sections:
            hits = {k: v for k, v in tracker.all_reason_counts.items()
                    if k.startswith(prefix) and v > 0}
            if prefix == "follow_":
                for extra in _follow_extras:
                    val = tracker.all_reason_counts.get(extra, 0)
                    if val > 0:
                        hits[extra] = val
            if hits:
                lines.append(f"  |  {'─' * 55}")
                lines.append(f"  |  {section_label} METRICS:")
                for k, v in sorted(hits.items(), key=lambda kv: kv[1], reverse=True):
                    pct = v / total_all * 100 if total_all else 0
                    lines.append(f"  |    {k:33s} {v:>5} ({pct:>5.1f}%)")
        lines.append(f"  +--------------------------------------------------------------+")

    # --- Oscillation / Cycle Detection ---
    lines.append(f"\n  +- OSCILLATION & CYCLE DETECTION -----------------------------+")
    any_cycles = False
    for team_key in ("a", "b", "c", "d"):
        osc_turns = tracker.oscillation_turns.get(team_key, 0)
        if osc_turns == 0:
            continue
        any_cycles = True
        osc_pct = osc_turns / max_turns * 100
        lines.append(f"  | {_team_label(team_key):35s}  {osc_turns} turns in detected cycles ({osc_pct:.1f}% of match)")

        # Show per-unit cycle details
        for uid, cycles in tracker.cycles_detected.items():
            unit = all_units.get(uid)
            if not unit or getattr(unit, "team", "") != team_key:
                continue
            uname = getattr(unit, "username", uid[:12])
            is_leader = uid == tracker.team_leaders.get(team_key)
            leader_tag = " ★LEADER" if is_leader else ""
            cycle_strs = [f"len-{cl}:×{cnt}" for cl, cnt in sorted(cycles.items())]
            lines.append(f"  |     {uname}{leader_tag}: {', '.join(cycle_strs)}")

    if not any_cycles:
        lines.append(f"  |  \033[32m[OK] No sustained oscillation cycles detected\033[0m")
    lines.append(f"  +--------------------------------------------------------------+")

    # --- Leader vs Follower Oscillation Breakdown ---
    lines.append(f"\n  +- OSCILLATION BREAKDOWN (leader vs followers) ---------------+")
    for team_key in ("a", "b", "c", "d"):
        leader_osc = tracker.leader_oscillation_turns.get(team_key, 0)
        follower_osc = tracker.follower_oscillation_turns.get(team_key, 0)
        total_osc = leader_osc + follower_osc
        if total_osc == 0:
            continue
        leader_pct = leader_osc / total_osc * 100 if total_osc else 0
        follower_pct = follower_osc / total_osc * 100 if total_osc else 0
        lines.append(f"  | {_team_label(team_key):35s}  leader: {leader_osc} ({leader_pct:.0f}%)  followers: {follower_osc} ({follower_pct:.0f}%)")
    lines.append(f"  +--------------------------------------------------------------+")

    # --- Leader Stall Analysis ---
    lines.append(f"\n  +- LEADER STALL ANALYSIS ------------------------------------+")
    for team_key in ("a", "b", "c", "d"):
        leader_id = tracker.team_leaders.get(team_key)
        if not leader_id:
            continue
        leader_unit = all_units.get(leader_id)
        leader_name = getattr(leader_unit, "username", "?") if leader_unit else "?"
        supp_turns = tracker.suppression_turns.get(team_key, 0)
        supp_pct = supp_turns / max_turns * 100 if max_turns else 0
        n_unique = len(tracker.unique_targets.get(team_key, set()))
        n_switches = tracker.target_switches.get(team_key, 0)
        target_hist = tracker._leader_target_history.get(team_key, [])

        # Compute "stuck on same target" — longest consecutive run of same room_id
        max_consecutive = 0
        cur_run = 0
        prev_rid = None
        for rid in target_hist:
            if rid is not None and rid == prev_rid:
                cur_run += 1
                max_consecutive = max(max_consecutive, cur_run)
            else:
                cur_run = 1
            prev_rid = rid

        lines.append(f"  | {_team_label(team_key)} leader: {leader_name}")
        lines.append(f"  |     Suppressed turns:      {supp_turns}/{max_turns} ({supp_pct:.0f}%)")
        lines.append(f"  |     Unique rooms targeted:  {n_unique}")
        lines.append(f"  |     Target switches:        {n_switches}")
        lines.append(f"  |     Max consecutive same:   {max_consecutive} turns")
        n_skips = tracker.rooms_skipped.get(team_key, 0)
        if n_skips:
            lines.append(f"  |     Rooms skipped (unreachable): {n_skips}")
        # RC#3: No-target turns & last progress turn
        no_tgt = tracker.no_target_turns.get(team_key, 0)
        if no_tgt:
            lines.append(f"  |     No exploration target:  {no_tgt} turns (all rooms cleared or skipped)")
        last_prog = tracker.last_progress_turn.get(team_key, 0)
        if last_prog > 0 and last_prog < max_turns - 20:
            lines.append(f"  |     \033[33m⚠ Last forward progress at T{last_prog} — exploration stalled for {max_turns - last_prog} turns\033[0m")
        elif last_prog == 0:
            lines.append(f"  |     \033[31m⚠ Leader never made forward progress toward any target\033[0m")
        # Flag issues
        if supp_pct > 20:
            lines.append(f"  |     \033[31m⚠ Suppressed {supp_pct:.0f}% of match — explore blocked too often\033[0m")
        if max_consecutive > 40:
            lines.append(f"  |     \033[31m⚠ Stuck targeting same room for {max_consecutive} turns — likely unreachable\033[0m")
        if n_switches == 0 and n_unique <= 1:
            lines.append(f"  |     \033[33m⚠ Never switched targets — only ever had 1 exploration target\033[0m")
    lines.append(f"  +--------------------------------------------------------------+")

    # --- RC#3: Per-Room Skip Log ---
    any_skips = any(tracker.room_skip_log[t] for t in ("a", "b", "c", "d"))
    if any_skips:
        lines.append(f"\n  +- ROOM SKIP LOG (rooms marked unreachable) ------------------+")
        room_info = get_room_info(tracker.match_id)
        for team_key in ("a", "b", "c", "d"):
            skips = tracker.room_skip_log[team_key]
            if not skips:
                continue
            lines.append(f"  | {_team_label(team_key)}:")
            for turn, rid, reason, count in skips[-10:]:
                rname = room_info.get(rid, {}).get("name", rid) if room_info else rid
                perm_tag = " \033[31m[PERMANENT]\033[0m" if count >= 4 else ""
                lines.append(f"  |   T{turn:>3}  {rname:20s}  skip #{count}  ({reason}){perm_tag}")
            if len(skips) > 10:
                lines.append(f"  |   ... {len(skips) - 10} more skips omitted")
        lines.append(f"  +--------------------------------------------------------------+")

    # --- RC#3: Door-Blocked Room Analysis ---
    door_room_map = _door_rooms.get(tracker.match_id, {})
    room_info = get_room_info(tracker.match_id)
    if door_room_map and room_info:
        lines.append(f"\n  +- DOOR-BLOCKED ROOM ANALYSIS --------------------------------+")
        final_progress = tracker.get_final_progress()
        for team_key in ("a", "b", "c", "d"):
            discovery = get_room_discovery(tracker.match_id, team_key)
            undiscovered = [rid for rid, st in discovery.items() if st == "undiscovered"]
            if not undiscovered:
                continue
            blocked = []
            for rid in undiscovered:
                # Find doors connecting to this room
                connecting_doors = []
                for dkey, rooms_touching in door_room_map.items():
                    if rid in rooms_touching:
                        connecting_doors.append(dkey)
                if connecting_doors:
                    rname = room_info.get(rid, {}).get("name", rid)
                    door_strs = [f"({d})" for d in connecting_doors[:3]]
                    blocked.append(f"{rname} via door{'s' if len(connecting_doors) > 1 else ''} {', '.join(door_strs)}")
            if blocked:
                lines.append(f"  | {_team_label(team_key)}: {len(undiscovered)} undiscovered rooms")
                for b in blocked[:5]:
                    lines.append(f"  |   → {b}")
                if len(blocked) > 5:
                    lines.append(f"  |   ... {len(blocked) - 5} more")
        lines.append(f"  +--------------------------------------------------------------+")

    # --- Door Approach Detail Log ---
    if tracker.door_approach_details:
        lines.append(f"\n  +- DOOR APPROACH FAILURES (detail log) -----------------------+")
        # Show up to 15 most recent failures
        shown = tracker.door_approach_details[-15:]
        for d in shown:
            doors_str = ", ".join(str(p) for p in d["door_pos"])
            ent_str = str(d["target_entrance"]) if d["target_entrance"] else "?"
            lines.append(
                f"  |  T{d['turn']:>3} {_team_label(d['team']):15s}  "
                f"leader@{d['leader_pos']}  door@[{doors_str}]  "
                f"A*→{d['next_step']}  target_ent={ent_str}"
            )
        if len(tracker.door_approach_details) > 15:
            lines.append(f"  |  ... {len(tracker.door_approach_details) - 15} more failures omitted")
        lines.append(f"  +--------------------------------------------------------------+")

    # --- Per-Class Oscillation Summary ---
    if tracker.class_oscillation_turns:
        lines.append(f"\n  +- PER-CLASS OSCILLATION SUMMARY -----------------------------+")
        sorted_classes = sorted(
            tracker.class_oscillation_turns.items(),
            key=lambda kv: kv[1], reverse=True,
        )
        for cls, osc in sorted_classes:
            n_units = tracker.class_unit_count.get(cls, 1)
            avg_osc = osc / n_units
            bar_len = min(20, int(avg_osc / 5))
            bar = "\033[31m" + "█" * bar_len + "\033[0m"
            lines.append(f"  |  {cls:20s}  total: {osc:>4} turns  across {n_units} units  avg: {avg_osc:>5.1f}/unit  {bar}")
        lines.append(f"  +--------------------------------------------------------------+")

    # --- Leader Distance-to-Target Trend ---
    lines.append(f"\n  +- LEADER DISTANCE-TO-TARGET TREND ---------------------------+")
    for team_key in ("a", "b", "c", "d"):
        dists = tracker.leader_distance_to_target.get(team_key, [])
        valid = [d for d in dists if d is not None]
        if not valid:
            continue
        avg_dist = sum(valid) / len(valid)
        min_dist = min(valid)
        max_dist = max(valid)
        # Check if distance is decreasing (progressing) or stagnant
        if len(valid) >= 10:
            first_quarter = valid[:len(valid)//4]
            last_quarter = valid[-(len(valid)//4):]
            avg_first = sum(first_quarter) / len(first_quarter) if first_quarter else 0
            avg_last = sum(last_quarter) / len(last_quarter) if last_quarter else 0
            if avg_last < avg_first * 0.7:
                trend = "\033[32m↓ PROGRESSING\033[0m"
            elif avg_last > avg_first * 1.1:
                trend = "\033[31m↑ REGRESSING\033[0m"
            else:
                trend = "\033[33m→ STAGNANT\033[0m"
        else:
            trend = "—"
        lines.append(f"  | {_team_label(team_key):35s}  avg:{avg_dist:>5.1f}  min:{min_dist:>3}  max:{max_dist:>3}  {trend}")
    lines.append(f"  +--------------------------------------------------------------+")

    # --- Exploration Health Score ---
    lines.append(f"\n  +- EXPLORATION HEALTH SCORE ----------------------------------+")
    score = 100
    deductions: list[str] = []

    for team_key in ("a", "b", "c", "d"):
        # Tile coverage penalty
        visited = len(tracker.tiles_visited.get(team_key, set()))
        if tracker.total_walkable > 0:
            pct = visited / tracker.total_walkable * 100
            if pct < 5:
                score -= 15
                deductions.append(f"-15 {_team_label(team_key)} tile coverage critically low ({pct:.1f}%)")
            elif pct < 15:
                score -= 8
                deductions.append(f"-8 {_team_label(team_key)} tile coverage low ({pct:.1f}%)")

        # Room discovery penalty
        prog = final_progress.get(team_key, {})
        total_rooms = prog.get("total_rooms", 1)
        discovered = prog.get("discovered_rooms", 0)
        if total_rooms > 0 and discovered / total_rooms < 0.2:
            score -= 10
            deductions.append(f"-10 {_team_label(team_key)} discovered < 20% of rooms ({discovered}/{total_rooms})")

        # Door opens penalty
        door_opens = tracker.door_opens.get(team_key, 0)
        if door_opens == 0:
            score -= 8
            deductions.append(f"-8 {_team_label(team_key)} never opened a door")

        # Oscillation penalty
        osc_turns = tracker.oscillation_turns.get(team_key, 0)
        if osc_turns > max_turns * 0.3:
            score -= 10
            deductions.append(f"-10 {_team_label(team_key)} sustained oscillation ({osc_turns} turns)")
        elif osc_turns > max_turns * 0.1:
            score -= 5
            deductions.append(f"-5 {_team_label(team_key)} oscillation ({osc_turns} turns)")

    score = max(0, min(100, score))
    if score >= 80:
        grade = f"\033[32m{score}/100 — HEALTHY\033[0m"
    elif score >= 50:
        grade = f"\033[33m{score}/100 — ROOM FOR IMPROVEMENT\033[0m"
    else:
        grade = f"\033[31m{score}/100 — STALLING DETECTED\033[0m"
    lines.append(f"  |  Score: {grade}")
    for d in deductions:
        lines.append(f"  |    {d}")
    if not deductions:
        lines.append(f"  |    No deductions — all teams exploring effectively")
    lines.append(f"  +--------------------------------------------------------------+")

    return "\n".join(lines)


# ─── Equipment Report Tracker ────────────────────────────────────────────────

class EquipmentTracker:
    """Collects equipment management events across the match for diagnostics."""

    def __init__(self):
        # Per-hero snapshots: {player_id: {class_id, username, team, ...}}
        self.hero_spawn_gear: dict[str, dict] = {}  # equipment at spawn
        self.hero_final_gear: dict[str, dict] = {}  # equipment at end
        # Event counters
        self.items_picked_up: list[dict] = []       # {player_id, items: [...]}
        self.items_traded: list[dict] = []           # {from_id, to_id, item_name}
        self.items_equipped: list[dict] = []         # {player_id, item_name, slot}
        self.items_purged: list[dict] = []           # {player_id, item_name}
        self.potions_shared: list[dict] = []         # {from_id, to_id, item_name}
        self.potions_used: list[dict] = []           # {player_id, item_name}
        self.scavenge_moves: dict[str, int] = {}     # {player_id: count}
        # Diagnostics
        self.weapon_class_violations: list[dict] = []  # items equipped by wrong class
        self.armor_mismatch: list[dict] = []           # armor not matching preferred
        self.inventory_overflow: list[dict] = []       # units exceeding capacity
        self.stranded_upgrades: int = 0                  # items in inventory that could upgrade someone

    def snapshot_spawn_gear(self, all_units: dict):
        """Capture equipment state at match start."""
        for uid, unit in all_units.items():
            team = getattr(unit, 'team', '')
            if team not in ('a', 'b', 'c', 'd'):
                continue
            self.hero_spawn_gear[uid] = {
                'player_id': uid,
                'username': getattr(unit, 'username', '?'),
                'class_id': getattr(unit, 'class_id', '?'),
                'team': team,
                'weapon': _item_summary(unit.equipment.get('weapon')),
                'armor': _item_summary(unit.equipment.get('armor')),
                'accessory': _item_summary(unit.equipment.get('accessory')),
                'inventory_count': len(unit.inventory),
                'potion_count': sum(1 for i in unit.inventory if isinstance(i, dict) and i.get('item_type') == 'consumable'),
            }

    def snapshot_final_gear(self, all_units: dict):
        """Capture equipment state at match end."""
        for uid, unit in all_units.items():
            team = getattr(unit, 'team', '')
            if team not in ('a', 'b', 'c', 'd'):
                continue
            self.hero_final_gear[uid] = {
                'player_id': uid,
                'username': getattr(unit, 'username', '?'),
                'class_id': getattr(unit, 'class_id', '?'),
                'team': team,
                'is_alive': unit.is_alive,
                'weapon': _item_summary(unit.equipment.get('weapon')),
                'armor': _item_summary(unit.equipment.get('armor')),
                'accessory': _item_summary(unit.equipment.get('accessory')),
                'inventory_count': len(unit.inventory),
                'potion_count': sum(1 for i in unit.inventory if isinstance(i, dict) and i.get('item_type') == 'consumable'),
            }

    def collect_turn_events(self, turn_result, all_units: dict, actions: list):
        """Extract equipment-related events from a resolved turn."""
        # Items picked up
        for ip in turn_result.items_picked_up:
            pid = ip.get('player_id', '')
            items = ip.get('items', [])
            unit = all_units.get(pid)
            if unit and getattr(unit, 'team', '') in ('a', 'b', 'c', 'd'):
                self.items_picked_up.append({'player_id': pid, 'items': items})

        # Parse action results for equipment events
        for act in turn_result.actions:
            msg = getattr(act, 'message', '') or ''
            pid = act.player_id
            unit = all_units.get(pid)
            if not unit or getattr(unit, 'team', '') not in ('a', 'b', 'c', 'd'):
                continue

            if 'received' in msg and 'from' in msg:
                # Could be trade or potion share
                item_name = msg.split('received ')[-1].split(' from')[0] if 'received' in msg else ''
                from_name = msg.split('from ')[-1] if 'from' in msg else ''
                if 'potion' in item_name.lower():
                    self.potions_shared.append({'to_id': pid, 'to_name': getattr(unit, 'username', ''), 'from_name': from_name, 'item_name': item_name})
                else:
                    self.items_traded.append({'to_id': pid, 'to_name': getattr(unit, 'username', ''), 'from_name': from_name, 'item_name': item_name})
            elif 'equipped' in msg:
                item_name = msg.split('equipped ')[-1] if 'equipped' in msg else ''
                self.items_equipped.append({'player_id': pid, 'username': getattr(unit, 'username', ''), 'item_name': item_name})
            elif 'destroyed' in msg and 'no upgrade' in msg:
                item_name = msg.split('destroyed ')[-1].split(' (')[0] if 'destroyed' in msg else ''
                self.items_purged.append({'player_id': pid, 'username': getattr(unit, 'username', ''), 'item_name': item_name})

        # Items used (potions)
        for iu in turn_result.items_used:
            pid = iu.get('player_id', '')
            unit = all_units.get(pid)
            if unit and getattr(unit, 'team', '') in ('a', 'b', 'c', 'd'):
                self.potions_used.append({'player_id': pid, 'username': getattr(unit, 'username', ''), 'item_name': iu.get('item_name', 'potion')})

        # Scavenge moves
        for act in actions:
            reason = getattr(act, 'reason', '') or ''
            if 'scavenge' in reason:
                pid = act.player_id
                self.scavenge_moves[pid] = self.scavenge_moves.get(pid, 0) + 1

    def run_diagnostics(self, all_units: dict):
        """Check for equipment management problems."""
        from app.models.items import INVENTORY_MAX_CAPACITY
        for uid, unit in all_units.items():
            team = getattr(unit, 'team', '')
            if team not in ('a', 'b', 'c', 'd'):
                continue
            class_id = getattr(unit, 'class_id', '')
            class_def = get_class_definition(class_id)
            if not class_def:
                continue

            # Check weapon class-lock
            weapon = unit.equipment.get('weapon')
            if weapon and isinstance(weapon, dict):
                wcat = weapon.get('weapon_category', '')
                allowed = getattr(class_def, 'allowed_weapon_categories', []) or []
                if wcat and allowed and wcat not in allowed:
                    self.weapon_class_violations.append({
                        'player_id': uid,
                        'username': getattr(unit, 'username', '?'),
                        'class_id': class_id,
                        'weapon': weapon.get('name', '?'),
                        'weapon_category': wcat,
                        'allowed': allowed,
                    })

            # Check armor affinity
            armor = unit.equipment.get('armor')
            if armor and isinstance(armor, dict):
                acat = armor.get('armor_category', '')
                preferred = getattr(class_def, 'preferred_armor', '')
                if acat and preferred and acat != preferred:
                    self.armor_mismatch.append({
                        'player_id': uid,
                        'username': getattr(unit, 'username', '?'),
                        'class_id': class_id,
                        'armor': armor.get('name', '?'),
                        'armor_category': acat,
                        'preferred': preferred,
                    })

            # Check inventory overflow
            if len(unit.inventory) > INVENTORY_MAX_CAPACITY:
                self.inventory_overflow.append({
                    'player_id': uid,
                    'username': getattr(unit, 'username', '?'),
                    'inventory_size': len(unit.inventory),
                    'max': INVENTORY_MAX_CAPACITY,
                })

        # Check for stranded upgrades across all teams
        for uid, unit in all_units.items():
            team = getattr(unit, 'team', '')
            if team not in ('a', 'b', 'c', 'd'):
                continue
            inv_items = [i for i in unit.inventory if isinstance(i, dict) and i.get("item_type") != "consumable"]
            if not inv_items:
                continue
            team_members = [
                u for u in all_units.values()
                if getattr(u, 'team', '') == team and u.is_alive
                and getattr(u, 'enemy_type', None) is None
            ]
            for item in inv_items:
                slot = item.get('equip_slot')
                if not slot:
                    continue
                for member in team_members:
                    mcid = getattr(member, 'class_id', '')
                    if slot == "weapon":
                        wcat = item.get("weapon_category", "")
                        if wcat:
                            member_class_def = get_class_definition(mcid)
                            allowed = getattr(member_class_def, 'allowed_weapon_categories', []) if member_class_def else []
                            if wcat not in allowed:
                                continue
                    role = _CLASS_ROLE_MAP.get(mcid, 'aggressive')
                    item_score = score_item_for_role(item, role)
                    current = getattr(member, 'equipment', {}).get(slot)
                    current_score = score_item_for_role(current, role) if current else 0.0
                    if item_score - current_score > 0:
                        self.stranded_upgrades += 1
                        break  # Count each item once


def _item_summary(item: dict | None) -> str:
    """One-line summary of an item for equipment reports."""
    if not item or not isinstance(item, dict):
        return "(empty)"
    name = item.get('name', '?')
    rarity = item.get('rarity', '')
    return f"{name} [{rarity}]" if rarity else name


def render_equipment_report(tracker: EquipmentTracker, all_units: dict) -> str:
    """Build a comprehensive equipment management report."""
    lines: list[str] = []
    lines.append(f"\n{'=' * 70}")
    lines.append(f"  EQUIPMENT MANAGEMENT REPORT")
    lines.append(f"{'=' * 70}")

    # --- Spawn Gear Summary ---
    lines.append(f"\n  +- SPAWN GEAR -----------------------------------------------+")
    for team_key in ('a', 'b', 'c', 'd'):
        team_heroes = [h for h in tracker.hero_spawn_gear.values() if h['team'] == team_key]
        if not team_heroes:
            continue
        lines.append(f"  | {_team_label(team_key)}:")
        for h in team_heroes:
            slots_filled = sum(1 for s in ('weapon', 'armor', 'accessory') if h[s] != '(empty)')
            lines.append(f"  |   {h['username']:20s} {h['class_id']:15s} | {slots_filled}/3 slots | {h['potion_count']} potions")
            lines.append(f"  |     W: {h['weapon']:25s} A: {h['armor']:25s} Acc: {h['accessory']}")
    lines.append(f"  +------------------------------------------------------------+")

    # --- Event Summary ---
    lines.append(f"\n  +- EQUIPMENT EVENTS -----------------------------------------+")
    total_pickups = sum(len(e['items']) for e in tracker.items_picked_up)
    lines.append(f"  |  Items picked up:          {total_pickups:>5}")
    lines.append(f"  |  Items traded to teammate:  {len(tracker.items_traded):>5}")
    lines.append(f"  |  Items auto-equipped:       {len(tracker.items_equipped):>5}")
    lines.append(f"  |  Items purged (no upgrade): {len(tracker.items_purged):>5}")
    lines.append(f"  |  Potions shared:            {len(tracker.potions_shared):>5}")
    lines.append(f"  |  Potions consumed:          {len(tracker.potions_used):>5}")
    lines.append(f"  |  Scavenge moves (loot-seek):{sum(tracker.scavenge_moves.values()):>5}")
    lines.append(f"  +------------------------------------------------------------+")

    # --- Per-Team Breakdown ---
    lines.append(f"\n  +- PER-TEAM BREAKDOWN ---------------------------------------+")
    for team_key in ('a', 'b', 'c', 'd'):
        team_ids = {h['player_id'] for h in tracker.hero_spawn_gear.values() if h['team'] == team_key}
        if not team_ids:
            continue
        t_pickups = sum(len(e['items']) for e in tracker.items_picked_up if e['player_id'] in team_ids)
        t_trades = sum(1 for e in tracker.items_traded if e['to_id'] in team_ids)
        t_equips = sum(1 for e in tracker.items_equipped if e['player_id'] in team_ids)
        t_purges = sum(1 for e in tracker.items_purged if e['player_id'] in team_ids)
        t_potions_shared = sum(1 for e in tracker.potions_shared if e['to_id'] in team_ids)
        t_potions_used = sum(1 for e in tracker.potions_used if e['player_id'] in team_ids)
        t_scavenges = sum(c for pid, c in tracker.scavenge_moves.items() if pid in team_ids)
        lines.append(f"  | {_team_label(team_key):35s} pickup:{t_pickups:>3}  trade:{t_trades:>3}  equip:{t_equips:>3}  purge:{t_purges:>3}  pot-share:{t_potions_shared:>3}  pot-use:{t_potions_used:>3}  scav:{t_scavenges:>3}")
    lines.append(f"  +------------------------------------------------------------+")

    # --- Final Gear & Upgrade Check ---
    lines.append(f"\n  +- FINAL GEAR -----------------------------------------------+")
    for team_key in ('a', 'b', 'c', 'd'):
        team_heroes = [h for h in tracker.hero_final_gear.values() if h['team'] == team_key]
        if not team_heroes:
            continue
        lines.append(f"  | {_team_label(team_key)}:")
        for h in team_heroes:
            status = "ALIVE" if h['is_alive'] else "DEAD"
            slots_filled = sum(1 for s in ('weapon', 'armor', 'accessory') if h[s] != '(empty)')
            # Compare spawn vs final
            spawn = tracker.hero_spawn_gear.get(h['player_id'], {})
            upgrades = 0
            for s in ('weapon', 'armor', 'accessory'):
                if spawn.get(s, '(empty)') != h.get(s, '(empty)') and h.get(s) != '(empty)':
                    upgrades += 1
            lines.append(f"  |   {h['username']:20s} {status:5s} | {slots_filled}/3 slots | {h['potion_count']} pots | {upgrades} upgraded | inv:{h['inventory_count']}")
            lines.append(f"  |     W: {h['weapon']:25s} A: {h['armor']:25s} Acc: {h['accessory']}")
    lines.append(f"  +------------------------------------------------------------+")

    # --- Potion Economy ---
    lines.append(f"\n  +- POTION ECONOMY -------------------------------------------+")
    for team_key in ('a', 'b', 'c', 'd'):
        spawn_heroes = [h for h in tracker.hero_spawn_gear.values() if h['team'] == team_key]
        final_heroes = [h for h in tracker.hero_final_gear.values() if h['team'] == team_key]
        if not spawn_heroes:
            continue
        start_pots = sum(h['potion_count'] for h in spawn_heroes)
        end_pots = sum(h['potion_count'] for h in final_heroes)
        end_distribution = [h['potion_count'] for h in final_heroes if h['is_alive']]
        balance_str = ', '.join(str(p) for p in end_distribution) if end_distribution else 'all dead'
        max_diff = (max(end_distribution) - min(end_distribution)) if len(end_distribution) >= 2 else 0
        balance_ok = "BALANCED" if max_diff <= 1 else f"UNBALANCED (diff={max_diff})"
        lines.append(f"  | {_team_label(team_key):35s} start:{start_pots:>3}  end:{end_pots:>3}  per-hero:[{balance_str}]  {balance_ok}")
    lines.append(f"  +------------------------------------------------------------+")

    # --- Diagnostics ---
    has_issues = tracker.weapon_class_violations or tracker.armor_mismatch or tracker.inventory_overflow
    if has_issues:
        lines.append(f"\n  +- DIAGNOSTICS (ISSUES FOUND) --------------------------------+")
        for v in tracker.weapon_class_violations:
            lines.append(f"  |  \033[31mWEAPON CLASS VIOLATION\033[0m: {v['username']} ({v['class_id']}) has {v['weapon']} [{v['weapon_category']}] -- allowed: {v['allowed']}")
        for v in tracker.armor_mismatch:
            lines.append(f"  |  \033[33mARMOR MISMATCH\033[0m: {v['username']} ({v['class_id']}) wearing {v['armor']} [{v['armor_category']}] -- prefers: {v['preferred']}")
        for v in tracker.inventory_overflow:
            lines.append(f"  |  \033[31mINVENTORY OVERFLOW\033[0m: {v['username']} has {v['inventory_size']}/{v['max']} items")
        lines.append(f"  +------------------------------------------------------------+")
    else:
        lines.append(f"\n  +- DIAGNOSTICS -----------------------------------------------+")
        lines.append(f"  |  \033[32m[OK] No weapon class-lock violations\033[0m")
        lines.append(f"  |  \033[32m[OK] No inventory overflow detected\033[0m")
        n_mismatch = len(tracker.armor_mismatch)
        if n_mismatch == 0:
            lines.append(f"  |  \033[32m[OK] All heroes wearing preferred armor type\033[0m")
        lines.append(f"  +------------------------------------------------------------+")

    # --- Inventory Contents (surviving heroes with items in bag) ---
    heroes_with_inv = []
    for uid, unit in all_units.items():
        team = getattr(unit, 'team', '')
        if team not in ('a', 'b', 'c', 'd'):
            continue
        if not unit.is_alive:
            continue
        inv_items = [i for i in unit.inventory if isinstance(i, dict) and i.get("item_type") != "consumable"]
        if inv_items:
            heroes_with_inv.append((uid, unit, inv_items))

    if heroes_with_inv:
        lines.append(f"\n  +- INVENTORY CONTENTS (equippable items in bag) -------------+")
        for uid, unit, inv_items in heroes_with_inv:
            uname = getattr(unit, 'username', '?')
            cid = getattr(unit, 'class_id', '?')
            team = getattr(unit, 'team', '?')
            lines.append(f"  | {_team_label(team)} {uname} ({cid}) — {len(inv_items)} equippable item(s):")
            for item in inv_items:
                slot = item.get('equip_slot', '?')
                name = item.get('name', '?')
                rarity = item.get('rarity', '')
                wcat = item.get('weapon_category', '')
                acat = item.get('armor_category', '')
                cat_str = f" [{wcat}]" if wcat else (f" [{acat}]" if acat else "")
                role = _CLASS_ROLE_MAP.get(cid, 'aggressive')
                item_score = score_item_for_role(item, role)
                current = getattr(unit, 'equipment', {}).get(slot)
                current_score = score_item_for_role(current, role) if current else 0.0
                delta = item_score - current_score
                if delta > 0:
                    delta_str = f"\033[32m+{delta:.1f} UPGRADE for self\033[0m"
                elif delta == 0:
                    delta_str = f"\033[33m±0 SIDEGRADE\033[0m"
                else:
                    delta_str = f"\033[90m{delta:.1f} vs equipped\033[0m"
                lines.append(f"  |     {slot:10s} {name} [{rarity}]{cat_str} score={item_score:.1f} ({delta_str})")
        lines.append(f"  +------------------------------------------------------------+")

    # --- Stranded Upgrades (items in Hero A's bag that upgrade Hero B) ---
    stranded: list[str] = []
    stranded_count = 0
    for uid, unit in all_units.items():
        team = getattr(unit, 'team', '')
        if team not in ('a', 'b', 'c', 'd'):
            continue
        inv_items = [i for i in unit.inventory if isinstance(i, dict) and i.get("item_type") != "consumable"]
        if not inv_items:
            continue
        # Get all living teammates (including self)
        team_members = [
            u for u in all_units.values()
            if getattr(u, 'team', '') == team and u.is_alive
            and getattr(u, 'enemy_type', None) is None
        ]
        for item in inv_items:
            slot = item.get('equip_slot')
            if not slot:
                continue
            for member in team_members:
                mid = member.player_id
                mname = getattr(member, 'username', '?')
                mcid = getattr(member, 'class_id', '?')
                # Check class lock for weapons
                if slot == "weapon":
                    wcat = item.get("weapon_category", "")
                    if wcat:
                        member_class_def = get_class_definition(mcid)
                        allowed = getattr(member_class_def, 'allowed_weapon_categories', []) if member_class_def else []
                        if wcat not in allowed:
                            continue
                role = _CLASS_ROLE_MAP.get(mcid, 'aggressive')
                item_score = score_item_for_role(item, role)
                current = getattr(member, 'equipment', {}).get(slot)
                current_score = score_item_for_role(current, role) if current else 0.0
                delta = item_score - current_score
                if delta > 0:
                    holder_name = getattr(unit, 'username', '?')
                    is_self = (uid == mid)
                    target_label = "SELF" if is_self else f"{mname} ({mcid})"
                    stranded.append(
                        f"  |  \033[31mSTRANDED UPGRADE\033[0m: {holder_name} has {item.get('name','?')} [{slot}] → "
                        f"+{delta:.1f} upgrade for {target_label}"
                    )
                    stranded_count += 1

    if stranded:
        lines.append(f"\n  +- STRANDED UPGRADES ({stranded_count} found) ----------------------------+")
        lines.append(f"  |  Items sitting in inventory that ARE upgrades for a teammate")
        lines.append(f"  |  (or self) but were never equipped or traded:")
        for s in stranded:
            lines.append(s)
        lines.append(f"  +------------------------------------------------------------+")
    else:
        lines.append(f"\n  +- STRANDED UPGRADES -----------------------------------------+")
        lines.append(f"  |  \033[32m[OK] No equippable upgrades lingering in any inventory\033[0m")
        lines.append(f"  +------------------------------------------------------------+")

    # --- Health Score ---
    lines.append(f"\n  +- EQUIPMENT SYSTEM HEALTH SCORE -----------------------------+")
    score = 100
    deductions: list[str] = []
    # Weapon violations = critical
    wv = len(tracker.weapon_class_violations)
    if wv:
        score -= wv * 20
        deductions.append(f"-{wv * 20} weapon class violations ({wv})")
    # Armor mismatch = moderate
    am = len(tracker.armor_mismatch)
    total_heroes = len(tracker.hero_final_gear)
    alive_heroes = sum(1 for h in tracker.hero_final_gear.values() if h['is_alive'])
    if am and alive_heroes:
        pct = am / alive_heroes * 100
        if pct > 50:
            penalty = 15
        elif pct > 25:
            penalty = 8
        else:
            penalty = 3
        score -= penalty
        deductions.append(f"-{penalty} armor mismatches ({am}/{alive_heroes} alive heroes)")
    # Inventory overflow = critical
    iof = len(tracker.inventory_overflow)
    if iof:
        score -= iof * 15
        deductions.append(f"-{iof * 15} inventory overflows ({iof})")
    # Potion balance check
    for team_key in ('a', 'b', 'c', 'd'):
        final_heroes = [h for h in tracker.hero_final_gear.values() if h['team'] == team_key and h['is_alive']]
        if len(final_heroes) >= 2:
            pots = [h['potion_count'] for h in final_heroes]
            diff = max(pots) - min(pots)
            if diff > 2:
                score -= 5
                deductions.append(f"-5 team {team_key.upper()} potion imbalance (diff={diff})")
    # Stranded upgrades = items that should have been equipped/traded
    if stranded_count:
        strand_penalty = min(25, stranded_count * 3)
        score -= strand_penalty
        deductions.append(f"-{strand_penalty} stranded upgrades ({stranded_count} items sitting in inventory that could upgrade someone)")
    # Distribution activity bonus
    if tracker.items_traded:
        score = min(100, score + 2)
    # Purge activity (good sign)
    if tracker.items_purged:
        score = min(100, score + 1)

    score = max(0, min(100, score))
    if score >= 90:
        grade = f"\033[32m{score}/100 -- EXCELLENT\033[0m"
    elif score >= 70:
        grade = f"\033[33m{score}/100 -- GOOD\033[0m"
    elif score >= 50:
        grade = f"\033[33m{score}/100 -- FAIR\033[0m"
    else:
        grade = f"\033[31m{score}/100 -- POOR\033[0m"
    lines.append(f"  |  Score: {grade}")
    for d in deductions:
        lines.append(f"  |    {d}")
    if not deductions:
        lines.append(f"  |    No deductions -- all systems working correctly")
    lines.append(f"  +------------------------------------------------------------+")

    return '\n'.join(lines)


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
    equipment_report: bool = False,
    exploration_report: bool = False,
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

    # Equipment tracking
    eq_tracker = EquipmentTracker() if equipment_report else None
    if eq_tracker:
        eq_tracker.snapshot_spawn_gear(all_units)

    # Exploration tracking
    exp_tracker = ExplorationTracker(match_id, grid_width, grid_height) if exploration_report else None
    if exp_tracker:
        obstacles_snapshot = get_obstacles_with_door_states(map_id, None)  # All doors closed = max obstacles
        exp_tracker.set_walkable_count(obstacles_snapshot)
        exp_tracker.register_leaders(all_units)

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

        # Step 1.5: Update room discovery & clearance (same as tick_loop.py)
        for team_letter, team_fov_set in ai_team_fov_map.items():
            if team_fov_set:
                update_room_discovery(match_id, team_letter, team_fov_set)
                update_room_clearance(match_id, team_letter, all_units, chest_states)

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

        # Collect equipment events for diagnostics
        if eq_tracker:
            eq_tracker.collect_turn_events(turn_result, all_units, action_list)

        # Collect exploration diagnostics
        if exp_tracker:
            exp_tracker.collect_turn(turn_number, action_list, all_units, door_tiles, match_id)

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

    # Equipment report
    if eq_tracker:
        all_units = get_match_players(match_id) or all_units
        eq_tracker.snapshot_final_gear(all_units)
        eq_tracker.run_diagnostics(all_units)
        report = render_equipment_report(eq_tracker, all_units)
        print(report)

    # Exploration report
    if exp_tracker:
        all_units = get_match_players(match_id) or all_units
        exp_report = render_exploration_report(exp_tracker, all_units, turn_number)
        print(exp_report)

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
    if exp_tracker:
        final_prog = exp_tracker.get_final_progress()
        result["exploration"] = {}
        for tk in ("a", "b", "c", "d"):
            result["exploration"][tk] = {
                "tiles_visited": len(exp_tracker.tiles_visited.get(tk, set())),
                "tile_coverage_pct": round(len(exp_tracker.tiles_visited.get(tk, set())) / max(1, exp_tracker.total_walkable) * 100, 1),
                "rooms_discovered": final_prog.get(tk, {}).get("discovered_rooms", 0),
                "rooms_total": final_prog.get(tk, {}).get("total_rooms", 0),
                "exploration_pct": final_prog.get(tk, {}).get("exploration_pct", 0),
                "doors_opened": exp_tracker.door_opens.get(tk, 0),
                "oscillation_turns": exp_tracker.oscillation_turns.get(tk, 0),
                "leader_osc_turns": exp_tracker.leader_oscillation_turns.get(tk, 0),
                "follower_osc_turns": exp_tracker.follower_oscillation_turns.get(tk, 0),
                "suppression_turns": exp_tracker.suppression_turns.get(tk, 0),
                "unique_targets": len(exp_tracker.unique_targets.get(tk, set())),
                "target_switches": exp_tracker.target_switches.get(tk, 0),
                "door_approach_failures": exp_tracker.door_approach_failures.get(tk, 0),
            }
        # Compute overall health score
        result["exploration_health_score"] = _calc_exploration_health_score(exp_tracker, final_prog, turn_number)
        # Per-class oscillation data for batch aggregation
        result["class_oscillation"] = dict(exp_tracker.class_oscillation_turns)
        result["class_unit_count"] = dict(exp_tracker.class_unit_count)
        # Phase 32D/E: All-hero reason counts for batch aggregation
        result["reason_counts"] = dict(exp_tracker.all_reason_counts)
    if eq_tracker:
        result["equipment_health_score"] = _calc_health_score(eq_tracker)
        result["weapon_violations"] = len(eq_tracker.weapon_class_violations)
        result["armor_mismatches"] = len(eq_tracker.armor_mismatch)
        result["inventory_overflows"] = len(eq_tracker.inventory_overflow)
        result["items_picked_up"] = sum(len(e['items']) for e in eq_tracker.items_picked_up)
        result["items_traded"] = len(eq_tracker.items_traded)
        result["items_purged"] = len(eq_tracker.items_purged)
        result["potions_used"] = len(eq_tracker.potions_used)
        result["stranded_upgrades"] = eq_tracker.stranded_upgrades

    if log_fh:
        log_fh.write(f"\n{'='*60}\n")
        log_fh.write(f"RESULT: {winner} wins in {result['turns']} turns\n")
        log_fh.close()
        print(f"\n  Movement log saved to: {log_file}")

    # Clean up
    remove_match(match_id)

    return result


# ─── Batch Results ───────────────────────────────────────────────────────────

def _calc_health_score(tracker: EquipmentTracker) -> int:
    """Calculate equipment health score (0-100)."""
    score = 100
    wv = len(tracker.weapon_class_violations)
    if wv:
        score -= wv * 20
    am = len(tracker.armor_mismatch)
    alive_heroes = sum(1 for h in tracker.hero_final_gear.values() if h['is_alive'])
    if am and alive_heroes:
        pct = am / alive_heroes * 100
        score -= 15 if pct > 50 else 8 if pct > 25 else 3
    iof = len(tracker.inventory_overflow)
    if iof:
        score -= iof * 15
    for team_key in ('a', 'b', 'c', 'd'):
        final_heroes = [h for h in tracker.hero_final_gear.values() if h['team'] == team_key and h['is_alive']]
        if len(final_heroes) >= 2:
            pots = [h['potion_count'] for h in final_heroes]
            if max(pots) - min(pots) > 2:
                score -= 5
    if tracker.items_traded:
        score = min(100, score + 2)
    if tracker.items_purged:
        score = min(100, score + 1)
    return max(0, min(100, score))


def _calc_exploration_health_score(tracker: ExplorationTracker, final_prog: dict, max_turns: int) -> int:
    """Calculate exploration health score (0-100) for batch summary."""
    score = 100
    for team_key in ("a", "b", "c", "d"):
        visited = len(tracker.tiles_visited.get(team_key, set()))
        if tracker.total_walkable > 0:
            pct = visited / tracker.total_walkable * 100
            if pct < 5:
                score -= 15
            elif pct < 15:
                score -= 8
        prog = final_prog.get(team_key, {})
        total_rooms = prog.get("total_rooms", 1)
        discovered = prog.get("discovered_rooms", 0)
        if total_rooms > 0 and discovered / total_rooms < 0.2:
            score -= 10
        if tracker.door_opens.get(team_key, 0) == 0:
            score -= 8
        osc_turns = tracker.oscillation_turns.get(team_key, 0)
        if osc_turns > max_turns * 0.3:
            score -= 10
        elif osc_turns > max_turns * 0.1:
            score -= 5
    return max(0, min(100, score))


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

    print(f"\n{'=' * 70}")
    print(f"  PVPVE BATCH RESULTS -- {total} matches")
    print(f"{'=' * 70}")
    for team_key in ["team_a", "team_b", "team_c", "team_d"]:
        wins = team_wins.get(team_key, 0)
        pct = wins / total * 100
        label = _team_label(team_key.replace("team_", ""))
        print(f"  {label} wins: {wins:>4}  ({pct:.1f}%)")
    draws = team_wins.get("draw", 0)
    print(f"  Draws:         {draws:>4}  ({draws / total * 100:.1f}%)")
    # Show any unexpected winner values
    known_keys = {"team_a", "team_b", "team_c", "team_d", "draw"}
    other = {k: v for k, v in team_wins.items() if k not in known_keys and v > 0}
    if other:
        for k, v in other.items():
            print(f"  Other ({k}): {v:>4}  ({v / total * 100:.1f}%)")
    print(f"  Avg turns:     {avg_turns:.1f}")

    # Equipment batch summary if available
    eq_results = [r for r in results if 'equipment_health_score' in r]
    if eq_results:
        avg_score = sum(r['equipment_health_score'] for r in eq_results) / len(eq_results)
        total_violations = sum(r.get('weapon_violations', 0) for r in eq_results)
        total_mismatches = sum(r.get('armor_mismatches', 0) for r in eq_results)
        total_overflows = sum(r.get('inventory_overflows', 0) for r in eq_results)
        total_picked = sum(r.get('items_picked_up', 0) for r in eq_results)
        total_traded = sum(r.get('items_traded', 0) for r in eq_results)
        total_purged = sum(r.get('items_purged', 0) for r in eq_results)
        total_pots = sum(r.get('potions_used', 0) for r in eq_results)
        total_stranded = sum(r.get('stranded_upgrades', 0) for r in eq_results)
        print(f"\n  +- EQUIPMENT BATCH SUMMARY ----------------------------------+")
        print(f"  |  Avg health score:      {avg_score:>5.1f}/100")
        print(f"  |  Weapon violations:     {total_violations:>5} across {len(eq_results)} matches")
        print(f"  |  Armor mismatches:      {total_mismatches:>5}")
        print(f"  |  Inventory overflows:   {total_overflows:>5}")
        print(f"  |  Stranded upgrades:     {total_stranded:>5}  \033[33m<-- items in bag that could upgrade someone\033[0m")
        print(f"  |  Total items picked up: {total_picked:>5}")
        print(f"  |  Total items traded:    {total_traded:>5}")
        print(f"  |  Total items purged:    {total_purged:>5}")
        print(f"  |  Total potions used:    {total_pots:>5}")
        print(f"  +------------------------------------------------------------+")

    # Exploration batch summary if available
    exp_results = [r for r in results if 'exploration_health_score' in r]
    if exp_results:
        avg_exp_score = sum(r['exploration_health_score'] for r in exp_results) / len(exp_results)
        print(f"\n  +- EXPLORATION BATCH SUMMARY --------------------------------+")
        print(f"  |  Avg exploration health: {avg_exp_score:>5.1f}/100")
        for tk in ("a", "b", "c", "d"):
            team_data = [r['exploration'].get(tk, {}) for r in exp_results if 'exploration' in r]
            if not team_data:
                continue
            avg_tiles = sum(d.get('tiles_visited', 0) for d in team_data) / len(team_data)
            avg_tile_pct = sum(d.get('tile_coverage_pct', 0) for d in team_data) / len(team_data)
            avg_rooms_pct = sum(d.get('exploration_pct', 0) for d in team_data) / len(team_data)
            avg_doors = sum(d.get('doors_opened', 0) for d in team_data) / len(team_data)
            avg_osc = sum(d.get('oscillation_turns', 0) for d in team_data) / len(team_data)
            avg_leader_osc = sum(d.get('leader_osc_turns', 0) for d in team_data) / len(team_data)
            avg_follower_osc = sum(d.get('follower_osc_turns', 0) for d in team_data) / len(team_data)
            avg_supp = sum(d.get('suppression_turns', 0) for d in team_data) / len(team_data)
            avg_targets = sum(d.get('unique_targets', 0) for d in team_data) / len(team_data)
            label = _team_label(tk)
            print(f"  |  {label:35s}  tiles:{avg_tiles:>5.0f} ({avg_tile_pct:>4.1f}%)  rooms:{avg_rooms_pct:>4.0f}%  doors:{avg_doors:>4.1f}  osc:{avg_osc:>5.1f}")
            print(f"  |  {'':35s}  ldr-osc:{avg_leader_osc:>4.1f}  fol-osc:{avg_follower_osc:>4.1f}  supp:{avg_supp:>4.1f}  targets:{avg_targets:>3.1f}")
        print(f"  +------------------------------------------------------------+")

        # Per-class oscillation aggregation across all matches
        agg_class_osc: dict[str, int] = {}
        agg_class_count: dict[str, int] = {}
        for r in exp_results:
            co = r.get("class_oscillation", {})
            cc = r.get("class_unit_count", {})
            for cls, osc in co.items():
                agg_class_osc[cls] = agg_class_osc.get(cls, 0) + osc
            for cls, cnt in cc.items():
                agg_class_count[cls] = agg_class_count.get(cls, 0) + cnt
        if agg_class_osc:
            print(f"\n  +- PER-CLASS OSCILLATION (aggregate across {len(exp_results)} matches) ----+")
            sorted_cls = sorted(agg_class_osc.items(), key=lambda kv: kv[1], reverse=True)
            for cls, total_osc in sorted_cls:
                n = agg_class_count.get(cls, 1)
                avg = total_osc / n
                print(f"  |  {cls:20s}  total:{total_osc:>5}  units:{n:>3}  avg:{avg:>6.1f}/unit")
            print(f"  +------------------------------------------------------------+")

        # Phase 32D/E: Aggregate reason counts across all matches
        agg_reasons: dict[str, int] = {}
        for r in exp_results:
            for reason, count in r.get("reason_counts", {}).items():
                agg_reasons[reason] = agg_reasons.get(reason, 0) + count
        if agg_reasons:
            total_reasons = sum(agg_reasons.values())
            print(f"\n  +- AI REASON SUMMARY (aggregate across {len(exp_results)} matches, {total_reasons} total) -+")
            sorted_reasons = sorted(agg_reasons.items(), key=lambda kv: kv[1], reverse=True)
            for reason, count in sorted_reasons[:25]:
                pct = count / total_reasons * 100 if total_reasons else 0
                bar_len = int(pct / 2)
                bar = "█" * bar_len
                print(f"  |  {reason:35s} {count:>6} ({pct:>5.1f}%)  {bar}")
            if len(sorted_reasons) > 25:
                remaining = sum(c for _, c in sorted_reasons[25:])
                print(f"  |  {'... +' + str(len(sorted_reasons) - 25) + ' more reasons':35s} {remaining:>6}")
            # Dynamic stance breakdowns — auto-discovers all reasons by prefix
            _stance_sections = [
                ("FOLLOW STANCE", "follow_"),
                ("AGGRESSIVE STANCE", "agg_"),
                ("DEFENSIVE STANCE", "def_"),
                ("HOLD STANCE", "hold_"),
            ]
            _follow_extras = ("oscillation_suppressed", "stall_breaker_yield")
            n_matches = len(exp_results)
            for section_label, prefix in _stance_sections:
                hits = {k: v for k, v in agg_reasons.items()
                        if k.startswith(prefix) and v > 0}
                if prefix == "follow_":
                    for extra in _follow_extras:
                        val = agg_reasons.get(extra, 0)
                        if val > 0:
                            hits[extra] = val
                if hits:
                    print(f"  |  {'─' * 55}")
                    print(f"  |  {section_label} METRICS (avg per match):")
                    for k, v in sorted(hits.items(), key=lambda kv: kv[1], reverse=True):
                        avg = v / n_matches
                        print(f"  |    {k:33s} {v:>6} total  ({avg:>6.1f}/match)")
            print(f"  +------------------------------------------------------------+")

    print(f"{'=' * 70}")
    print(f"  Reports saved to server/data/match_history/")
    print(f"  View detailed stats in Arena Analyst (start-arena-analyst.bat)")
    print(f"{'=' * 70}")


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
    parser.add_argument("--equipment-report", action="store_true",
                        help="Print detailed AI equipment management diagnostics per match")
    parser.add_argument("--exploration-report", action="store_true",
                        help="Print exploration coverage, door interaction, and oscillation diagnostics per match")

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
            equipment_report=args.equipment_report,
            exploration_report=args.exploration_report,
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
