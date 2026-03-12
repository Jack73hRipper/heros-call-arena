"""Deep-dive timeline analysis for a specific class (Inquisitor)."""
import json, os, glob
from collections import defaultdict

TARGET_CLASS = "inquisitor"

history_dir = os.path.join(os.path.dirname(__file__), "data", "match_history")
files = sorted(glob.glob(os.path.join(history_dir, "*.json")))

# Track per-match: when inquisitor dies, what actions it takes, etc.
death_turns = []          # Turn number when inquisitor dies
match_durations = []      # Total turns of matches with inquisitor
actions_per_turn = []     # (turn, action_type) for all inquisitor actions
skill_usage_counts = defaultdict(int)
empty_turns = 0           # turns where inquisitor had 0 events
total_inq_turns = 0
total_inq_damage_turns = 0
total_inq_appearances = 0
first_action_turn = []    # turn of first damage/heal action per match

# Track: how many turns before first damage dealt
turns_before_first_damage = []

# Track what kills inquisitors
killed_by_class = defaultdict(int)
killed_by_skill = defaultdict(int)

# Track ranged vs melee attack usage
ranged_attacks = 0
melee_attacks = 0

for fp in files:
    try:
        with open(fp, "r", encoding="utf-8") as f:
            report = json.load(f)
    except:
        continue

    unit_stats = report.get("unit_stats", {})
    timeline = report.get("timeline", [])
    duration = report.get("duration_turns", 0)

    # Find inquisitor unit IDs in this match
    inq_ids = set()
    for uid, stats in unit_stats.items():
        if stats.get("class_id") == TARGET_CLASS:
            inq_ids.add(uid)

    if not inq_ids:
        continue

    total_inq_appearances += len(inq_ids)

    # Build uid -> class_id map
    uid_to_class = {}
    for uid, stats in unit_stats.items():
        uid_to_class[uid] = stats.get("class_id", "unknown")

    for inq_id in inq_ids:
        match_durations.append(duration)
        first_dmg_turn = None
        inq_died_turn = None

        for turn_entry in timeline:
            turn_num = turn_entry.get("turn", 0)
            events = turn_entry.get("events", [])

            inq_did_something = False

            for evt in events:
                # Damage dealt BY inquisitor
                if evt.get("type") == "damage" and evt.get("src") == inq_id:
                    inq_did_something = True
                    total_inq_damage_turns += 1
                    skill = evt.get("skill", "unknown")
                    skill_usage_counts[skill] += 1
                    if skill in ("attack", "auto_attack_melee"):
                        melee_attacks += 1
                    elif skill in ("ranged_attack",):
                        ranged_attacks += 1
                    if first_dmg_turn is None:
                        first_dmg_turn = turn_num

                # Heal BY inquisitor
                if evt.get("type") == "heal" and evt.get("src") == inq_id:
                    inq_did_something = True

                # Buff BY inquisitor
                if evt.get("type") == "buff" and evt.get("src") == inq_id:
                    inq_did_something = True

                # Inquisitor death
                if evt.get("type") == "death" and evt.get("unit") == inq_id:
                    inq_died_turn = turn_num
                    killer_id = evt.get("killer", "")
                    if killer_id:
                        killer_class = uid_to_class.get(killer_id, "unknown")
                        killed_by_class[killer_class] += 1

            # Check if inquisitor was alive this turn but did nothing visible
            if inq_died_turn is None or turn_num < inq_died_turn:
                total_inq_turns += 1
                if not inq_did_something:
                    empty_turns += 1

        if inq_died_turn is not None:
            death_turns.append(inq_died_turn)

        if first_dmg_turn is not None:
            turns_before_first_damage.append(first_dmg_turn)

# Also check what skills killed the inquisitor from damage events preceding death
for fp in files:
    try:
        with open(fp, "r", encoding="utf-8") as f:
            report = json.load(f)
    except:
        continue

    unit_stats = report.get("unit_stats", {})
    timeline = report.get("timeline", [])

    inq_ids = set()
    for uid, stats in unit_stats.items():
        if stats.get("class_id") == TARGET_CLASS:
            inq_ids.add(uid)

    if not inq_ids:
        continue

    for turn_entry in timeline:
        events = turn_entry.get("events", [])
        # Find damage dealt TO inquisitor
        for evt in events:
            if evt.get("type") == "damage" and evt.get("tgt") in inq_ids:
                # Check if this was a killing blow (death event same turn, same target)
                tgt = evt.get("tgt")
                is_kill = any(
                    e.get("type") == "death" and e.get("unit") == tgt
                    for e in events
                )
                if is_kill:
                    killed_by_skill[evt.get("skill", "unknown")] += 1


print(f"=== INQUISITOR DEEP DIVE ({total_inq_appearances} appearances) ===\n")

print(f"--- SURVIVABILITY ---")
if death_turns:
    avg_death = sum(death_turns) / len(death_turns)
    deaths_before_10 = sum(1 for t in death_turns if t <= 10)
    deaths_before_20 = sum(1 for t in death_turns if t <= 20)
    print(f"  Total deaths recorded: {len(death_turns)}")
    print(f"  Avg death turn: {avg_death:.1f}")
    print(f"  Median death turn: {sorted(death_turns)[len(death_turns)//2]}")
    print(f"  Deaths before turn 10: {deaths_before_10} ({deaths_before_10/len(death_turns)*100:.0f}%)")
    print(f"  Deaths before turn 20: {deaths_before_20} ({deaths_before_20/len(death_turns)*100:.0f}%)")
    print(f"  Earliest death: turn {min(death_turns)}")
    print(f"  Latest death: turn {max(death_turns)}")
else:
    print(f"  No deaths recorded")

print(f"\n--- WASTED TURNS ---")
print(f"  Total turns alive: {total_inq_turns}")
print(f"  Turns with NO visible action: {empty_turns} ({empty_turns/max(total_inq_turns,1)*100:.1f}%)")
print(f"  Turns with damage dealt: {total_inq_damage_turns}")

print(f"\n--- TIME TO FIRST DAMAGE ---")
if turns_before_first_damage:
    avg_first = sum(turns_before_first_damage) / len(turns_before_first_damage)
    print(f"  Avg turns before first damage: {avg_first:.1f}")
    print(f"  Median: {sorted(turns_before_first_damage)[len(turns_before_first_damage)//2]}")
else:
    print(f"  No data")

print(f"\n--- MELEE vs RANGED ---")
print(f"  Melee attacks: {melee_attacks}")
print(f"  Ranged attacks: {ranged_attacks}")
print(f"  Skill damage actions breakdown:")
for skill, count in sorted(skill_usage_counts.items(), key=lambda x: x[1], reverse=True):
    print(f"    {skill:<28} {count:>5}")

print(f"\n--- KILLED BY (class) ---")
for cls, count in sorted(killed_by_class.items(), key=lambda x: x[1], reverse=True):
    print(f"  {cls:<20} {count:>4}")

print(f"\n--- KILLING BLOW (skill) ---")
for skill, count in sorted(killed_by_skill.items(), key=lambda x: x[1], reverse=True):
    print(f"  {skill:<28} {count:>4}")

# Distribution of death turns
print(f"\n--- DEATH TURN DISTRIBUTION ---")
if death_turns:
    buckets = defaultdict(int)
    for t in death_turns:
        bucket = (t // 10) * 10
        buckets[bucket] += 1
    for b in sorted(buckets.keys()):
        bar = "#" * buckets[b]
        print(f"  Turn {b:>3}-{b+9:<3}: {buckets[b]:>3} {bar}")
