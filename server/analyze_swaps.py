"""Analyze PVPVE swap/oscillation patterns from the log file."""
import re
from collections import defaultdict, Counter

import sys
log_file = sys.argv[1] if len(sys.argv) > 1 else 'swap_diagnosis.log'
with open(log_file, 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Parse ALL actions (MOVE, WAIT, ATTACK, etc.)
actions = []
for line in lines:
    # MOVE
    m = re.match(r'\s*\[T(\d+)\]\s+(Team \w+)\s+(.+?):\s+MOVE\s+\((\d+),(\d+)\)\s+.*?\s+\((\d+),(\d+)\)\s+\[(.+?)\]', line)
    if m:
        actions.append({
            'turn': int(m.group(1)), 'team': m.group(2), 'name': m.group(3),
            'action': 'MOVE', 'from': (int(m.group(4)), int(m.group(5))),
            'to': (int(m.group(6)), int(m.group(7))), 'reason': m.group(8),
        })
        continue
    # WAIT
    m = re.match(r'\s*\[T(\d+)\]\s+(Team \w+)\s+(.+?):\s+WAIT\s+\[(.+?)\]', line)
    if m:
        actions.append({
            'turn': int(m.group(1)), 'team': m.group(2), 'name': m.group(3),
            'action': 'WAIT', 'reason': m.group(4),
        })
        continue
    # INTERACT
    m = re.match(r'\s*\[T(\d+)\]\s+(Team \w+)\s+(.+?):\s+INTERACT', line)
    if m:
        actions.append({
            'turn': int(m.group(1)), 'team': m.group(2), 'name': m.group(3),
            'action': 'INTERACT', 'reason': 'door/chest',
        })

# 1. Count reason categories for hero teams only
hero_reasons = Counter()
hero_team_reasons = defaultdict(Counter)
for a in actions:
    if a['team'] in ('Team A', 'Team B', 'Team C', 'Team D'):
        hero_reasons[a['reason']] += 1
        hero_team_reasons[a['team']][a['reason']] += 1

print('=== HERO ACTION REASON BREAKDOWN (All Teams) ===')
for reason, count in hero_reasons.most_common(30):
    print(f'  {count:4d}x {reason}')

stall_yield = hero_reasons.get('stall_breaker_yield', 0)
osc_suppress = hero_reasons.get('oscillation_suppressed', 0)
total_hero = sum(hero_reasons.values())
print()
print('=== STALL/OSCILLATION EVENTS ===')
print(f'  Stall breaker yields:    {stall_yield}')
print(f'  Oscillation suppressed:  {osc_suppress}')
print(f'  Total hero actions:      {total_hero}')
if total_hero > 0:
    print(f'  Stall/oscillation %:     {(stall_yield + osc_suppress)/total_hero*100:.1f}%')

print()
print('=== FOLLOW ACTION TYPES ===')
for key in ['follow_trail_moving', 'follow_trail_owner', 'follow_move_to_target', 'follow_idle', 'follow_no_owner']:
    print(f'  {key:30s}: {hero_reasons.get(key, 0)}')

print()
print('=== LEADER DECISION TYPES ===')
for key in ['explore_room', 'patrol_move', 'directed_adjacent_move', 'aggro_chest_seek', 'aggro_rush_melee']:
    print(f'  {key:30s}: {hero_reasons.get(key, 0)}')

# 2. Detect tile-swapping oscillation per unit
print()
print('=== TILE OSCILLATION DETECTION (A->B->A within 3 turns) ===')
unit_moves = defaultdict(list)
for a in actions:
    if a['action'] == 'MOVE' and a['team'] in ('Team A', 'Team B', 'Team C', 'Team D'):
        unit_moves[a['name']].append((a['turn'], a['from'], a['to'], a['reason']))

total_oscillations = 0
for name, history in sorted(unit_moves.items()):
    oscillations = []
    for i in range(1, len(history)):
        turn_i, from_i, to_i, reason_i = history[i]
        for j in range(max(0, i-3), i):
            turn_j, from_j, to_j, reason_j = history[j]
            if to_i == from_j and from_i == to_j:
                oscillations.append((turn_j, turn_i, from_j, to_j, reason_j, reason_i))
                break
    if oscillations:
        total_oscillations += len(oscillations)
        print(f'\n  {name}: {len(oscillations)} oscillation(s) in {len(history)} total moves')
        for t1, t2, pos_a, pos_b, r1, r2 in oscillations[:15]:
            print(f'    T{t1:3d}: {pos_a}->{pos_b} [{r1}]  <->  T{t2:3d}: {pos_b}->{pos_a} [{r2}]')

print(f'\n  TOTAL oscillation events: {total_oscillations}')
total_hero_moves = sum(len(v) for v in unit_moves.values())
print(f'  Total hero MOVE actions:  {total_hero_moves}')
if total_hero_moves > 0:
    print(f'  Oscillation rate:         {total_oscillations/total_hero_moves*100:.1f}%')

# 3. Check which reason pairs trigger oscillation
print()
print('=== OSCILLATION REASON PAIRS ===')
reason_pairs = Counter()
for name, history in unit_moves.items():
    for i in range(1, len(history)):
        turn_i, from_i, to_i, reason_i = history[i]
        for j in range(max(0, i-3), i):
            turn_j, from_j, to_j, reason_j = history[j]
            if to_i == from_j and from_i == to_j:
                pair = f'{reason_j} <-> {reason_i}'
                reason_pairs[pair] += 1
                break

for pair, count in reason_pairs.most_common(20):
    print(f'  {count:3d}x  {pair}')

# 4. Check for door proximity during oscillation
print()
print('=== DOOR-RELATED ACTIONS ===')
door_actions = [a for a in actions if a['action'] == 'INTERACT']
for da in door_actions:
    print(f'  T{da["turn"]:3d} {da["team"]} {da["name"]}: INTERACT [{da["reason"]}]')

# Look at what happened around door interactions (3 turns before/after)
if door_actions:
    print()
    print('=== MOVEMENT AROUND DOOR INTERACTIONS ===')
    for da in door_actions[:5]:
        door_turn = da['turn']
        door_team = da['team']
        print(f'\n  Door: T{door_turn} {door_team} {da["name"]}')
        for a in actions:
            if a['team'] == door_team and abs(a['turn'] - door_turn) <= 3:
                if a['action'] == 'MOVE':
                    print(f'    T{a["turn"]:3d} {a["name"]:20s}: MOVE {a["from"]}->{a["to"]} [{a["reason"]}]')
                elif a['action'] == 'WAIT':
                    print(f'    T{a["turn"]:3d} {a["name"]:20s}: WAIT [{a["reason"]}]')
                elif a['action'] == 'INTERACT':
                    print(f'    T{a["turn"]:3d} {a["name"]:20s}: INTERACT [{a["reason"]}]')
