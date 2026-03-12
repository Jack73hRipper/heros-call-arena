"""Quick one-off script to aggregate match history for class balance analysis."""
import json, os, glob
from collections import defaultdict

history_dir = os.path.join(os.path.dirname(__file__), "data", "match_history")
files = sorted(glob.glob(os.path.join(history_dir, "*.json")))
print(f"Total match files: {len(files)}")

class_data = defaultdict(lambda: {
    "appearances": 0, "wins": 0, "losses": 0, "draws": 0,
    "total_damage": 0, "total_healing": 0, "total_kills": 0,
    "total_deaths": 0, "total_turns_survived": 0, "total_match_turns": 0,
    "highest_hit_ever": 0, "times_first_to_die": 0, "times_survived": 0,
    "total_damage_taken": 0,
})

total_matches = 0
draws = 0

for fp in files:
    try:
        with open(fp, "r") as f:
            report = json.load(f)
    except:
        continue

    total_matches += 1
    winner = report.get("winner", "")
    duration = report.get("duration_turns", 0)
    unit_stats = report.get("unit_stats", {})

    if winner == "draw":
        draws += 1

    for uid, stats in unit_stats.items():
        cid = stats.get("class_id")
        if not cid:
            continue
        cd = class_data[cid]
        cd["appearances"] += 1

        team = stats.get("team", "")
        team_won = (team == "a" and winner == "team_a") or (team == "b" and winner == "team_b")

        if winner == "draw":
            cd["draws"] += 1
        elif team_won:
            cd["wins"] += 1
        else:
            cd["losses"] += 1

        cd["total_damage"] += stats.get("damage_dealt", 0)
        cd["total_healing"] += stats.get("healing_done", 0)
        cd["total_kills"] += stats.get("kills", 0)
        cd["total_deaths"] += stats.get("deaths", 0)
        cd["total_damage_taken"] += stats.get("damage_taken", 0)
        cd["total_turns_survived"] += stats.get("turns_survived", 0)
        cd["total_match_turns"] += duration
        if stats.get("status") == "survived":
            cd["times_survived"] += 1
        hh = stats.get("highest_hit", 0)
        if hh > cd["highest_hit_ever"]:
            cd["highest_hit_ever"] = hh

# Find first deaths per match
for fp in files:
    try:
        with open(fp, "r") as f:
            report = json.load(f)
    except:
        continue
    unit_stats = report.get("unit_stats", {})
    timeline = report.get("timeline", [])
    for turn_entry in timeline:
        for evt in turn_entry.get("events", []):
            if evt.get("type") == "death":
                death_id = evt.get("unit", "")
                if death_id in unit_stats:
                    cid = unit_stats[death_id].get("class_id")
                    if cid:
                        class_data[cid]["times_first_to_die"] += 1
                break
        else:
            continue
        break

print(f"Total matches parsed: {total_matches} (draws: {draws})")
print()

header = (
    f"{'Class':<16} {'Apps':>5} {'Wins':>5} {'Loss':>5} {'Draw':>5} "
    f"{'Win%':>7} {'AvgDmg':>8} {'AvgHeal':>8} {'AvgKills':>8} "
    f"{'AvgDeath':>8} {'AvgDmgTkn':>9} {'Surv%':>7} {'AvgTurns':>8} "
    f"{'TopHit':>7} {'1stDie':>6}"
)
print(header)
print("-" * len(header))

sorted_classes = sorted(
    class_data.items(),
    key=lambda x: x[1]["wins"] / max(x[1]["appearances"], 1),
)

for cid, cd in sorted_classes:
    a = cd["appearances"]
    wr = (cd["wins"] / a * 100) if a > 0 else 0
    avg_dmg = cd["total_damage"] / a if a else 0
    avg_heal = cd["total_healing"] / a if a else 0
    avg_kills = cd["total_kills"] / a if a else 0
    avg_deaths = cd["total_deaths"] / a if a else 0
    avg_dmg_tkn = cd["total_damage_taken"] / a if a else 0
    surv_pct = cd["times_survived"] / a * 100 if a else 0
    avg_turns = cd["total_turns_survived"] / a if a else 0
    print(
        f"{cid:<16} {a:>5} {cd['wins']:>5} {cd['losses']:>5} {cd['draws']:>5} "
        f"{wr:>6.1f}% {avg_dmg:>8.0f} {avg_heal:>8.0f} {avg_kills:>8.2f} "
        f"{avg_deaths:>8.2f} {avg_dmg_tkn:>9.0f} {surv_pct:>6.1f}% {avg_turns:>8.1f} "
        f"{cd['highest_hit_ever']:>7} {cd['times_first_to_die']:>6}"
    )

# Skill usage breakdown from timeline
print("\n\n=== SKILL/DAMAGE SOURCE FREQUENCY (top sources per class) ===\n")

class_skill_dmg = defaultdict(lambda: defaultdict(lambda: {"count": 0, "total_dmg": 0}))
class_skill_heal = defaultdict(lambda: defaultdict(lambda: {"count": 0, "total_heal": 0}))

for fp in files:
    try:
        with open(fp, "r") as f:
            report = json.load(f)
    except:
        continue

    unit_stats = report.get("unit_stats", {})
    timeline = report.get("timeline", [])

    # Build uid -> class_id mapping
    uid_to_class = {}
    for uid, stats in unit_stats.items():
        uid_to_class[uid] = stats.get("class_id", "unknown")

    for turn_entry in timeline:
        for evt in turn_entry.get("events", []):
            src = evt.get("src", "")
            cid = uid_to_class.get(src, "")
            if not cid:
                continue

            if evt.get("type") == "damage":
                skill = evt.get("skill", "auto_attack")
                class_skill_dmg[cid][skill]["count"] += 1
                class_skill_dmg[cid][skill]["total_dmg"] += evt.get("dmg", 0)

            elif evt.get("type") == "heal":
                skill = evt.get("skill", "heal")
                class_skill_heal[cid][skill]["count"] += 1
                class_skill_heal[cid][skill]["total_heal"] += evt.get("amt", 0)

for cid in sorted(class_skill_dmg.keys()):
    skills = class_skill_dmg[cid]
    total_actions = sum(s["count"] for s in skills.values())
    print(f"  {cid}  ({total_actions} damage actions)")
    top = sorted(skills.items(), key=lambda x: x[1]["total_dmg"], reverse=True)[:8]
    for skill_name, sd in top:
        avg = sd["total_dmg"] / sd["count"] if sd["count"] else 0
        print(f"    {skill_name:<28} hits={sd['count']:>5}  totalDmg={sd['total_dmg']:>8}  avgHit={avg:>6.1f}")

    heals = class_skill_heal.get(cid, {})
    if heals:
        print(f"    -- heals --")
        for skill_name, sh in sorted(heals.items(), key=lambda x: x[1]["total_heal"], reverse=True):
            avg = sh["total_heal"] / sh["count"] if sh["count"] else 0
            print(f"    {skill_name:<28} casts={sh['count']:>5}  totalHeal={sh['total_heal']:>8}  avgHeal={avg:>6.1f}")
    print()
