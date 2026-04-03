"""Quick analysis of Hexblade performance from latest batch run."""
import json, glob, os
from collections import defaultdict

reports = sorted(glob.glob(os.path.join('data', 'match_history', '2026-04-03_00*.json')))
print(f'Analyzing {len(reports)} reports...\n')

hex_totals = {'games': 0, 'wins': 0, 'kills': 0, 'deaths': 0, 'damage': 0, 'healing': 0, 'survival': 0}
hex_skills = defaultdict(lambda: {'uses': 0, 'dmg': 0, 'heal': 0})

class_stats = defaultdict(lambda: {'kills': 0, 'deaths': 0, 'damage': 0, 'healing': 0, 'survival': 0, 'games': 0, 'wins': 0})

for rpath in reports:
    with open(rpath) as f:
        data = json.load(f)

    winner = data.get('winner', '')
    unit_stats = data.get('unit_stats', {})
    timeline = data.get('timeline', [])

    # Build per-unit skill usage from timeline
    unit_skill_uses = defaultdict(lambda: defaultdict(int))
    unit_skill_dmg = defaultdict(lambda: defaultdict(int))
    unit_skill_heal = defaultdict(lambda: defaultdict(int))

    for entry in timeline:
        for ev in entry.get('events', []):
            src = ev.get('src', '')
            etype = ev.get('type', '')
            skill = ev.get('skill', '')
            if etype == 'damage' and skill:
                unit_skill_uses[src][skill] += 1
                unit_skill_dmg[src][skill] += ev.get('dmg', 0)
            elif etype == 'heal' and skill:
                unit_skill_uses[src][skill] += 1
                unit_skill_heal[src][skill] += ev.get('amt', 0)
            elif etype == 'buff' and skill:
                unit_skill_uses[src][skill] += 1

    for uid, stats in unit_stats.items():
        cls = stats.get('class_id', '')
        team = stats.get('team', '')
        won = (team == 'a' and winner == 'team_a') or (team == 'b' and winner == 'team_b')

        cs = class_stats[cls]
        cs['games'] += 1
        cs['wins'] += 1 if won else 0
        cs['kills'] += stats.get('kills', 0)
        cs['deaths'] += stats.get('deaths', 0)
        cs['damage'] += stats.get('damage_dealt', 0)
        cs['healing'] += stats.get('healing_done', 0)
        cs['survival'] += stats.get('turns_survived', 0)

        if cls == 'hexblade':
            hex_totals['games'] += 1
            hex_totals['wins'] += 1 if won else 0
            hex_totals['kills'] += stats.get('kills', 0)
            hex_totals['deaths'] += stats.get('deaths', 0)
            hex_totals['damage'] += stats.get('damage_dealt', 0)
            hex_totals['healing'] += stats.get('healing_done', 0)
            hex_totals['survival'] += stats.get('turns_survived', 0)

            # Match unit_id to timeline src
            for sk, cnt in unit_skill_uses.get(uid, {}).items():
                hex_skills[sk]['uses'] += cnt
            for sk, dmg in unit_skill_dmg.get(uid, {}).items():
                hex_skills[sk]['dmg'] += dmg
            for sk, heal in unit_skill_heal.get(uid, {}).items():
                hex_skills[sk]['heal'] += heal

g = max(hex_totals['games'], 1)
print('=== HEXBLADE DETAILED STATS ===')
print(f"Games: {hex_totals['games']}  Wins: {hex_totals['wins']}  Win%: {hex_totals['wins']/g*100:.1f}%")
print(f"Kills: {hex_totals['kills']}  Deaths: {hex_totals['deaths']}  K/D: {hex_totals['kills']/max(hex_totals['deaths'],1):.2f}")
print(f"Avg Damage: {hex_totals['damage']/g:.0f}  Avg Healing Done: {hex_totals['healing']/g:.0f}")
print(f"Avg Survival: {hex_totals['survival']/g:.1f} turns")
print()
print('--- Hexblade Skill Usage (total across all games) ---')
for sk in sorted(hex_skills, key=lambda s: hex_skills[s]['uses'], reverse=True):
    s = hex_skills[sk]
    avg_dmg = s['dmg'] / max(s['uses'], 1)
    avg_heal = s['heal'] / max(s['uses'], 1) if s['heal'] else 0
    extra = f", {s['heal']:5d} total heal ({avg_heal:.1f} avg)" if s['heal'] else ""
    print(f"  {sk:20s}: {s['uses']:4d} uses, {s['dmg']:5d} total dmg ({avg_dmg:.1f} avg){extra}")

print()
print('=== ALL CLASSES COMPARISON ===')
print(f"{'Class':16s} {'Games':>5s} {'Win%':>6s} {'AvgDmg':>7s} {'AvgHeal':>7s} {'K/D':>6s} {'AvgSurv':>8s}")
print('-' * 62)
for cls in sorted(class_stats, key=lambda c: class_stats[c]['wins']/max(class_stats[c]['games'],1), reverse=True):
    s = class_stats[cls]
    g2 = max(s['games'], 1)
    kd = s['kills'] / max(s['deaths'], 1)
    wr = s['wins'] / g2 * 100
    print(f"{cls:16s} {s['games']:5d} {wr:5.1f}% {s['damage']/g2:7.0f} {s['healing']/g2:7.0f} {kd:6.2f} {s['survival']/g2:8.1f}")
