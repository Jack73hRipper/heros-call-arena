/**
 * Skill name/icon resolver for the Combat Meter breakdown view.
 *
 * Maps skill_id → { name, icon, type } for display purposes.
 * This is a client-side lookup table so we don't need to fetch configs at runtime.
 * Keep in sync with server/configs/skills_config.json when adding new skills.
 */

const SKILL_INFO = {
  // Auto attacks
  auto_attack_melee:  { name: 'Auto Attack',       icon: '⚔',  type: 'damage',  description: 'Basic melee attack. Pursue and strike an adjacent enemy.', cooldown: 0, range: 1, targeting: 'enemy_adjacent' },
  auto_attack_ranged: { name: 'Auto Attack',       icon: '🏹', type: 'damage',  description: 'Basic ranged attack. Pursue and shoot enemies within range.', cooldown: 0, range: 0, targeting: 'enemy_ranged' },

  // Confessor skills
  heal:               { name: 'Heal',              icon: '💚', type: 'heal',    description: 'Restore HP to yourself or a nearby ally.', cooldown: 4, range: 3, targeting: 'ally_or_self' },
  shield_of_faith:    { name: 'Shield of Faith',   icon: '✨', type: 'buff',    description: 'Grant an ally or self +5 armor for 3 turns.', cooldown: 5, range: 3, targeting: 'ally_or_self' },
  exorcism:           { name: 'Exorcism',          icon: '☀️', type: 'damage',  description: 'Deal 20 holy damage (40 vs Undead/Demons). 5-tile range.', cooldown: 4, range: 5, targeting: 'enemy_ranged' },
  prayer:             { name: 'Prayer',            icon: '🙏', type: 'heal',    description: 'Heal over time — restore 8 HP per turn for 4 turns (32 total) to self or ally.', cooldown: 6, range: 4, targeting: 'ally_or_self' },

  // Crusader skills
  taunt:              { name: 'Taunt',             icon: '🗣️', type: 'utility', description: 'Force all nearby enemies within 2 tiles to target you for 2 turns.', cooldown: 5, range: 2, targeting: 'self' },
  shield_bash:        { name: 'Shield Bash',       icon: '🛡️💥', type: 'damage', description: 'Slam an adjacent enemy with your shield — deals 0.7x melee damage and stuns for 1 turn.', cooldown: 4, range: 1, targeting: 'enemy_adjacent' },
  holy_ground:        { name: 'Holy Ground',       icon: '✝️', type: 'heal',    description: 'Consecrate the ground around you — heal all allies within 1 tile for 15 HP.', cooldown: 5, range: 1, targeting: 'self' },
  bulwark:            { name: 'Bulwark',           icon: '🏰', type: 'buff',    description: 'Brace yourself — gain +8 armor for 4 turns.', cooldown: 5, range: 0, targeting: 'self' },

  // Inquisitor skills
  power_shot:         { name: 'Power Shot',        icon: '🎯', type: 'damage',  description: 'A devastating ranged attack at 1.8x damage. Longer cooldown than normal ranged.', cooldown: 5, range: 0, targeting: 'enemy_ranged' },
  shadow_step:        { name: 'Shadow Step',       icon: '👤', type: 'utility', description: 'Teleport to a tile within 3 range (must be unoccupied, must have LOS).', cooldown: 4, range: 3, targeting: 'empty_tile' },
  divine_sense:       { name: 'Divine Sense',      icon: '👁️', type: 'utility', description: 'Reveal all Undead and Demon enemies within 12 tiles for 4 turns.', cooldown: 7, range: 0, targeting: 'self' },
  rebuke:             { name: 'Rebuke the Wicked', icon: '⚡', type: 'damage',  description: 'Deal 28 holy damage (42 vs Undead/Demons). 6-tile range.', cooldown: 5, range: 6, targeting: 'enemy_ranged' },

  // Ranger skills
  volley:             { name: 'Volley',            icon: '🏹🌧️', type: 'damage', description: 'Rain arrows on an area — deal 0.5x ranged damage to all enemies within 2 tiles of target.', cooldown: 5, range: 5, targeting: 'ground_aoe' },
  evasion:            { name: 'Evasion',           icon: '💨', type: 'buff',    description: 'Enter a defensive stance — dodge the next 2 attacks. Lasts up to 4 turns.', cooldown: 6, range: 0, targeting: 'self' },
  crippling_shot:     { name: 'Crippling Shot',    icon: '🦵🏹', type: 'damage', description: 'A precise shot that deals 0.8x ranged damage and slows the target for 2 turns (cannot move).', cooldown: 5, range: 0, targeting: 'enemy_ranged' },

  // Hexblade skills
  double_strike:      { name: 'Double Strike',     icon: '⚔️⚔️', type: 'damage', description: 'Strike an adjacent enemy twice at 60% damage each hit.', cooldown: 3, range: 1, targeting: 'enemy_adjacent' },
  wither:             { name: 'Wither',            icon: '🩸', type: 'damage',  description: 'Curse an enemy — deal 6 damage per turn for 4 turns (24 total). Cannot stack.', cooldown: 6, range: 3, targeting: 'enemy_ranged' },
  ward:               { name: 'Ward',              icon: '🛡️', type: 'buff',    description: 'Gain 3 charges. When attacked, attacker takes 8 reflected damage and 1 charge is consumed.', cooldown: 6, range: 0, targeting: 'self' },

  // Mage skills
  fireball:           { name: 'Fireball',          icon: '🔥', type: 'damage',  description: 'Hurl a bolt of fire — deal 2.0x ranged as magic damage (50% armor bypass). 5-tile range.', cooldown: 5, range: 5, targeting: 'enemy_ranged' },
  frost_nova:         { name: 'Frost Nova',        icon: '❄️', type: 'damage',  description: 'Blast frost around you — 12 magic damage + 2-turn slow to all enemies within 2 tiles.', cooldown: 6, range: 0, targeting: 'self' },
  arcane_barrage:     { name: 'Arcane Barrage',    icon: '✨', type: 'damage',  description: 'Rain arcane energy on an area — deal 1.0x ranged damage to all enemies within 1 tile of target.', cooldown: 5, range: 5, targeting: 'ground_aoe' },
  blink:              { name: 'Blink',             icon: '💫', type: 'utility', description: 'Teleport to an unoccupied tile within 4 range. Essential escape tool.', cooldown: 5, range: 4, targeting: 'empty_tile' },

  // Enemy skills
  war_cry:            { name: 'War Cry',           icon: '📯', type: 'buff',    description: 'Buff yourself — next melee attack deals 2x damage. Lasts 2 turns.', cooldown: 5, range: 0, targeting: 'self' },
  venom_gaze:         { name: 'Venom Gaze',        icon: '🐍', type: 'damage',  description: 'Fix your serpentine gaze on an enemy — deal 5 poison damage per turn for 3 turns (15 total).', cooldown: 5, range: 4, targeting: 'enemy_ranged' },
  soul_reap:          { name: 'Soul Reap',         icon: '💀', type: 'damage',  description: 'Rend an enemy\'s soul at range for 2.0x ranged damage. A devastating dark magic attack.', cooldown: 4, range: 4, targeting: 'enemy_ranged' },

  // Revenant skills
  grave_thorns:       { name: 'Grave Thorns',      icon: '🦴', type: 'buff',    description: 'Reflect 10 damage per hit received for 3 turns. Bone shards punish every attacker.', cooldown: 5, range: 0, targeting: 'self' },
  grave_chains:       { name: 'Grave Chains',      icon: '⛓️', type: 'utility', description: 'Taunt an enemy for 3 turns — spectral chains force them to attack you. Range 3.', cooldown: 5, range: 3, targeting: 'enemy_ranged' },
  undying_will:       { name: 'Undying Will',      icon: '💀', type: 'buff',    description: 'If you would die within 5 turns, revive at 30% HP instead. The signature cheat death.', cooldown: 10, range: 0, targeting: 'self' },
  soul_rend:          { name: 'Soul Rend',         icon: '⚔️', type: 'damage',  description: '1.2× melee damage + slow for 2 turns. Cursed blade tears at the soul.', cooldown: 5, range: 1, targeting: 'enemy_adjacent' },
};

/** Color per skill type — used for header accents and bar fills */
export const SKILL_TYPE_COLORS = {
  damage:  '#e04040',
  heal:    '#40cc40',
  buff:    '#4a8fd0',
  utility: '#c090e0',
};

/**
 * Look up display info for a skill.
 * Falls back to a formatted version of the ID if unknown.
 */
export function getSkillInfo(skillId) {
  if (SKILL_INFO[skillId]) return SKILL_INFO[skillId];

  // Fallback: convert snake_case to Title Case
  const name = skillId
    .split('_')
    .map(w => w.charAt(0).toUpperCase() + w.slice(1))
    .join(' ');

  return { name, icon: '❓', type: 'damage', description: null, cooldown: null, range: null, targeting: null };
}

export default SKILL_INFO;
