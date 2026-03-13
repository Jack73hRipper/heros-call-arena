// ─────────────────────────────────────────────────────────────────────────────
// ParticleManager.js — Bridges the particle engine with the game's combat events
//
// Data-driven: reads particle-effects.json to decide which presets fire for
// which game actions. Change the mapping JSON to swap effects — no code edits.
//
// Runs its own requestAnimationFrame loop on a dedicated overlay <canvas>
// so particles never trigger React re-renders.
// ─────────────────────────────────────────────────────────────────────────────

import { ParticleEngine } from './ParticleEngine.js';
import { ParticleProjectile } from './ParticleProjectile.js';
import { TILE_SIZE } from '../renderConstants.js';

export class ParticleManager {
  /**
   * @param {HTMLCanvasElement} canvas — overlay canvas positioned on top of the game canvas
   */
  constructor(canvas) {
    this.canvas = canvas;
    this.ctx = canvas.getContext('2d');
    this.engine = new ParticleEngine();

    /** @type {object|null} Effect mapping loaded from particle-effects.json */
    this.effectMap = null;

    /** Viewport offset in tiles (updated each frame by Arena) */
    this.viewportOffsetX = 0;
    this.viewportOffsetY = 0;

    /**
     * Emitters that follow a player each frame.
     * @type {Array<{ emitter: Emitter, playerId: string }>}
     */
    this._trackedEmitters = [];

    /**
     * Phase 14E: Active CC status emitters keyed by `${playerId}:${ccType}`.
     * Maintains looping emitters that persist while a unit has a CC buff.
     * @type {Map<string, { emitter: Emitter, playerId: string }>}
     */
    this._ccEmitters = new Map();

    /**
     * Persistent buff aura emitters keyed by `${playerId}:${buffKey}`.
     * Mirrors CC emitters but for positive buffs (armor, war cry, evasion, etc.).
     * @type {Map<string, { emitter: Emitter, playerId: string, yOffset: number }>}
     */
    this._buffEmitters = new Map();

    /**
     * Phase 18E (E5): Persistent affix ambient particle emitters keyed by
     * `${playerId}:${affixId}`. Looping emitters that follow enhanced monsters
     * to provide visual hints of their affixes (fire embers, frost crystals, etc.).
     * @type {Map<string, { emitter: Emitter, playerId: string }>}
     */
    this._affixEmitters = new Map();

    /**
     * Phase 23: Persistent AoE ground zone emitters keyed by zone id.
     * Looping emitters anchored at fixed tile positions for Miasma, Enfeeble zones.
     * @type {Map<string, { emitter: Emitter, x: number, y: number }>}
     */
    this._zoneEmitters = new Map();

    /**
     * Phase 14G: Active projectiles in flight.
     * Each projectile moves from caster → victim in pixel-space, emitting a
     * trail, then fires the impact effect on arrival.
     * @type {ParticleProjectile[]}
     */
    this._projectiles = [];

    /**
     * Reference to current players map, kept up-to-date by Arena.jsx.
     * Used in the rAF loop to reposition tracked emitters.
     * @type {Object|null}
     */
    this._playersRef = null;

    // Animation loop state
    this._lastTime = 0;
    this._rafId = null;
    this._running = false;

    // ── Tab-visibility lifecycle ──
    // When the tab is hidden the browser pauses rAF, but WebSocket messages
    // keep arriving and React effects keep calling processActions /
    // updateCCStatus / updateBuffStatus.  Without a guard those calls would
    // create emitters that pile up in the engine, producing a burst of
    // stale effects the moment the user alt-tabs back.
    //
    // Solution: set _hidden = true while the document is not visible.
    // All public trigger methods early-return when hidden.  On return we
    // clear one-shot emitters and rebuild persistent auras from current
    // game state so the visual layer is immediately correct.
    this._hidden = document.hidden;
    this._onVisibilityChange = this._onVisibilityChange.bind(this);
    document.addEventListener('visibilitychange', this._onVisibilityChange);
  }

  // ─── Initialization ────────────────────────────────────────────────────────

  /**
   * Load preset definitions and the effect mapping config.
   * Call once at mount time.
   */
  async init() {
    try {
      // Cache-bust with timestamp so edits to public/ JSON files take effect
      // immediately without requiring a hard-refresh.
      const baseUrl = import.meta.env.BASE_URL;
      const cacheBust = `?t=${Date.now()}`;
      const [presetsRes, mapRes] = await Promise.all([
        fetch(`${baseUrl}particle-presets.json${cacheBust}`),
        fetch(`${baseUrl}particle-effects.json${cacheBust}`),
      ]);
      if (presetsRes.ok) {
        const data = await presetsRes.json();
        let presets;
        if (Array.isArray(data)) {
          // Legacy: single flat array
          presets = data;
        } else if (data.files) {
          // New: index file pointing to category files
          const fetches = data.files.map(f =>
            fetch(`${baseUrl}${f}${cacheBust}`).then(r => r.json())
          );
          const arrays = await Promise.all(fetches);
          presets = arrays.flat();
        }
        if (presets) {
          this.engine.loadPresets(presets);
          const names = presets.map(p => p.name);
          console.log(`[ParticleManager] Loaded ${presets.length} presets:`, names);
        }
      } else {
        console.warn('[ParticleManager] Could not load particle-presets.json');
      }
      if (mapRes.ok) {
        this.effectMap = await mapRes.json();
        const skillKeys = Object.keys(this.effectMap.skills || {});
        console.log(`[ParticleManager] Effect mapping loaded — ${skillKeys.length} skills:`, skillKeys);
      } else {
        console.warn('[ParticleManager] Could not load particle-effects.json');
      }

      // ── Boot diagnostic: cross-check all mapped effects against loaded presets ──
      if (this.effectMap && this.engine.presets.size > 0) {
        const allMapped = [];
        for (const section of ['combat', 'skills', 'items', 'environment', 'buff_status']) {
          const entries = this.effectMap[section] || {};
          for (const [key, mapping] of Object.entries(entries)) {
            if (mapping.effect) allMapped.push({ section, key, effect: mapping.effect });
            if (mapping.extras) {
              for (const extra of mapping.extras) {
                allMapped.push({ section, key, effect: extra });
              }
            }
          }
        }
        const missing = allMapped.filter(m => !this.engine.presets.has(m.effect));
        if (missing.length > 0) {
          console.error(`[ParticleManager] ⚠ ${missing.length} mapped effects have NO matching preset — these will NOT render:`);
          for (const m of missing) {
            console.error(`  ${m.section}.${m.key} → "${m.effect}" — MISSING from particle-presets.json`);
          }
        } else {
          console.log(`[ParticleManager] ✓ All ${allMapped.length} mapped effects verified — every effect has a matching preset`);
        }
      }
    } catch (err) {
      console.warn('[ParticleManager] Init failed:', err);
    }
  }

  // ─── Animation Loop ────────────────────────────────────────────────────────

  /** Start the rAF render loop. */
  start() {
    if (this._running) return;
    this._running = true;
    this._hidden = document.hidden;
    this._lastTime = performance.now();
    this._tick = this._tick.bind(this);
    this._rafId = requestAnimationFrame(this._tick);
  }

  /** Stop the rAF loop. */
  stop() {
    this._running = false;
    if (this._rafId) {
      cancelAnimationFrame(this._rafId);
      this._rafId = null;
    }
  }

  // ─── Tab-Visibility Lifecycle ──────────────────────────────────────────────

  /**
   * Handle document visibilitychange events.
   * When hidden  → set flag so trigger methods become no-ops.
   * When visible → clear stale one-shot emitters, reset rAF timestamp to
   *                avoid a large dt spike, and rebuild persistent auras.
   */
  _onVisibilityChange() {
    this._hidden = document.hidden;

    if (!document.hidden) {
      // ── Returning to the tab ──
      console.log('[ParticleManager] Tab visible — clearing stale emitters and resyncing auras');

      // 1. Reset the rAF timestamp so the first tick after return uses a
      //    tiny dt instead of a multi-second jump.
      this._lastTime = performance.now();

      // 2. Wipe all one-shot emitters and projectiles that accumulated
      //    while hidden (there should be none thanks to the guards, but
      //    this is a safety net).
      this.engine.clear();
      this._trackedEmitters = [];
      for (const proj of this._projectiles) proj.forceComplete();
      this._projectiles = [];

      // 3. Tear down persistent aura emitters — they reference emitters
      //    that were just cleared from the engine.
      this._ccEmitters.clear();
      this._buffEmitters.clear();
      this._affixEmitters.clear();

      // 4. Rebuild persistent auras from current game state.  The next
      //    React-driven call to updateCCStatus / updateBuffStatus will
      //    naturally recreate the correct emitters because _hidden is
      //    now false and the Maps are empty.
      //    If _playersRef is available we can kick that off immediately
      //    so auras appear on the very first rendered frame.
      if (this._playersRef && this.effectMap) {
        this.updateCCStatus(this._playersRef, this._lastVisibleTiles || null);
        this.updateBuffStatus(this._playersRef, this._lastVisibleTiles || null);
        this.updateAffixStatus(this._playersRef, this._lastVisibleTiles || null);
      }
    } else {
      console.log('[ParticleManager] Tab hidden — particle triggers paused');
    }
  }

  /**
   * Update the reference to current players map.
   * Call whenever players state changes so tracked emitters follow correctly.
   * @param {Object} players — { id: { position: {x, y}, ... } }
   */
  setPlayers(players) {
    this._playersRef = players;
  }

  /** Internal rAF callback. */
  _tick(now) {
    if (!this._running) return;

    const dt = Math.min((now - this._lastTime) / 1000, 0.1); // cap at 100ms
    this._lastTime = now;

    // Reposition emitters that follow a player
    this._updateTrackedEmitters();

    // Phase 14E: Reposition CC status emitters
    this._updateCCEmitters();

    // Reposition persistent buff aura emitters
    this._updateBuffEmitters();

    // Phase 18E (E5): Reposition affix ambient emitters
    this._updateAffixEmitters();

    // Phase 23: Clean up dead zone emitters
    this._cleanupZoneEmitters();

    // Phase 14G: Update active projectiles
    this._updateProjectiles(dt);

    // Update engine
    this.engine.update(dt);

    // Clear & render
    this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
    if (this.engine.totalParticles > 0) {
      this.ctx.save();
      // Translate so that world coordinates map to screen correctly
      this.ctx.translate(
        -this.viewportOffsetX * TILE_SIZE,
        -this.viewportOffsetY * TILE_SIZE
      );
      this.engine.render(this.ctx);
      this.ctx.restore();
    }

    this._rafId = requestAnimationFrame(this._tick);
  }

  /**
   * Reposition tracked emitters to follow their bound player.
   * Called each rAF frame before engine.update().
   */
  _updateTrackedEmitters() {
    if (this._trackedEmitters.length === 0) return;
    const players = this._playersRef;

    for (let i = this._trackedEmitters.length - 1; i >= 0; i--) {
      const tracked = this._trackedEmitters[i];

      // Remove entry if emitter was cleaned up by the engine
      if (tracked.emitter.isDead) {
        this._trackedEmitters.splice(i, 1);
        continue;
      }

      // Move emitter to player's current tile center
      const p = players && players[tracked.playerId];
      if (p?.position) {
        const px = this._tileToPx(p.position.x, p.position.y);
        tracked.emitter.moveTo(px.x, px.y);
      }
    }
  }

  /** Update viewport offset (call whenever the camera moves). */
  setViewport(ox, oy) {
    this.viewportOffsetX = ox;
    this.viewportOffsetY = oy;
  }

  /** Resize the overlay canvas to match the game canvas. */
  resize(width, height) {
    this.canvas.width = width;
    this.canvas.height = height;
  }

  // ─── Coordinate Helpers ────────────────────────────────────────────────────

  /** Convert a tile position to world-pixel center. */
  _tileToPx(tileX, tileY) {
    return {
      x: tileX * TILE_SIZE + TILE_SIZE / 2,
      y: tileY * TILE_SIZE + TILE_SIZE / 2,
    };
  }

  // ─── Event Processing ──────────────────────────────────────────────────────

  /**
   * Process a batch of actions from a turn result and fire matching particle effects.
   * Called from Arena.jsx whenever a TURN_RESULT arrives.
   *
   * @param {Array} actions — action results from the server turn payload
   * @param {Object} players — current player map { id: { position, ... } }
   */
  processActions(actions, players) {
    if (this._hidden) return;  // Tab not visible — skip to avoid emitter buildup
    if (!this.effectMap || !actions) return;

    for (const act of actions) {
      // Phase 14D: Dodge events fire evasion-blur on the dodger
      if (!act.success && act.target_id) {
        const msg = (act.message || '').toLowerCase();
        if (msg.includes('dodged') || msg.includes('evaded')) {
          this._fireCombatEffect('dodge', act, players);
        }
        continue;
      }
      if (!act.success) continue;

      // ── Kill (fires on top of the normal hit effect) ──
      if (act.killed && this.effectMap.combat?.kill) {
        this._fireEffect(this.effectMap.combat.kill, act, players);
      }

      // Phase 18E (E10): Affix on-death explosion particles
      // Phase 18E (E11): Rare / Super Unique death celebration particles
      if (act.killed && act.target_id) {
        const victim = players[act.target_id];
        if (victim) {
          // E10: Fire Enchanted dies → fire explosion burst
          const victimAffixes = victim.affixes || [];
          if (victimAffixes.includes('fire_enchanted')) {
            const deathMapping = { effect: 'affix-fire-death-explosion', target: 'victim' };
            this._fireEffect(deathMapping, act, players);
          }
          // E10: Possessed dies → purple shadow explosion
          if (victimAffixes.includes('possessed')) {
            const deathMapping = { effect: 'affix-possessed-death-explosion', target: 'victim' };
            this._fireEffect(deathMapping, act, players);
          }
          // E11: Rare death → gold loot celebration
          if (victim.monster_rarity === 'rare') {
            const deathMapping = { effect: 'rare-death-celebration', target: 'victim' };
            this._fireEffect(deathMapping, act, players);
          }
          // E11: Super Unique death → large purple + gold celebration
          if (victim.monster_rarity === 'super_unique') {
            const deathMapping = { effect: 'super-unique-death-celebration', target: 'victim' };
            this._fireEffect(deathMapping, act, players);
          }
        }
      }

      // Phase 14F: Fire critical-hit preset for kills or high-damage hits
      const HIGH_DAMAGE_THRESHOLD = 25;
      if (act.damage_dealt && (act.killed || act.damage_dealt >= HIGH_DAMAGE_THRESHOLD)) {
        const critMapping = { effect: 'critical-hit', target: 'victim' };
        this._fireEffect(critMapping, act, players);
      }

      // ── Melee attack ──
      if (act.action_type === 'attack' && act.damage_dealt) {
        this._fireCombatEffect('attack', act, players);
      }

      // ── Ranged attack ──
      else if (act.action_type === 'ranged_attack' && act.damage_dealt) {
        this._fireCombatEffect('ranged_attack', act, players);
      }

      // ── Skill ──
      else if (act.action_type === 'skill' && act.skill_id) {
        this._fireSkillEffect(act, players);

        // Phase 25F: Undying Will revive trigger — dramatic resurrection burst
        // The revive action has heal_amount (revive HP), distinguishing it from
        // the initial cast (which has buff_applied). Fire extra dramatic effects.
        if (act.skill_id === 'undying_will' && act.heal_amount) {
          const reviveBurst = { effect: 'revenant-revive-burst', target: 'caster' };
          const reviveCrack = { effect: 'revenant-revive-ground-crack', target: 'caster' };
          this._fireEffect(reviveBurst, act, players);
          this._fireEffect(reviveCrack, act, players);
        }
      }

      // ── Item use (potion) ──
      else if (act.action_type === 'use_item') {
        const mapping = this.effectMap.items?.use_potion;
        if (mapping) {
          this._fireEffect(mapping, act, players);
        }
      }
    }
  }

  /**
   * Process environment events from a turn result (door opens, chests).
   *
   * @param {Array} doorChanges — [{x, y, state}]
   * @param {Array} chestOpened — [{x, y, ...}]
   */
  processEnvironment(doorChanges, chestOpened) {
    if (this._hidden) return;  // Tab not visible — skip to avoid emitter buildup
    if (!this.effectMap) return;

    if (doorChanges) {
      for (const dc of doorChanges) {
        if (dc.state === 'open' && this.effectMap.environment?.door_open) {
          const pos = this._tileToPx(dc.x, dc.y);
          const emitter = this.engine.emit(this.effectMap.environment.door_open.effect, pos.x, pos.y);
          if (emitter && emitter.loop) emitter.loop = false;
        }
      }
    }

    if (chestOpened) {
      for (const co of chestOpened) {
        if (this.effectMap.environment?.chest_open) {
          const pos = this._tileToPx(co.x, co.y);
          const emitter = this.engine.emit(this.effectMap.environment.chest_open.effect, pos.x, pos.y);
          if (emitter && emitter.loop) emitter.loop = false;
        }
      }
    }
  }

  // ─── Internal Helpers ──────────────────────────────────────────────────────

  /** Fire a combat effect from the combat section of the mapping. */
  _fireCombatEffect(actionType, act, players) {
    const mapping = this.effectMap.combat?.[actionType];
    if (!mapping) return;
    this._fireEffect(mapping, act, players);
  }

  /** Fire a skill effect from the skills section of the mapping. */
  _fireSkillEffect(act, players) {
    const mapping = this.effectMap.skills?.[act.skill_id];
    if (!mapping) {
      console.warn(`[ParticleManager] No mapping for skill "${act.skill_id}"`);
      // Fallback: no specific mapping, check if there's damage → generic melee-hit
      if (act.damage_dealt) {
        this._fireCombatEffect('attack', act, players);
      } else if (act.heal_amount) {
        const fallback = this.effectMap.skills?.heal;
        if (fallback) this._fireEffect(fallback, act, players);
      }
      return;
    }
    console.log(`[ParticleManager] Firing skill effect: ${act.skill_id} → ${mapping.effect} (target=${mapping.target})`);
    this._fireEffect(mapping, act, players);
  }

  /**
   * Resolve a mapping entry and emit its effect(s).
   * If the mapping has a `projectile` config, launches a traveling projectile
   * from caster → target; the impact fires on arrival. Otherwise fires immediately.
   *
   * @param {object} mapping — { effect, target, projectile?, extras?, extrasTarget? }
   * @param {object} act — the action result
   * @param {object} players — player map
   */
  _fireEffect(mapping, act, players) {
    const pos = this._resolvePosition(mapping.target, act, players);
    if (!pos) {
      console.warn(`[ParticleManager] Could not resolve position for "${mapping.effect}" (target="${mapping.target}", player_id=${act.player_id}, target_id=${act.target_id})`);
      return;
    }

    // Phase 14G: If the mapping has a projectile config, launch a traveling
    // projectile instead of firing the impact instantly.
    if (mapping.projectile && mapping.projectile.trail) {
      this._launchProjectile(mapping, act, players, pos);
      return;
    }

    // No projectile — fire the impact immediately (original behavior)
    this._fireImpact(mapping, act, players, pos);
  }

  /**
   * Resolve the player ID to follow from a target type.
   * @param {string} target — 'victim' | 'caster' | 'destination'
   * @param {object} act — the action result
   * @returns {string|null}
   */
  _resolveFollowId(target, act) {
    switch (target) {
      case 'caster':
        return act.player_id || null;
      case 'victim':
        return act.target_id || null;
      default:
        return null;
    }
  }

  /**
   * Resolve a target type to world-pixel coordinates.
   * @param {string} target — 'victim' | 'caster' | 'destination' | 'tile'
   * @param {object} act — action result
   * @param {object} players — player map
   * @returns {{ x: number, y: number } | null}
   */
  _resolvePosition(target, act, players) {
    switch (target) {
      case 'victim': {
        const p = act.target_id && players[act.target_id];
        if (p?.position) return this._tileToPx(p.position.x, p.position.y);
        break;
      }
      case 'caster': {
        const p = act.player_id && players[act.player_id];
        if (p?.position) return this._tileToPx(p.position.x, p.position.y);
        break;
      }
      case 'destination': {
        // For teleport-type skills: use to_x/to_y if available, else target position
        if (act.to_x != null && act.to_y != null) {
          return this._tileToPx(act.to_x, act.to_y);
        }
        const p = act.target_id && players[act.target_id];
        if (p?.position) return this._tileToPx(p.position.x, p.position.y);
        break;
      }
      case 'tile': {
        if (act.to_x != null && act.to_y != null) {
          return this._tileToPx(act.to_x, act.to_y);
        }
        break;
      }
      default:
        break;
    }
    return null;
  }

  // ─── Phase 14E: CC Status Particle Management ─────────────────────────────

  /**
   * Reposition CC status emitters to follow their bound player each frame.
   * Also removes emitters that have died (shouldn't happen for looping, but safety).
   */
  _updateCCEmitters() {
    if (this._ccEmitters.size === 0) return;
    const players = this._playersRef;

    for (const [key, tracked] of this._ccEmitters) {
      if (tracked.emitter.isDead) {
        this._ccEmitters.delete(key);
        continue;
      }
      const p = players && players[tracked.playerId];
      if (p?.position) {
        const px = this._tileToPx(p.position.x, p.position.y);
        // Stun stars orbit above the unit, slow frost at the unit center
        if (key.endsWith(':stun')) {
          tracked.emitter.moveTo(px.x, px.y - 12);
        } else {
          tracked.emitter.moveTo(px.x, px.y);
        }
      }
    }
  }

  /**
   * Phase 14E: Scan players for active CC buffs and maintain looping particle emitters.
   * Creates emitters for new CC states, removes emitters for expired CC states.
   * 
   * Call this every time players state updates (from Arena.jsx).
   *
   * @param {Object} players — { id: { position, active_buffs, is_alive, ... } }
   * @param {Set|null} visibleTiles — FOV tile set (null = show all)
   */
  updateCCStatus(players, visibleTiles) {
    if (this._hidden) return;  // Tab not visible — skip to avoid emitter buildup
    this._lastVisibleTiles = visibleTiles;  // Cache for resync on tab return
    if (!this.effectMap || !players) return;

    const ccMappings = this.effectMap.cc_status;
    if (!ccMappings) return;

    const ccTypes = Object.keys(ccMappings); // ['stun', 'slow']
    const activeKeys = new Set();

    for (const [pid, p] of Object.entries(players)) {
      if (!p.is_alive || p.is_alive === false || !p.position) continue;
      if (p.extracted) continue;

      // Skip units outside FOV
      if (visibleTiles && !visibleTiles.has(`${p.position.x},${p.position.y}`)) continue;

      const buffs = p.active_buffs || [];
      for (const ccType of ccTypes) {
        const hasBuff = buffs.some(b => b.type === ccType);
        const key = `${pid}:${ccType}`;

        if (hasBuff) {
          activeKeys.add(key);

          // If we don't already have a looping emitter for this, create one
          if (!this._ccEmitters.has(key)) {
            const mapping = ccMappings[ccType];
            const pos = this._tileToPx(p.position.x, p.position.y);
            const spawnY = ccType === 'stun' ? pos.y - 12 : pos.y;
            const emitter = this.engine.emit(mapping.effect, pos.x, spawnY);
            if (emitter) {
              // Keep it looping — it will persist until we manually stop it
              this._ccEmitters.set(key, { emitter, playerId: pid });
              console.log(`[ParticleManager] CC emitter started: ${key} → ${mapping.effect}`);
            }
          }
        }
      }
    }

    // Clean up emitters for CC states that are no longer active
    for (const [key, tracked] of this._ccEmitters) {
      if (!activeKeys.has(key)) {
        // Stop the looping emitter — it will finish its current particles and die
        tracked.emitter.loop = false;
        this._ccEmitters.delete(key);
        console.log(`[ParticleManager] CC emitter stopped: ${key}`);
      }
    }
  }

  // ─── Persistent Buff Aura Management ─────────────────────────────────────

  /**
   * Reposition buff aura emitters to follow their bound player each frame.
   * Removes emitters that have died unexpectedly.
   */
  _updateBuffEmitters() {
    if (this._buffEmitters.size === 0) return;
    const players = this._playersRef;

    for (const [key, tracked] of this._buffEmitters) {
      if (tracked.emitter.isDead) {
        this._buffEmitters.delete(key);
        continue;
      }
      const p = players && players[tracked.playerId];
      if (p?.position) {
        const px = this._tileToPx(p.position.x, p.position.y);
        tracked.emitter.moveTo(px.x, px.y + (tracked.yOffset || 0));
      }
    }
  }

  /**
   * Scan players for active positive buffs and maintain looping particle emitters.
   * Creates emitters for new buff states, removes emitters for expired ones.
   * Mirrors the CC status system but for beneficial effects.
   *
   * Supports `buff_id_overrides` so the generic "buff" type can show different
   * auras per skill (e.g. war_cry gets orange embers, shield_of_faith gets gold).
   *
   * Call this every time players state updates (from Arena.jsx).
   *
   * @param {Object} players — { id: { position, active_buffs, is_alive, ... } }
   * @param {Set|null} visibleTiles — FOV tile set (null = show all)
   */
  updateBuffStatus(players, visibleTiles) {
    if (this._hidden) return;  // Tab not visible — skip to avoid emitter buildup
    this._lastVisibleTiles = visibleTiles;  // Cache for resync on tab return
    if (!this.effectMap || !players) return;

    const buffMappings = this.effectMap.buff_status;
    if (!buffMappings) return;

    const buffTypes = Object.keys(buffMappings).filter(k => !k.startsWith('_'));
    const activeKeys = new Set();

    for (const [pid, p] of Object.entries(players)) {
      if (!p.is_alive || p.is_alive === false || !p.position) continue;
      if (p.extracted) continue;

      // Skip units outside FOV
      if (visibleTiles && !visibleTiles.has(`${p.position.x},${p.position.y}`)) continue;

      const buffs = p.active_buffs || [];

      for (const buffType of buffTypes) {
        // Find all active buffs of this type
        const matchingBuffs = buffs.filter(b => b.type === buffType);
        if (matchingBuffs.length === 0) continue;

        const mapping = buffMappings[buffType];

        // For the generic "buff" type, each buff_id may get a unique aura
        // via buff_id_overrides. For other types (evasion, hot, etc.), one aura per type.
        if (buffType === 'buff' && mapping.buff_id_overrides) {
          for (const b of matchingBuffs) {
            const override = mapping.buff_id_overrides[b.buff_id];
            const effectName = override ? override.effect : mapping.effect;
            const yOffset = override?.yOffset ?? mapping.yOffset ?? 0;
            const key = `${pid}:buff:${b.buff_id}`;
            activeKeys.add(key);

            if (!this._buffEmitters.has(key)) {
              const pos = this._tileToPx(p.position.x, p.position.y);
              const emitter = this.engine.emit(effectName, pos.x, pos.y + yOffset);
              if (emitter) {
                this._buffEmitters.set(key, { emitter, playerId: pid, yOffset });
                console.log(`[ParticleManager] Buff aura started: ${key} → ${effectName}`);
              }
            }
          }
        } else {
          // One aura per buff type (evasion, hot, shield_charges, taunt)
          const key = `${pid}:${buffType}`;
          activeKeys.add(key);

          if (!this._buffEmitters.has(key)) {
            const yOffset = mapping.yOffset ?? 0;
            const pos = this._tileToPx(p.position.x, p.position.y);
            const emitter = this.engine.emit(mapping.effect, pos.x, pos.y + yOffset);
            if (emitter) {
              this._buffEmitters.set(key, { emitter, playerId: pid, yOffset });
              console.log(`[ParticleManager] Buff aura started: ${key} → ${mapping.effect}`);
            }
          }
        }
      }
    }

    // Clean up emitters for buff states that are no longer active
    for (const [key, tracked] of this._buffEmitters) {
      if (!activeKeys.has(key)) {
        tracked.emitter.loop = false;
        this._buffEmitters.delete(key);
        console.log(`[ParticleManager] Buff aura stopped: ${key}`);
      }
    }
  }

  // ─── Phase 18E (E5): Affix Ambient Particle Management ─────────────────

  /**
   * Map from server affix IDs to particle preset names.
   * Only affixes with a meaningful ambient visual are listed here.
   * @type {Object<string, string>}
   */
  static AFFIX_PRESET_MAP = {
    fire_enchanted:  'affix-fire-enchanted',
    cold_enchanted:  'affix-cold-enchanted',
    thorns:          'affix-thorns',
    might_aura:      'affix-might-aura',
    conviction_aura: 'affix-conviction-aura',
    teleporter:      'affix-teleporter',
    regenerating:    'affix-regenerating',
    shielded:        'affix-shielded',
  };

  /**
   * Reposition affix ambient emitters to follow their bound unit each frame.
   * Removes emitters whose underlying Emitter was cleaned up by the engine.
   */
  _updateAffixEmitters() {
    if (this._affixEmitters.size === 0) return;
    const players = this._playersRef;

    for (const [key, tracked] of this._affixEmitters) {
      if (tracked.emitter.isDead) {
        this._affixEmitters.delete(key);
        continue;
      }
      const p = players && players[tracked.playerId];
      if (p?.position) {
        const px = this._tileToPx(p.position.x, p.position.y);
        tracked.emitter.moveTo(px.x, px.y);
      }
    }
  }

  /**
   * Phase 18E (E5): Scan players for monster affixes and maintain looping
   * ambient particle emitters.  Creates emitters for new affix states,
   * removes emitters when the unit dies or leaves FOV.
   *
   * @param {Object} players — { id: { position, affixes, monster_rarity, is_alive, ... } }
   * @param {Set|null} visibleTiles — FOV tile set (null = show all)
   */
  updateAffixStatus(players, visibleTiles) {
    if (this._hidden) return;
    this._lastVisibleTiles = visibleTiles;
    if (!players) return;

    const presetMap = ParticleManager.AFFIX_PRESET_MAP;
    const activeKeys = new Set();

    for (const [pid, p] of Object.entries(players)) {
      if (!p.is_alive || p.is_alive === false || !p.position) continue;
      if (p.extracted) continue;

      // Only enhanced monsters have affixes
      const affixes = p.affixes;
      if (!affixes || affixes.length === 0) continue;

      // Skip units outside FOV
      if (visibleTiles && !visibleTiles.has(`${p.position.x},${p.position.y}`)) continue;

      for (const affixId of affixes) {
        const presetName = presetMap[affixId];
        if (!presetName) continue; // No visual for this affix (e.g. extra_strong, cursed)

        const key = `${pid}:${affixId}`;
        activeKeys.add(key);

        if (!this._affixEmitters.has(key)) {
          const pos = this._tileToPx(p.position.x, p.position.y);
          const emitter = this.engine.emit(presetName, pos.x, pos.y);
          if (emitter) {
            this._affixEmitters.set(key, { emitter, playerId: pid });
            console.log(`[ParticleManager] Affix emitter started: ${key} → ${presetName}`);
          }
        }
      }
    }

    // Clean up emitters for units that died, left FOV, or lost their affix
    for (const [key, tracked] of this._affixEmitters) {
      if (!activeKeys.has(key)) {
        tracked.emitter.loop = false;
        this._affixEmitters.delete(key);
        console.log(`[ParticleManager] Affix emitter stopped: ${key}`);
      }
    }
  }

  // ─── Phase 23: Ground Zone Particle Management ──────────────────────────

  /** Preset name lookup for ground zone skills. */
  static ZONE_PRESET_MAP = {
    miasma: 'plague-miasma-zone-ambient',
    enfeeble: 'plague-enfeeble-zone-ambient',
  };

  /**
   * Create/remove looping particle emitters for persistent AoE ground zones.
   * Called from Arena.jsx whenever groundZones state changes.
   *
   * @param {Array} zones - Array of { id, x, y, radius, turnsRemaining, color, skillId }
   */
  updateGroundZones(zones) {
    if (this._hidden) return;
    if (!zones) zones = [];

    const activeIds = new Set(zones.map(z => z.id));

    // Create emitters for new zones
    for (const zone of zones) {
      if (this._zoneEmitters.has(zone.id)) continue;

      const presetName = ParticleManager.ZONE_PRESET_MAP[zone.skillId];
      if (!presetName) continue;

      const pos = this._tileToPx(zone.x, zone.y);
      const emitter = this.engine.emit(presetName, pos.x, pos.y);
      if (emitter) {
        this._zoneEmitters.set(zone.id, { emitter, x: zone.x, y: zone.y });
        console.log(`[ParticleManager] Zone emitter started: ${zone.id} → ${presetName}`);
      }
    }

    // Stop emitters for expired zones
    for (const [id, tracked] of this._zoneEmitters) {
      if (!activeIds.has(id)) {
        tracked.emitter.loop = false;
        this._zoneEmitters.delete(id);
        console.log(`[ParticleManager] Zone emitter stopped: ${id}`);
      }
    }
  }

  /**
   * Cleanup dead zone emitters (safety net — normally removed by updateGroundZones).
   */
  _cleanupZoneEmitters() {
    for (const [id, tracked] of this._zoneEmitters) {
      if (tracked.emitter.isDead) {
        this._zoneEmitters.delete(id);
      }
    }
  }

  // ─── Phase 14G: Projectile Management ───────────────────────────────────

  /**
   * Update all active projectiles each frame.
   * Removes dead projectiles (arrived + trail particles finished).
   * @param {number} dt — delta time in seconds
   */
  _updateProjectiles(dt) {
    for (let i = this._projectiles.length - 1; i >= 0; i--) {
      const proj = this._projectiles[i];
      proj.update(dt);
      if (proj.isDead) {
        this._projectiles.splice(i, 1);
      }
    }
  }

  /**
   * Create a projectile that travels from caster to the resolved target
   * position, then fires the impact effect on arrival.
   *
   * @param {object} mapping — the full effect mapping (with .projectile config)
   * @param {object} act — action result from the server
   * @param {object} players — player map
   * @param {{ x: number, y: number }} targetPos — resolved world-pixel target position
   */
  _launchProjectile(mapping, act, players, targetPos) {
    // Resolve caster position for the start point
    const casterPos = this._resolvePosition('caster', act, players);
    if (!casterPos) {
      // Can't find caster — fall back to immediate impact
      console.warn('[ParticleManager] Projectile: no caster position, firing impact immediately');
      this._fireImpact(mapping, act, players, targetPos);
      return;
    }

    const projCfg = mapping.projectile;
    const projectile = new ParticleProjectile(this.engine, {
      trailPreset: projCfg.trail,
      headPreset: projCfg.head || null,
      fromX: casterPos.x,
      fromY: casterPos.y,
      toX: targetPos.x,
      toY: targetPos.y,
      speed: projCfg.speed || 400,
      arc: projCfg.arc || 0,
      onArrive: () => {
        // On arrival, fire the impact effect + extras at the destination
        this._fireImpact(mapping, act, players, targetPos);
      },
    });

    this._projectiles.push(projectile);
    console.log(`[ParticleManager] Projectile launched: ${projCfg.trail}${projCfg.head ? ` + ${projCfg.head}` : ''} → ${mapping.effect} (speed=${projCfg.speed}, arc=${projCfg.arc || 0})`);
  }

  /**
   * Fire the impact portion of an effect mapping at a resolved position.
   * This is what _fireEffect does today, but extracted so projectiles can
   * call it on arrival without re-resolving positions.
   *
   * @param {object} mapping — { effect, target, extras?, loopDuration?, follow? }
   * @param {object} act — action result
   * @param {object} players — player map
   * @param {{ x: number, y: number }} pos — world-pixel impact position
   */
  _fireImpact(mapping, act, players, pos) {
    const emitter = this.engine.emit(mapping.effect, pos.x, pos.y);
    if (!emitter) {
      console.warn(`[ParticleManager] Failed to emit "${mapping.effect}" — preset not found in engine`);
    }
    if (emitter && emitter.loop) {
      if (mapping.loopDuration && mapping.loopDuration > 0) {
        setTimeout(() => { emitter.loop = false; }, mapping.loopDuration * 1000);
      } else {
        emitter.loop = false;
      }
    }

    // Follow tracking
    if (emitter && mapping.follow) {
      const followId = this._resolveFollowId(mapping.target, act);
      if (followId) {
        this._trackedEmitters.push({ emitter, playerId: followId });
      }
    }

    // Fire extras
    if (mapping.extras) {
      const extrasTarget = mapping.extrasTarget || mapping.target;
      const extrasPos = mapping.extrasTarget
        ? this._resolvePosition(mapping.extrasTarget, act, players)
        : pos;
      if (extrasPos) {
        for (const extraName of mapping.extras) {
          const extra = this.engine.emit(extraName, extrasPos.x, extrasPos.y);
          if (extra && extra.loop) {
            if (mapping.loopDuration && mapping.loopDuration > 0) {
              setTimeout(() => { extra.loop = false; }, mapping.loopDuration * 1000);
            } else {
              extra.loop = false;
            }
          }
          if (extra && mapping.follow) {
            const followId = this._resolveFollowId(extrasTarget, act);
            if (followId) {
              this._trackedEmitters.push({ emitter: extra, playerId: followId });
            }
          }
        }
      }
    }
  }

  /** Clean up — stop loop, clear engine, remove visibility listener. */
  destroy() {
    this.stop();
    document.removeEventListener('visibilitychange', this._onVisibilityChange);
    // Force-complete any in-flight projectiles
    for (const proj of this._projectiles) {
      proj.forceComplete();
    }
    this._projectiles = [];
    this.engine.clear();
    this._trackedEmitters = [];
    this._ccEmitters.clear();
    this._buffEmitters.clear();
    this._affixEmitters.clear();
    this._playersRef = null;
    this._lastVisibleTiles = null;
  }
}
