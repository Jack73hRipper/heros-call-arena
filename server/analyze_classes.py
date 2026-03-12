"""Quick class comparison analysis from recent match history."""
import json, os, glob
from collections import defaultdict

history_dir = os.path.join(os.path.dirname(__file__), "data", "match_history")
files = sorted(glob.glob(os.path.join(history_dir, "*.json")))[-30:]

class_stats = defaultdict(lambda: {
    "games": 0, "total_dmg": 0, "total_taken": 0, "total_heal": 0,
    "kills": 0, "deaths": 0, "survived": 0, "turns_alive": 0,
})

for fp in files:
    try:
        with open(fp, "r", encoding="utf-8") as f:
            report = json.load(f)
    except Exception:
        continue
    unit_stats = report.get("unit_stats", {})
    for uid, stats in unit_stats.items():
        cid = stats.get("class_id", "unknown")
        cs = class_stats[cid]
        cs["games"] += 1
        cs["total_dmg"] += stats.get("damage_dealt", 0)
        cs["total_taken"] += stats.get("damage_taken", 0)
        cs["total_heal"] += stats.get("healing_done", 0)
        cs["kills"] += stats.get("kills", 0)
        cs["deaths"] += stats.get("deaths", 0)
        cs["survived"] += 1 if stats.get("status") == "survived" else 0
        cs["turns_alive"] += stats.get("turns_survived", 0)

header = f"{'Class':<16} {'Games':>5} {'AvgDmg':>8} {'AvgTkn':>8} {'AvgHeal':>8} {'Kills':>5} {'Deaths':>6} {'SurvRate':>8} {'AvgTurns':>8}"
print(header)
print("-" * len(header))
for cid in sorted(
    class_stats.keys(),
    key=lambda c: class_stats[c]["total_dmg"] / max(1, class_stats[c]["games"]),
    reverse=True,
):
    cs = class_stats[cid]
    g = max(1, cs["games"])
    surv_pct = cs["survived"] / g * 100
    print(
        f"{cid:<16} {cs['games']:>5} {cs['total_dmg']/g:>8.1f} "
        f"{cs['total_taken']/g:>8.1f} {cs['total_heal']/g:>8.1f} "
        f"{cs['kills']:>5} {cs['deaths']:>6} "
        f"{surv_pct:>7.1f}% {cs['turns_alive']/g:>8.1f}"
    )
