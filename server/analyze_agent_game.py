"""Quick analysis of the agent game log."""
import json, sys

with open("agent_turn/game_log.json", "r", encoding="utf-8") as f:
    log = json.load(f)

print("=== MATCH INFO ===")
for k, v in log["match_info"].items():
    print(f"  {k}: {v}")

print(f"\nTotal turns logged: {log['total_turns']}")

print("\n=== AGENT DECISIONS (first 30 turns) ===")
for t in log["turns"][:30]:
    act = t["action"]
    action = act.get("action", "?")
    reason = act.get("reasoning", "")[:70]
    outcomes = t.get("outcome", [])
    out_str = " | ".join(outcomes[:2]) if outcomes else ""
    print(f"  T{t['turn']:>3}: {action:>15} - {reason}")
    if out_str:
        print(f"       -> {out_str}")

print("\n=== TEAM A DEATHS ===")
for t in log["turns"]:
    for o in t.get("outcome", []):
        if "Team A" in o and "DIED" in o:
            print(f"  {o}")

print("\n=== ACTION DISTRIBUTION ===")
counts = {}
for t in log["turns"]:
    a = t["action"].get("action", "WAIT")
    counts[a] = counts.get(a, 0) + 1
for action, count in sorted(counts.items(), key=lambda x: -x[1]):
    print(f"  {action}: {count}")
