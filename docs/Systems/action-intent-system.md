# Action Intent System

**Status:** Tier 1 implemented (v2: centered layout, sprite icons, click-to-cancel) · Tiers 2–3 planned  
**Component:** `client/src/components/BottomBar/BottomBar.jsx`  
**CSS:** `client/src/styles/main.css` (search: "Action Intent Banner")

## Problem

Players had no clear visual feedback for what action they had selected or what was about to happen next turn. After clicking a skill, queuing movement, or engaging auto-target pursuit, the only indicators were:

- A purple glow on the skill button (only while in targeting mode)
- A plain `Q: 3/10` counter that showed queue depth but not queue *content*
- An auto-target frame in the right-panel HUD (easy to miss during action selection)

The result: players felt "blind" — they couldn't tell if their spell was actually queued, what their character was about to do, or whether the right target was selected.

## Solution — Tier 1: Action Intent Banner

A color-coded status banner embedded directly in the BottomBar, **centered** between the skill/action slots (left) and the queue controls (right). It provides a **single-sentence description** of the player's current intent at all times, with **sprite icons** for actions that have them.

### Layout Position

```
[ Skill1 | Skill2 | Skill3 | Skill4 | 🧪 ]  [ ⚔(sprite) Casting: Power Shot → Goblin ]  [⚔] [Q: 1/10] [↩][✕][✖]
                                               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
                                              Centered, flex: 1, sprite icon from sheet
```

### Intent Priority (highest → lowest)

The banner displays the **most relevant** state from this priority chain:

| Priority | State | Example | Color |
|----------|-------|---------|-------|
| 1 | Dead | 💀 You have been eliminated | Red |
| 2 | Skill targeting mode | 🎯 Targeting: Power Shot — click an enemy | Purple (pulsing) |
| 3 | Auto-target w/ skill | ⚔ Casting: Power Shot → Goblin Scout | Purple (solid) |
| 3b | Auto-target pursuing | 🏃 Pursuing: Goblin Scout — Power Shot ready | Amber (pulsing) |
| 3c | Auto-target attacking | ⚔ Attacking: Skeleton Warrior | Red |
| 3d | Auto-target cooldown | ⏳ Cooldown (2) — Power Shot → Goblin | Dim orange |
| 3e | Healing target | 💚 Healing: Heal → Brother Marcus | Green |
| 4 | Queue: move+combat | ⚔ Moving to attack Goblin (3 steps) | Orange |
| 4b | Queue: pure move | 🦶 Moving to (5, 3) — 3 steps | Blue |
| 4c | Queue: skill | ✦ Queued: War Cry → target | Orange |
| 4d | Queue: potion | 🧪 Queued: Use Potion | Orange |
| 4e | Queue: interact | 🚪 Queued: Interact at (7, 2) | Orange |
| 5 | Selected target | 🎯 Selected: Goblin Scout (enemy) | Subtle red |
| 5b | Selected ally | 💚 Selected: Brother Marcus (ally) | Subtle green |
| 6 | Idle | — Awaiting orders | Dim/italic |

### Visual Design

Each intent state has a unique border color, background tint, and text color. Active states (targeting, pursuing) use a gentle CSS pulse animation for attention without being distracting.

- **Targeting mode**: Purple glow with breathing pulse — communicates "waiting for your click"
- **Pursuing**: Amber pulse — communicates "moving toward target automatically"
- **Casting/Attacking**: Solid bright glow — communicates "this is happening now"
- **Queued actions**: Orange tint — communicates "scheduled, will execute next turn(s)"
- **Idle**: Dim gray italic — communicates "nothing planned"

### Smart Queue Description

When the queue contains a mix of moves followed by combat (which is the common right-click-to-attack pattern), the banner describes the *goal* rather than the first step:

- `⚔ Moving to attack Goblin Scout (3 steps)` instead of `🦶 Moving to (5, 3)`
- `✦ Moving to cast Power Shot → Goblin (2 steps)` instead of `🦶 Moving to (6, 4)`

This gives the player the full picture of what their queued actions will accomplish.

### Implementation Details

- Uses `useMemo` for efficient recomputation only when relevant state changes
- Resolves skill definitions via a `findSkillDef` helper that searches `classSkills` and `allClassSkills`
- Reuses the existing `isInSkillRange()` function for range-aware status text
- Added `autoTargetId` and `autoSkillId` to BottomBar's state destructuring (already available in GameStateContext)
- Zero gameplay/mechanic changes — purely visual/informational

### v2 Improvements (Centered Layout, Sprite Icons, Click-to-Cancel)

#### Centered Banner

The banner was previously squeezed to the right because `.action-slots` had `flex: 1`, pushing the banner toward the queue controls. Now:

- `.action-slots` uses `flex-shrink: 0` — stays at its natural width
- `.action-intent-banner` uses `flex: 1` — fills the center gap
- Content inside the banner uses `justify-content: center`
- `min-height: 40px` and larger `padding`/`gap` give it more visual weight
- `font-size: 0.8rem` (up from 0.72rem) for better readability
- `max-width: 480px` (up from 340px) for wider screens

#### Sprite Icons in Banner

When the intent involves a skill or action that has a sprite on the `skill-icons.png` sheet, the banner renders a 24×24 `<SkillIcon>` instead of an emoji. The `hasSkillSprite()` check ensures we only replace emojis that have actual sprite replacements — skills without sprites keep their emoji fallback.

**Skills with sprite icons in the banner:**
| Skill ID | Sprite? | Used for |
|----------|---------|----------|
| `auto_attack_melee` | ✅ | Attacking, pursuing (melee), queued attack |
| `auto_attack_ranged` | ✅ | Queued ranged attack |
| `heal` | ✅ | Healing, heal-pursuing |
| `double_strike` | ✅ | Casting, pursuing with skill |
| `power_shot` | ✅ | Casting, pursuing with skill |
| `war_cry` | ✅ | Casting, pursuing with skill |
| `shadow_step` | ✅ | Casting, pursuing with skill |
| `wither` | ✅ | Casting, pursuing with skill |
| `ward` | ✅ | Casting, pursuing with skill |
| `divine_sense` | ✅ | Casting, pursuing with skill |
| `shield_of_faith` | ✅ | Casting, pursuing with skill |
| `exorcism` | ✅ | Casting, pursuing with skill |
| `prayer` | ✅ | Healing, heal-pursuing |
| `potion` | ✅ | Queued: Use Potion |

**Emojis kept (no sprite replacement available):**
- `💀` Dead, `🏃` Pursuing (label only), `🦶` Moving, `🚪` Interact, `📋` Generic queue
- `🎯` Selected enemy, `💚` Selected ally, `—` Idle, `⏳` Cooldown (label only)

#### Click-to-Cancel (QoL)

Intent states marked `cancellable: true` allow the player to click the banner to cancel:
- **Skill targeting mode** → exits targeting (dispatches `SET_ACTION_MODE: null`)
- **Auto-target pursuit** → clears auto-target (sends `set_auto_target: null`)

The banner shows a pointer cursor and brightens on hover when cancellable. A `title="Click to cancel"` tooltip confirms the action.

### CSS Classes

All styles are under the `.action-intent-banner` namespace:
- `.intent-idle`, `.intent-dead`, `.intent-targeting`, `.intent-pursuing`
- `.intent-attacking`, `.intent-casting`, `.intent-cooldown`
- `.intent-healing`, `.intent-heal-pursuing`
- `.intent-moving`, `.intent-attack-queued`, `.intent-skill-queued`
- `.intent-item-queued`, `.intent-interact-queued`, `.intent-queued`
- `.intent-target-enemy`, `.intent-target-ally`

Responsive breakpoints shrink the banner below 900px viewport width.

---

## Future QoL — Tier 2: Mini Queue Icons

**Status:** Not started

Replace the plain `Q: 3/10` text counter with a visual icon strip showing each queued action as a small icon:

```
🦶🦶🦶⚔🧪  (5/10)
```

### Design

- Each queued action maps to an icon: 🦶 (move), ⚔ (attack), 🏹 (ranged), ✦ (skill), 🧪 (potion), 🚪 (interact), ⏸ (wait)
- Icons are ~16px inline, displayed in queue order
- Hovering an icon shows a tooltip: "Move to (4, 3)" or "Attack → Goblin Scout"
- Clicking an icon could select it for removal (alternative to the current undo button which only removes the last action)
- The strip scrolls horizontally if queue is very long (unlikely with 10-cap)

### Where to build

Update the `.bar-queue-info` section in `BottomBar.jsx`. Replace or augment the `Q: {queueLength}/10` span with a mapped icon list from `currentQueue`.

---

## Future QoL — Tier 3: Active Skill Pulse

**Status:** Not started

When a skill is the one that will auto-fire next turn (via auto-target pursuit), give that skill button a **breathing pulse animation** on its border — distinct from the existing `active` class (which means "in targeting mode right now").

### Design

- New CSS class `.slot-auto-active` applied to the skill button when `autoSkillId === skill.skill_id`
- Slow breathing animation (2s cycle): border color oscillates between dim and bright
- Different color than the purple targeting glow — suggest amber/gold to match auto-target theme
- Stacks with cooldown overlay: if the skill is on cooldown, show both the cooldown number AND the pulse (dimmed) so the player knows "this skill will fire once cooldown expires"

### Where to build

In `BottomBar.jsx`, inside the skill `.map()` render, add a conditional:
```jsx
const isAutoSkill = autoSkillId === skill.skill_id;
// Add to className: `${isAutoSkill ? ' slot-auto-active' : ''}`
```

CSS animation:
```css
.action-slot.slot-auto-active {
  animation: slot-auto-pulse 2s ease-in-out infinite;
}
@keyframes slot-auto-pulse {
  0%, 100% { border-color: var(--accent-ember-dim); }
  50% { border-color: var(--accent-ember-bright); box-shadow: 0 0 12px var(--accent-ember-glow); }
}
```

---

## Future QoL — Additional Ideas

### Canvas Cursor Label
When in skill targeting mode, show a small floating label near the mouse cursor on the canvas displaying the skill name and a range circle overlay. Helps players understand what they're aiming while scanning the grid.

### Queue Preview Action Icons on Canvas
The numbered queue-path tiles on the canvas currently show step numbers (1, 2, 3...). Adding tiny icons (⚔, 🦶, ✦) at the step tile would reinforce what action each step represents. This builds on `overlayRenderer.js → drawQueuePreview()`.

### Audio Confirmation Cues
A subtle click/chime sound when an action successfully queues (confirms input registered). A different tone when the queue is full (feedback that the input was rejected). Uses the existing Audio infrastructure.

### Targeting Mode Edge Glow
When entering skill targeting mode, briefly flash the canvas border with the skill's color (purple for offensive, green for heals) to draw attention to the grid area where the player needs to click.

### Turn Execution Flash
When the turn timer hits zero and actions execute, briefly highlight the intent banner with a white flash to signal "your actions are resolving now." Then transition to the new intent state for the next turn.

### Group Intent Summary
When multiple party members are selected (multi-select), show a compact summary: "3 units → Pursuing Goblin Scout" or "Group moving to (5, 3)". Currently the intent banner only reflects the active/primary unit.

### Intent History / Last Action Recap
After a turn resolves, briefly show the *last* intent that was executed ("Attacked Goblin → 12 dmg") for 1–2 seconds before transitioning to the new state. This gives the player confirmation that their action resolved and what it did, bridging the gap between intent and outcome.

### Banner Transition Animations
Smooth fade/slide transitions when the intent changes state (e.g., from "Pursuing" to "Attacking" when reaching the target). Currently the text snaps instantly — a 200ms crossfade would feel more polished.

### Target HP Preview in Banner
When an auto-target pursuit or selected target intent is active, briefly show the target's HP bar or percentage alongside the name: "Pursuing: Goblin Scout (45% HP)". Reduces the need to glance at the enemy panel.
