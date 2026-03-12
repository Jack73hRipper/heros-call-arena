# Combat Meter System

Live, real-time combat statistics panel — tracks damage, healing, kills, and more during a match.

## Overview

The Combat Meter aggregates structured combat data from every `turn_result` tick to provide live per-unit statistics. It's a client-side feature that requires zero server changes — all data is already present in the existing `ActionResult` payloads.

Click any player row to drill into their **per-skill breakdown** — see which abilities dealt the most damage or healing, average per cast, best single hit, and damage/healing source type distribution.

**Toggle:** Click the ⚔ button on the action bar, or press Tab / M.

## UI Layout

The meter is a **drop-down panel** that slides below the action bar (BottomBar), floating above the main game canvas. It contains:

1. **Header row** — view selector dropdown, turn counter, close button
2. **Body** — the active stats view (scrollable)

The panel is 600px wide (or 90vw on small screens), max 340px tall, centered horizontally.

## Views

| View | Description | Sort |
|------|-------------|------|
| **Damage Done** | Horizontal bars per unit, colored by class | Descending by total damage |
| **Damage Taken** | Who absorbs the most hits (tank metric) | Descending by damage taken |
| **Healing Done** | Healer contribution (skills + potions + HoTs) | Descending by total healing |
| **Kills** | Table with kill count, boss kills, highest hit | Descending by kills |
| **Overview** | Compact table with all stats in columns | Descending by damage dealt |

All bar views show **per-turn rate** (DPT/HPT) alongside the total. The player's own row is highlighted with an ember accent.

## Architecture

### Data Flow

```
Server tick_loop → turn_result WS message → App.jsx handleMessage
  ↓
  dispatch(TURN_RESULT)      → combatReducer (existing: log, floaters, players)
  dispatch(COMBAT_STATS_UPDATE) → combatStatsReducer (new: per-unit stat accumulation)
```

### Files

| File | Purpose |
|------|---------|
| `client/src/context/reducers/combatStatsReducer.js` | Reducer that accumulates per-unit stats from ActionResult arrays |
| `client/src/context/GameStateContext.jsx` | Added `CombatStatsContext` + `CombatStatsDispatchContext`, `useCombatStats()`, `useCombatStatsDispatch()` hooks |
| `client/src/components/CombatMeter/CombatMeter.jsx` | Main panel container with dropdown selector + drill-in state management |
| `client/src/components/CombatMeter/MeterBar.jsx` | Reusable horizontal bar component (clickable) |
| `client/src/components/CombatMeter/SkillBreakdownView.jsx` | Per-skill detail panel — shown when clicking a player row; includes hover tooltips |
| `client/src/components/CombatMeter/skillInfo.js` | Skill name/icon/type/description/cooldown/range/targeting resolver — maps skill_id → display info |
| `client/src/components/CombatMeter/DamageDoneView.jsx` | Damage dealt view |
| `client/src/components/CombatMeter/DamageTakenView.jsx` | Damage taken view |
| `client/src/components/CombatMeter/HealingDoneView.jsx` | Healing done view |
| `client/src/components/CombatMeter/KillsView.jsx` | Kill leaderboard table |
| `client/src/components/CombatMeter/OverviewView.jsx` | Full stats table |
| `client/src/components/BottomBar/BottomBar.jsx` | Toggle button added (⚔ icon + Tab hotkey) |
| `client/src/components/Arena/Arena.jsx` | CombatMeter rendered inside arena-bottom-bar |
| `client/src/styles/main.css` | All combat meter CSS (end of file) |
| `client/src/App.jsx` | Added `COMBAT_STATS_UPDATE` dispatch on each `turn_result` |

### Per-Unit Stats Tracked

| Stat | Source |
|------|--------|
| `damage_dealt` | `ActionResult.damage_dealt` from attacks/skills |
| `damage_taken` | Inverse — tracked on the target |
| `healing_done` | `ActionResult.heal_amount` + `items_used.effect.actual_healed` |
| `kills` / `boss_kills` | `ActionResult.killed` flag |
| `highest_hit` | Max single `damage_dealt` value ever seen |
| `deaths` | From `turn_result.deaths` array |
| `turns_alive` | Updated each tick for living units |
| `potions_used` | Counted from `use_item` actions and `items_used` |
| `items_looted` | From `items_picked_up` in turn_result |
| `damage_by_type` | Breakdown: `melee`, `ranged`, `skill`, `dot`, `reflect` |
| `healing_by_type` | Breakdown: `skill`, `potion`, `hot` |
| `skill_breakdown` | Per-skill: `{ damage, heals, casts, highest_hit }` |

### Hotkey

- **Tab / M** — Toggle combat meter panel
- **Escape** — Back from skill breakdown (or close panel if already at top level)
- **Backspace** — Back from skill breakdown
- **Enter** — Drill into focused row (keyboard nav on MeterBar rows)

## Per-Skill Breakdown View (Implemented)

Click any player row in **any** meter view to drill into their per-skill breakdown. The breakdown replaces the list view with:

### Layout

1. **Back button** (← Back) — returns to the parent view. Also Escape/Backspace.
2. **Sticky unit summary header** — player name, class badge, total damage, total healing, kills
3. **Ability Breakdown table** — sorted by total contribution (damage + healing), showing:
   - Skill icon + name with colored % bar underneath
   - Total damage, total healing, cast count
   - Average per cast, best single hit
   - % of player's total damage (and healing if applicable)
4. **Damage Sources** — horizontal bars showing melee/ranged/skill/DoT/reflect split
5. **Healing Sources** — horizontal bars showing skill/potion/HoT split

### State

| State field | Purpose |
|-------------|--------|
| `selectedUnit` | `unitId` when drilled in, `null` at top level |

Switching views via the dropdown clears `selectedUnit` and returns to list.

### Skill Info Resolver

`skillInfo.js` maps `skill_id` → `{ name, icon, type, description, cooldown, range, targeting }` with a fallback for unknown skills (snake_case → Title Case + ❓ icon). Covers all 25 skills from `skills_config.json`.

Skill types: `damage` (red), `heal` (green), `buff` (blue), `utility` (purple) — used for bar coloring.

### Auto-Attack Tracking

Auto-attacks (melee/ranged without a `skill_id`) are tracked under `auto_attack_melee` / `auto_attack_ranged` keys in `skill_breakdown`, giving visibility into ability vs auto-attack damage ratios.

### Hover Tooltip on Skill Rows (Implemented)

Hovering any row in the Ability Breakdown table shows a drop-down tooltip below the ability cell — matching the same pattern and `.skill-tooltip` styles used by the BottomBar action bar skill tooltips.

The tooltip displays:

- **Name** — skill name in heading font
- **Targeting & range** — e.g. "Enemy (Melee) · Range: 1" or "Ally or Self · Range: 3"
- **Cooldown** — turn count if the skill has a cooldown
- **Description** — full skill description in italic flavor text

Implementation uses simple `hoveredSkillId` state (no positioning math, no timeouts). Each `<tr>` row sets/clears the hovered ID on mouse enter/leave. When hovered, a `.meter-skill-tooltip-anchor` div is rendered inside the ability `<td>` with `position: absolute; top: 100%` — the standard CSS drop-down approach. The `.skill-tooltip` class is reused from the existing BottomBar tooltip styles for visual consistency.

**Files changed:**

| File | Change |
|------|--------|
| `skillInfo.js` | Added `description`, `cooldown`, `range`, `targeting` fields to all 25 skill entries + fallback |
| `SkillBreakdownView.jsx` | Added `hoveredSkillId` state, mouse handlers on `<tr>`, inline tooltip anchor per ability cell |
| `main.css` | Added `.meter-skill-tooltip-anchor` (positioning + fade-in) + `.skill-breakdown-row:hover` highlight |

## Known Limitations & Future Work

### Pending Improvements

- [ ] **Overkill damage tracking** — need pre-hit HP to compute accurately; currently the server clamps target_hp_remaining to 0
- [ ] **Damage mitigated** — would need server to broadcast pre-armor damage alongside post-armor; small server addition
- [ ] **Buff uptime tracking** — track buff_applied/expired events to compute active turns per buff
- [ ] **Kill participation / assists** — track "damaged a unit that died this turn" (cross-reference deaths with damage sources)
- [x] **Per-skill breakdown view** — click any player row to see skill-by-skill damage/heal contribution, source type bars, avg/best per skill
- [ ] **Mini-meter inline on action bar** — show your own DPT as a small number next to the toggle button without opening the panel
- [ ] **Team grouping in PvP** — separate "Your Team" vs "Enemy Team" sections in each view
- [ ] **Match-end integration** — use live meter stats to enrich the post-match summary overlay (currently uses separate heroOutcomes from server)
- [ ] **Damage timeline** — track damage per turn over time for a sparkline graph
- [ ] **Export / copy stats** — button to copy stats to clipboard for sharing
- [ ] **Customizable sort** — click column headers in Overview to sort by any stat
- [ ] **Filter by team** — dropdown to filter "All / My Team / Enemies"
- [ ] **DoT/HoT classification** — server action_type for buff ticks varies; may need refinement for accurate dot/hot categorization
- [ ] **Shield reflect attribution** — currently keyed on message text matching "reflected"; would be cleaner with a dedicated `action_type`

### Per-Skill Breakdown — Next Steps

- [x] **Hover tooltip on skill rows** — show full skill description, cooldown, range, and targeting type from skills_config when hovering an ability row
- [ ] **Per-skill casts-per-turn sparkline** — mini timeline showing when each skill was used (needs per-turn tracking in reducer)
- [ ] **Per-target breakdown** — "who did I damage most" drill-down (requires tracking `{ target_id: damage }` per attacker)
- [ ] **Healing received view** — show who healed this unit and by how much (inverse of healing_done)
- [ ] **Sort toggle on breakdown table** — click column headers to sort by damage/heals/casts/avg/best
- [ ] **Skill icon sprites** — replace emoji with sprite sheet icons when skill icon sprites are available
- [ ] **Animate drill-in transition** — slide-in animation when entering/leaving the breakdown view
- [ ] **Pin breakdown** — option to keep a unit's breakdown visible while continuing to monitor real-time updates

### QoL Features to Consider

- **Resizable panel** — drag to resize the meter height
- **Detachable/dockable** — option to dock the meter to the left or right panel instead of floating
- **Sound cue** — subtle click sound when toggling (consistent with other UI)
- **Remember state** — persist open/closed state and selected view in localStorage
- **Color-blind friendly** — alternate color schemes for the bars
