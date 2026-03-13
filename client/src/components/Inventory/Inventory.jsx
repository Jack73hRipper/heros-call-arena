import React, { useState, useCallback, useRef, useEffect, useMemo } from 'react';
import { useGameState, useGameDispatch, useCombatStats } from '../../context/GameStateContext';
import ItemTooltip from './ItemTooltip';
import { getItemSetInfo } from '../../utils/itemUtils';
import { CLASS_SHAPES, CLASS_COLORS } from '../../canvas/renderConstants';
import HeroSprite from '../TownHub/HeroSprite';

/**
 * Slot icon display (visual indicators for equipment slots)
 */
const SLOT_ICONS = {
  weapon: '\u2694',   // ⚔ crossed swords
  armor: '\u229B',    // ⊛ shield-like
  accessory: '\u25C7', // ◇ diamond
};

/**
 * Item type icon mapping (text-based, no emojis).
 */
const ITEM_ICONS = {
  weapon: 'W',
  armor: 'A',
  accessory: 'R',
  consumable: 'P',
};

/**
 * Slot label display names
 */
const SLOT_LABELS = {
  weapon: 'Weapon',
  armor: 'Armor',
  accessory: 'Accessory',
};

/**
 * Rarity sort order (higher = better)
 */
const RARITY_ORDER = {
  common: 0, uncommon: 0, magic: 1, rare: 2, epic: 3, unique: 4, set: 5,
};

/**
 * Item type sort order
 */
const TYPE_ORDER = {
  weapon: 0, armor: 1, accessory: 2, consumable: 3,
};

/**
 * Sort modes for bag
 */
const SORT_MODES = [
  { key: 'type', label: 'Type' },
  { key: 'rarity', label: 'Rarity' },
  { key: 'name', label: 'Name' },
];

/**
 * Sort bag items according to mode.
 */
function sortBagItems(items, mode) {
  const indexed = items.map((item, i) => ({ item, origIndex: i }));
  indexed.sort((a, b) => {
    if (!a.item && !b.item) return 0;
    if (!a.item) return 1;
    if (!b.item) return -1;
    if (mode === 'type') {
      const ta = TYPE_ORDER[a.item.item_type] ?? 9;
      const tb = TYPE_ORDER[b.item.item_type] ?? 9;
      if (ta !== tb) return ta - tb;
      // Secondary: rarity descending
      const ra = RARITY_ORDER[a.item.rarity] ?? 0;
      const rb = RARITY_ORDER[b.item.rarity] ?? 0;
      return rb - ra;
    }
    if (mode === 'rarity') {
      const ra = RARITY_ORDER[a.item.rarity] ?? 0;
      const rb = RARITY_ORDER[b.item.rarity] ?? 0;
      if (ra !== rb) return rb - ra;
      // Secondary: type
      const ta = TYPE_ORDER[a.item.item_type] ?? 9;
      const tb = TYPE_ORDER[b.item.item_type] ?? 9;
      return ta - tb;
    }
    if (mode === 'name') {
      const na = (a.item.name || '').toLowerCase();
      const nb = (b.item.name || '').toLowerCase();
      return na.localeCompare(nb);
    }
    return 0;
  });
  return indexed;
}

/**
 * Class shape SVG icons for character portrait
 */
const CLASS_SHAPE_PATHS = {
  square: <rect x="6" y="6" width="20" height="20" rx="2" />,
  circle: <circle cx="16" cy="16" r="11" />,
  triangle: <polygon points="16,4 28,28 4,28" />,
  diamond: <polygon points="16,3 29,16 16,29 3,16" />,
  star: <polygon points="16,3 19.5,12 29,12 21.5,18 24,28 16,22 8,28 10.5,18 3,12 12.5,12" />,
  hexagon: <polygon points="16,3 27,9 27,23 16,29 5,23 5,9" />,
  crescent: <path d="M22,4 A13,13 0 1,1 22,28 A9,9 0 1,0 22,4 Z" />,
  shield: <path d="M16,2 C20,2 24,5 24,9 L21,19 16,24 11,19 8,9 C8,5 12,2 16,2 Z" />,
  flask: <path d="M 42 10 L 58 10 L 58 25 L 72 38 Q 82 55 72 75 L 68 82 L 32 82 L 28 75 Q 18 55 28 38 L 42 25 Z" />,
  coffin: <path d="M 38 5 L 62 5 L 72 30 L 60 95 L 40 95 L 28 30 Z" />,
  totem: <path d="M 40 10 L 60 10 L 65 35 L 70 35 L 70 65 L 75 65 L 75 90 L 25 90 L 25 65 L 30 65 L 30 35 L 35 35 Z" />,
};

/**
 * Inventory — Equipment slots (3) + bag grid (10 slots).
 * Click equippable item in bag → equip. Click equipped item → unequip.
 * Use consumable sends use_item action.
 *
 * Phase 6E-5: Rendered as a toggle overlay/modal instead of inline sidebar.
 * Party inventory: When controlling a party member, shows their inventory.
 * Transfer: Click "Transfer" on a bag item to move it to another party member.
 * Props: sendAction, onClose
 */
/**
 * Format buff names for display.
 */
function formatBuffName(buffId) {
  const names = {
    war_cry: 'War Cry', double_strike: 'Double Strike', power_shot: 'Power Shot',
    heal: 'Heal', shadow_step: 'Shadow Step', wither: 'Wither', ward: 'Ward',
    divine_sense: 'Divine Sense', rebuke: 'Rebuke', shield_of_faith: 'Shield of Faith',
    exorcism: 'Exorcism', prayer: 'Prayer', detected: 'Detected',
    ballad_of_might: 'Ballad of Might', dirge_of_weakness: 'Dirge of Weakness',
    verse_of_haste: 'Verse of Haste', cacophony: 'Cacophony',
    crimson_veil: 'Crimson Veil', blood_frenzy: 'Blood Frenzy',
    miasma: 'Miasma', plague_flask: 'Plague Flask',
    enfeeble: 'Enfeeble', inoculate: 'Inoculate',
    grave_thorns: 'Grave Thorns', grave_chains: 'Grave Chains',
    undying_will: 'Undying Will', soul_rend: 'Soul Rend',
    healing_totem: 'Healing Totem', searing_totem: 'Searing Totem',
    soul_anchor: 'Soul Anchor', earthgrasp: 'Earthgrasp',
  };
  return names[buffId] || buffId.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
}

/**
 * Format buff effect description.
 */
function formatBuffEffect(buff) {
  if (buff.type === 'dot') return `${buff.damage_per_tick} dmg/turn`;
  if (buff.type === 'hot') return `+${buff.heal_per_tick} hp/turn`;
  if (buff.type === 'shield_charges') return `${buff.charges} charges (${buff.reflect_damage} reflect)`;
  if (buff.type === 'detection') return 'Revealed';
  if (buff.stat === 'all_damage_multiplier') return `${((buff.magnitude - 1) * 100).toFixed(0)}% damage`;
  if (buff.stat === 'damage_taken_multiplier') return `+${((buff.magnitude - 1) * 100).toFixed(0)}% damage taken`;
  if (buff.stat === 'damage_dealt_multiplier') {
    const pct = Math.round((1 - buff.magnitude) * 100);
    return `-${pct}% damage dealt`;
  }
  if (buff.stat === 'melee_damage_multiplier') return `${buff.magnitude}x melee`;
  if (buff.stat === 'ranged_damage_multiplier') return `${buff.magnitude}x ranged`;
  if (buff.stat === 'damage_reduction') return `${Math.round((1 - buff.magnitude) * 100)}% dmg red`;
  if (buff.stat === 'armor') return `+${buff.magnitude} armor`;
  if (buff.stat === 'thorns_damage') return `Reflects ${buff.magnitude} dmg per hit`;
  if (buff.stat === 'cheat_death') return `Revive at ${Math.round((buff.revive_hp_pct || 0.3) * 100)}% HP if killed`;
  if (buff.stat === 'soul_anchor') return 'Survives killing blow at 1 HP';
  if (buff.stat === 'rooted') return 'Cannot move — can still attack';
  return buff.stat ? `${buff.magnitude}x ${buff.stat.replace(/_/g, ' ')}` : 'active';
}

export default function Inventory({ sendAction, onClose }) {
  const {
    inventory, equipment, playerId, players,
    activeUnitId, partyMembers, partyInventories,
    classSkills, allClassSkills,
    isDungeon, currentFloor, gold, startGold,
  } = useGameState();
  const dispatch = useGameDispatch();
  const combatStats = useCombatStats();
  const [hoveredItem, setHoveredItem] = useState(null); // { item, source, slotKey, rect }
  const [transferItem, setTransferItem] = useState(null); // { index, item } — item being transferred
  const [showAdvancedStats, setShowAdvancedStats] = useState(false);
  const [bagSortMode, setBagSortMode] = useState(null); // null | 'type' | 'rarity' | 'name'
  const [confirmDestroyId, setConfirmDestroyId] = useState(null); // item_id awaiting confirm
  const panelRef = useRef(null);

  // Determine which unit's inventory to show
  const effectiveUnitId = activeUnitId || playerId;
  const isViewingPartyMember = activeUnitId && activeUnitId !== playerId;

  // Get the correct inventory/equipment for the viewed unit
  let viewInventory = inventory;
  let viewEquipment = equipment;
  if (isViewingPartyMember && partyInventories[activeUnitId]) {
    viewInventory = partyInventories[activeUnitId].inventory || [];
    viewEquipment = partyInventories[activeUnitId].equipment || { weapon: null, armor: null, accessory: null };
  }

  const viewedUnit = players[effectiveUnitId];
  const isAlive = viewedUnit?.is_alive !== false;
  const viewedName = viewedUnit?.username || 'Unknown';

  // Click-outside-to-close: if user clicks the backdrop (not the panel), close the overlay
  const handleBackdropClick = useCallback((e) => {
    if (panelRef.current && !panelRef.current.contains(e.target)) {
      if (transferItem) {
        setTransferItem(null); // Close transfer modal first
      } else {
        onClose?.();
      }
    }
  }, [onClose, transferItem]);

  // Close on Escape or I key
  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === 'Escape') {
        if (transferItem) {
          setTransferItem(null);
        } else {
          onClose?.();
        }
      }
      // I key toggles the panel closed (same key that opened it)
      if ((e.key === 'i' || e.key === 'I') && !e.ctrlKey && !e.metaKey && !e.altKey) {
        if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;
        e.preventDefault();
        if (transferItem) {
          setTransferItem(null);
        } else {
          onClose?.();
        }
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [onClose, transferItem]);

  const handleEquip = useCallback((item) => {
    if (!isAlive || !item?.item_id) return;
    const msg = { type: 'equip_item', item_id: item.item_id };
    if (isViewingPartyMember) msg.unit_id = activeUnitId;
    sendAction(msg);
  }, [isAlive, sendAction, isViewingPartyMember, activeUnitId]);

  const handleUnequip = useCallback((slot) => {
    if (!isAlive) return;
    const msg = { type: 'unequip_item', slot };
    if (isViewingPartyMember) msg.unit_id = activeUnitId;
    sendAction(msg);
  }, [isAlive, sendAction, isViewingPartyMember, activeUnitId]);

  const handleUseItem = useCallback((inventoryIndex) => {
    if (!isAlive) return;
    sendAction({ type: 'action', action_type: 'use_item', target_x: inventoryIndex });
  }, [isAlive, sendAction]);

  const handleTransfer = useCallback((toUnitId) => {
    if (!transferItem) return;
    sendAction({
      type: 'transfer_item',
      from_unit_id: effectiveUnitId,
      to_unit_id: toUnitId,
      item_index: transferItem.index,
    });
    setTransferItem(null);
  }, [transferItem, effectiveUnitId, sendAction]);

  const handleDestroyItem = useCallback((item) => {
    if (!isAlive || !item) return;
    const itemKey = item.instance_id || item.item_id;
    if (confirmDestroyId === itemKey) {
      const msg = { type: 'destroy_item', item_id: itemKey };
      if (isViewingPartyMember) msg.unit_id = activeUnitId;
      sendAction(msg);
      setConfirmDestroyId(null);
    } else {
      setConfirmDestroyId(itemKey);
    }
  }, [isAlive, sendAction, confirmDestroyId, isViewingPartyMember, activeUnitId]);

  const handleSlotMouseEnter = (e, item, source, slotKey) => {
    if (!item) return;
    const rect = e.currentTarget.getBoundingClientRect();
    setHoveredItem({ item, source, slotKey, rect });
  };

  const handleSlotMouseLeave = () => {
    setHoveredItem(null);
  };

  // Build list of transfer targets (alive party members + self if viewing party member)
  const transferTargets = [];
  if (partyMembers && partyMembers.length > 0) {
    // Add self (player's own unit) as a transfer target if viewing a party member
    if (isViewingPartyMember) {
      const selfUnit = players[playerId];
      if (selfUnit?.is_alive !== false) {
        transferTargets.push({
          unit_id: playerId,
          username: selfUnit.username || 'You',
          class_id: selfUnit.class_id,
          bagCount: inventory?.length || 0,
        });
      }
    }
    // Add party members (excluding the one we're currently viewing)
    for (const pm of partyMembers) {
      if (pm.unit_id === effectiveUnitId) continue;
      if (!pm.is_alive) continue;
      const pmInv = partyInventories[pm.unit_id];
      const pmBagCount = pmInv?.inventory?.length || 0;
      transferTargets.push({
        unit_id: pm.unit_id,
        username: pm.username || players[pm.unit_id]?.username || 'Ally',
        class_id: pm.class_id || players[pm.unit_id]?.class_id,
        bagCount: pmBagCount,
      });
    }
  }
  const canTransfer = transferTargets.length > 0;

  // Equipment slot data (defined early for use in useMemo hooks)
  const slots = ['weapon', 'armor', 'accessory'];

  // Sorted bag items (memoized)
  const sortedBag = useMemo(() => {
    if (!bagSortMode) return null;
    return sortBagItems(viewInventory, bagSortMode);
  }, [viewInventory, bagSortMode]);

  // Set bonus detection for equipment slots
  const equipmentSetInfo = useMemo(() => {
    const info = {};
    const setCounts = {}; // { setId: count }
    // First pass: count how many set pieces are equipped
    for (const slot of slots) {
      const item = viewEquipment[slot];
      if (!item) continue;
      const si = getItemSetInfo(item);
      if (si) {
        setCounts[si.setId] = (setCounts[si.setId] || 0) + 1;
      }
    }
    // Second pass: attach set info to each slot
    for (const slot of slots) {
      const item = viewEquipment[slot];
      if (!item) continue;
      const si = getItemSetInfo(item);
      if (si) {
        info[slot] = { ...si, equipped: setCounts[si.setId] || 0 };
      }
    }
    return info;
  }, [viewEquipment]);

  // Party quick-switch tabs — all controllable units (self + party members)
  const partyTabs = useMemo(() => {
    const tabs = [];
    // Always include self
    const selfUnit = players[playerId];
    if (selfUnit) {
      tabs.push({
        unit_id: playerId,
        username: selfUnit.username || 'You',
        class_id: selfUnit.class_id || '',
        is_alive: selfUnit.is_alive !== false,
        isSelf: true,
      });
    }
    // Add party members
    if (partyMembers && partyMembers.length > 0) {
      for (const pm of partyMembers) {
        tabs.push({
          unit_id: pm.unit_id,
          username: pm.username || players[pm.unit_id]?.username || 'Ally',
          class_id: pm.class_id || players[pm.unit_id]?.class_id || '',
          is_alive: pm.is_alive !== false,
          isSelf: false,
        });
      }
    }
    return tabs;
  }, [playerId, players, partyMembers]);

  const showPartyTabs = partyTabs.length > 1;

  const handlePartyTabClick = useCallback((unitId) => {
    if (unitId === playerId) {
      // Switch back to self
      dispatch({ type: 'SELECT_ACTIVE_UNIT', payload: null });
    } else {
      dispatch({ type: 'SELECT_ACTIVE_UNIT', payload: unitId });
    }
    setHoveredItem(null);
    setTransferItem(null);
  }, [playerId, dispatch]);

  // ---------- Character Stats ----------
  const unitClassId = viewedUnit?.class_id || '';
  const unitHp = viewedUnit?.hp ?? 0;
  const unitMaxHp = viewedUnit?.max_hp ?? 0;
  const unitAttack = viewedUnit?.attack_damage ?? 0;
  const unitRanged = viewedUnit?.ranged_damage ?? 0;
  const unitArmor = viewedUnit?.armor ?? 0;
  const unitVision = viewedUnit?.vision_range ?? 0;
  const hpPercent = unitMaxHp > 0 ? Math.round((unitHp / unitMaxHp) * 100) : 0;

  // Advanced stats from server player model
  const critChance = viewedUnit?.crit_chance ?? 0.05;
  const critDamage = viewedUnit?.crit_damage ?? 1.5;
  const dodgeChance = viewedUnit?.dodge_chance ?? 0;
  const dmgReduction = viewedUnit?.damage_reduction_pct ?? 0;
  const hpRegen = viewedUnit?.hp_regen ?? 0;
  const lifeOnHit = viewedUnit?.life_on_hit ?? 0;
  const cdrPct = viewedUnit?.cooldown_reduction_pct ?? 0;
  const thorns = viewedUnit?.thorns ?? 0;
  const goldFind = viewedUnit?.gold_find_pct ?? 0;
  const magicFind = viewedUnit?.magic_find_pct ?? 0;
  const armorPen = viewedUnit?.armor_pen ?? 0;
  const skillDmg = viewedUnit?.skill_damage_pct ?? 0;

  // Active buffs
  const activeBuffs = viewedUnit?.active_buffs || [];

  // Kill count from combat stats
  const unitStats = combatStats?.units?.[effectiveUnitId];
  const totalKills = unitStats?.kills ?? 0;

  // Calculate equipment bonus totals
  const equipBonuses = { attack_damage: 0, ranged_damage: 0, armor: 0, max_hp: 0 };
  for (const slot of slots) {
    const eqItem = viewEquipment[slot];
    if (eqItem?.stat_bonuses) {
      for (const [key, val] of Object.entries(eqItem.stat_bonuses)) {
        if (equipBonuses[key] !== undefined) equipBonuses[key] += val;
      }
    }
  }

  // Check if any advanced stats are non-default (worth showing)
  const hasAdvancedStats = critChance > 0.05 || critDamage > 1.5 || dodgeChance > 0 ||
    dmgReduction > 0 || hpRegen > 0 || lifeOnHit > 0 || cdrPct > 0 ||
    thorns > 0 || goldFind > 0 || magicFind > 0 || armorPen > 0 || skillDmg > 0;

  return (
    <div className="inventory-overlay-backdrop" onClick={handleBackdropClick}>
      <div className="inventory-overlay character-panel" ref={panelRef}>
        {/* Party Quick-Switch Tabs */}
        {showPartyTabs && (
          <div className="party-switch-tabs">
            {partyTabs.map((tab) => {
              const isActive = tab.isSelf ? !activeUnitId || activeUnitId === playerId : activeUnitId === tab.unit_id;
              const shapeKey = CLASS_SHAPES[tab.class_id] || 'circle';
              const shapeColor = CLASS_COLORS[tab.class_id] || '#888';
              return (
                <button
                  key={tab.unit_id}
                  className={`party-switch-tab ${isActive ? 'tab-active' : ''} ${!tab.is_alive ? 'tab-dead' : ''}`}
                  onClick={() => handlePartyTabClick(tab.unit_id)}
                  title={`${tab.username} (${tab.class_id || 'Hero'})${!tab.is_alive ? ' — Dead' : ''}`}
                >
                  <HeroSprite
                    classId={tab.class_id}
                    variant={players[tab.unit_id]?.sprite_variant || 1}
                    size={18}
                    grayscale={!tab.is_alive}
                    className="party-tab-icon"
                  />
                  <span className="party-tab-name">{tab.username}</span>
                </button>
              );
            })}
          </div>
        )}

        <div className="inventory-overlay-header">
          {/* Character Portrait */}
          <div className="character-portrait" title={`${unitClassId} — ${viewedName}`}>
            <HeroSprite
              classId={unitClassId}
              variant={viewedUnit?.sprite_variant || 1}
              size={28}
              grayscale={!isAlive}
              className="portrait-shape"
            />
          </div>
          <h3>
            {isViewingPartyMember ? `${viewedName}` : (viewedName || 'Character')}
          </h3>
          <span className="character-class-label">{unitClassId || 'Unknown'}</span>
          <button className="inventory-close-btn" onClick={onClose} title="Close (Esc / I)">X</button>
        </div>

        {/* Dungeon Context Strip */}
        {isDungeon && (
          <div className="dungeon-context-strip">
            <span className="context-item context-floor" title="Current dungeon floor">
              <span className="context-icon">▼</span> Floor {currentFloor || 1}
            </span>
            <span className="context-separator">·</span>
            <span className="context-item context-gold" title="Gold">
              <span className="context-icon">●</span> {gold ?? 0}g
              {(() => {
                const earned = (gold ?? 0) - (startGold ?? 0);
                return earned > 0 ? <span className="context-gold-earned" title="Gold earned this run"> (+{earned})</span> : null;
              })()}
            </span>
            <span className="context-separator">·</span>
            <span className="context-item context-kills" title="Enemies killed this run">
              <span className="context-icon">✕</span> {totalKills} Kills
            </span>
          </div>
        )}

        {/* Character Stats Section */}
        <div className="character-stats-section">
          {/* HP Bar — value inside */}
          <div className="character-hp-row">
            <span className="character-hp-label">HP</span>
            <div className="character-hp-bar-track">
              <div
                className={`character-hp-bar-fill ${hpPercent <= 25 ? 'hp-critical' : hpPercent <= 50 ? 'hp-low' : ''}`}
                style={{ width: `${hpPercent}%` }}
              />
              <span className="character-hp-bar-text">{unitHp} / {unitMaxHp}</span>
            </div>
          </div>

          {/* Core Stats Grid */}
          <div className="character-stat-grid">
            <div className="character-stat-row">
              <span className="stat-icon stat-melee">Melee</span>
              <span className="stat-value">{unitAttack}{equipBonuses.attack_damage > 0 ? <span className="stat-bonus"> (+{equipBonuses.attack_damage})</span> : ''}</span>
            </div>
            <div className="character-stat-row">
              <span className="stat-icon stat-ranged">Ranged</span>
              <span className="stat-value">{unitRanged}{equipBonuses.ranged_damage > 0 ? <span className="stat-bonus"> (+{equipBonuses.ranged_damage})</span> : ''}</span>
            </div>
            <div className="character-stat-row">
              <span className="stat-icon stat-armor">Armor</span>
              <span className="stat-value">{unitArmor}{equipBonuses.armor > 0 ? <span className="stat-bonus"> (+{equipBonuses.armor})</span> : ''}</span>
            </div>
            <div className="character-stat-row">
              <span className="stat-icon stat-vision">Vision</span>
              <span className="stat-value">{unitVision}</span>
            </div>
          </div>

          {/* Advanced Stats — Collapsible */}
          <button
            className={`advanced-stats-toggle ${showAdvancedStats ? 'expanded' : ''} ${hasAdvancedStats ? 'has-stats' : ''}`}
            onClick={() => setShowAdvancedStats(v => !v)}
          >
            <span className="toggle-arrow">{showAdvancedStats ? '▾' : '▸'}</span>
            Advanced Stats
            {hasAdvancedStats && <span className="advanced-stats-dot" />}
          </button>
          {showAdvancedStats && (
            <div className="advanced-stats-grid">
              <div className="adv-stat-row">
                <span className="adv-stat-label">Crit Chance</span>
                <span className="adv-stat-value">{Math.round(critChance * 100)}%</span>
              </div>
              <div className="adv-stat-row">
                <span className="adv-stat-label">Crit Damage</span>
                <span className="adv-stat-value">{Math.round(critDamage * 100)}%</span>
              </div>
              {dodgeChance > 0 && <div className="adv-stat-row">
                <span className="adv-stat-label">Dodge</span>
                <span className="adv-stat-value adv-stat-highlight">{Math.round(dodgeChance * 100)}%</span>
              </div>}
              {dmgReduction > 0 && <div className="adv-stat-row">
                <span className="adv-stat-label">Dmg Reduction</span>
                <span className="adv-stat-value adv-stat-highlight">{Math.round(dmgReduction * 100)}%</span>
              </div>}
              {armorPen > 0 && <div className="adv-stat-row">
                <span className="adv-stat-label">Armor Pen</span>
                <span className="adv-stat-value adv-stat-highlight">{armorPen}</span>
              </div>}
              {hpRegen > 0 && <div className="adv-stat-row">
                <span className="adv-stat-label">HP Regen</span>
                <span className="adv-stat-value adv-stat-highlight">+{hpRegen}/turn</span>
              </div>}
              {lifeOnHit > 0 && <div className="adv-stat-row">
                <span className="adv-stat-label">Life on Hit</span>
                <span className="adv-stat-value adv-stat-highlight">+{lifeOnHit}</span>
              </div>}
              {cdrPct > 0 && <div className="adv-stat-row">
                <span className="adv-stat-label">Cooldown Red.</span>
                <span className="adv-stat-value adv-stat-highlight">{Math.round(cdrPct * 100)}%</span>
              </div>}
              {skillDmg > 0 && <div className="adv-stat-row">
                <span className="adv-stat-label">Skill Damage</span>
                <span className="adv-stat-value adv-stat-highlight">+{Math.round(skillDmg * 100)}%</span>
              </div>}
              {thorns > 0 && <div className="adv-stat-row">
                <span className="adv-stat-label">Thorns</span>
                <span className="adv-stat-value adv-stat-highlight">{thorns}</span>
              </div>}
              {goldFind > 0 && <div className="adv-stat-row">
                <span className="adv-stat-label">Gold Find</span>
                <span className="adv-stat-value adv-stat-gold">+{Math.round(goldFind * 100)}%</span>
              </div>}
              {magicFind > 0 && <div className="adv-stat-row">
                <span className="adv-stat-label">Magic Find</span>
                <span className="adv-stat-value adv-stat-magic">+{Math.round(magicFind * 100)}%</span>
              </div>}
            </div>
          )}

          {/* Active Buffs — always rendered with fixed min-height to prevent layout shifts */}
          <div className="character-buffs-section">
            <span className="character-buffs-label">Buffs</span>
            <div className="character-buffs-list">
              {activeBuffs.length > 0 ? (
                activeBuffs.map((buff, i) => {
                  const pillClass = buff.type === 'dot' ? 'cbuff-dot'
                    : buff.type === 'hot' ? 'cbuff-hot'
                    : buff.type === 'shield_charges' ? 'cbuff-shield'
                    : buff.type === 'detection' ? 'cbuff-detection'
                    : buff.stat === 'armor' ? 'cbuff-armor' : 'cbuff-default';
                  const durationText = buff.type === 'shield_charges' ? `${buff.charges}ch` : `${buff.turns_remaining}t`;
                  return (
                    <span
                      key={`${buff.buff_id}-${i}`}
                      className={`character-buff-pill ${pillClass}`}
                      title={`${formatBuffName(buff.buff_id)}: ${formatBuffEffect(buff)}`}
                    >
                      {formatBuffName(buff.buff_id)} ({durationText})
                    </span>
                  );
                })
              ) : (
                <span className="character-buff-none">None</span>
              )}
            </div>
          </div>
        </div>

        <div className="character-divider" />

        {/* Equipment Slots */}
        <h4 className="inventory-section-label">Equipment</h4>
      <div className="equipment-slots-v2">
        {slots.map((slot) => {
          const item = viewEquipment[slot] || null;
          const rarity = item?.rarity || 'common';
          const setInfo = equipmentSetInfo[slot];
          return (
            <div
              key={slot}
              className={`equip-slot-v2 equip-slot-${slot} ${item ? `has-item rarity-${rarity}` : ''}`}
              onClick={() => item && handleUnequip(slot)}
              onMouseEnter={(e) => handleSlotMouseEnter(e, item, 'equipment', slot)}
              onMouseLeave={handleSlotMouseLeave}
              title={
                item
                  ? `${item.name} (click to unequip)`
                  : `${SLOT_LABELS[slot]} — empty`
              }
            >
              <div className="equip-slot-icon-area">
                <span className={`equip-slot-icon ${item ? `rarity-${rarity}` : ''}`}>{SLOT_ICONS[slot]}</span>
              </div>
              <div className="equip-slot-info">
                <span className="equip-slot-label">{SLOT_LABELS[slot]}</span>
                {item ? (
                  <span className={`equip-slot-item-name rarity-${rarity}`}>{item.name}</span>
                ) : (
                  <span className="equip-slot-empty">Empty</span>
                )}
              </div>
              {setInfo && (
                <span className="equip-set-badge" title={`${setInfo.setName} (${setInfo.equipped} equipped)`}>
                  <span className="set-badge-icon">◈</span>
                  <span className="set-badge-count">{setInfo.equipped}</span>
                </span>
              )}
              {item && <span className="equip-slot-unequip-hint">x</span>}
            </div>
          );
        })}
      </div>

      {/* Bag */}
      <div className="bag-header">
        <span>Bag</span>
        <div className="bag-header-right">
          <div className="bag-sort-controls">
            {SORT_MODES.map((mode) => (
              <button
                key={mode.key}
                className={`bag-sort-btn ${bagSortMode === mode.key ? 'sort-active' : ''}`}
                onClick={() => setBagSortMode(bagSortMode === mode.key ? null : mode.key)}
                title={`Sort by ${mode.label}${bagSortMode === mode.key ? ' (click to unsort)' : ''}`}
              >
                {mode.label}
              </button>
            ))}
          </div>
          <span className="bag-count">{viewInventory.length}/10</span>
        </div>
      </div>
      <div className="bag-grid">
        {Array.from({ length: 10 }, (_, i) => {
          // Use sorted order if sort mode is active
          const entry = sortedBag ? sortedBag[i] : null;
          const item = sortedBag ? (entry?.item || null) : (viewInventory[i] || null);
          const origIndex = sortedBag ? (entry?.origIndex ?? i) : i;
          const rarity = item?.rarity || 'common';
          const isConsumable = item?.item_type === 'consumable';
          const isEquippable = item?.item_type && item.item_type !== 'consumable';

          return (
            <div
              key={i}
              className={`bag-slot ${item ? `has-item rarity-${rarity}` : ''} ${isConsumable ? 'bag-slot-consumable' : ''}`}
              onMouseEnter={(e) => handleSlotMouseEnter(e, item, 'bag', i)}
              onMouseLeave={handleSlotMouseLeave}
            >
              {item ? (
                <div className="bag-slot-content">
                  <div
                    className="bag-slot-item-info"
                    onClick={() => {
                      if (!item || !isAlive) return;
                      if (isConsumable) {
                        handleUseItem(origIndex);
                      } else if (isEquippable) {
                        handleEquip(item);
                      }
                    }}
                    title={
                      isConsumable
                        ? `${item.name} (click to use)`
                        : `${item.name} (click to equip)`
                    }
                  >
                    <span className={`bag-item-type-badge badge-${item.item_type}`}>{ITEM_ICONS[item.item_type] || '?'}</span>
                    <span className={`bag-item-name rarity-${rarity}`}>{item.name}</span>
                  </div>
                  {isAlive && (
                    <div className="bag-slot-actions">
                      {canTransfer && (
                        <button
                          className="bag-transfer-btn"
                          onClick={(e) => {
                            e.stopPropagation();
                            setTransferItem({ index: origIndex, item });
                          }}
                          title="Transfer to another party member"
                        >
                          ↗
                        </button>
                      )}
                      <button
                        className={`bag-destroy-btn ${confirmDestroyId === (item.instance_id || item.item_id) ? 'destroy-confirm' : ''}`}
                        onClick={(e) => {
                          e.stopPropagation();
                          handleDestroyItem(item);
                        }}
                        title={confirmDestroyId === (item.instance_id || item.item_id) ? 'Click again to confirm destroy' : 'Destroy item'}
                      >
                        {confirmDestroyId === (item.instance_id || item.item_id) ? '✕' : '🗑'}
                      </button>
                    </div>
                  )}
                </div>
              ) : (
                <span className="bag-slot-empty">•</span>
              )}
            </div>
          );
        })}
      </div>

      {/* Transfer Modal */}
      {transferItem && (
        <div className="dungeon-transfer-modal-overlay" onClick={() => setTransferItem(null)}>
          <div className="dungeon-transfer-modal" onClick={(e) => e.stopPropagation()}>
            <h4 className="transfer-title">Transfer Item</h4>
            <p className="transfer-subtitle">
              Send <strong>{transferItem.item.name}</strong> to:
            </p>
            <div className="transfer-hero-list">
              {transferTargets.map((target) => {
                const isFull = target.bagCount >= 10;
                return (
                  <button
                    key={target.unit_id}
                    className={`transfer-hero-btn ${isFull ? 'transfer-hero-full' : ''}`}
                    onClick={() => !isFull && handleTransfer(target.unit_id)}
                    disabled={isFull}
                    title={isFull ? 'Inventory full' : `Transfer to ${target.username}`}
                  >
                    <span className="transfer-hero-icon">[T]</span>
                    <span className="transfer-hero-info">
                      <span className="transfer-hero-name">
                        {target.username}
                        {target.unit_id === playerId ? ' (You)' : ''}
                      </span>
                      <span className="transfer-hero-class">{target.class_id || 'Hero'}</span>
                    </span>
                    <span className={`transfer-hero-bag ${isFull ? 'bag-full' : ''}`}>
                      {target.bagCount}/10
                    </span>
                  </button>
                );
              })}
            </div>
            <button className="transfer-cancel-btn" onClick={() => setTransferItem(null)}>
              Cancel
            </button>
          </div>
        </div>
      )}
      </div>

      {/* Item Tooltip — rendered outside the scrollable panel to prevent layout shaking */}
      {hoveredItem && hoveredItem.item && (
        <ItemTooltip
          item={hoveredItem.item}
          equippedItem={
            // Phase 16G: Pass the equipped item in the same slot for comparison
            hoveredItem.source === 'bag' && hoveredItem.item.equip_slot
              ? viewEquipment[hoveredItem.item.equip_slot] || null
              : null
          }
          hint={
            isViewingPartyMember
              ? 'Viewing party member inventory'
              : hoveredItem.source === 'equipment'
              ? 'Click to unequip'
              : hoveredItem.item.item_type === 'consumable'
              ? 'Click to use'
              : 'Click to equip'
          }
          rect={hoveredItem.rect}
        />
      )}
    </div>
  );
}
