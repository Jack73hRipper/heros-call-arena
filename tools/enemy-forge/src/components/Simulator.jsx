// ─────────────────────────────────────────────────────────
// Simulator.jsx — TTK Calculator & Encounter Simulator
// ─────────────────────────────────────────────────────────
// Simulates N encounters between a hero party and an enemy
// configuration, providing TTK, DPS, and danger statistics.

import React, { useState, useMemo, useCallback } from 'react';

const DEFAULT_HERO = { class_id: 'crusader', level: 1, gear_bonus_damage: 5, gear_bonus_armor: 3, gear_bonus_hp: 20 };

function getClassStats(classId, classes) {
  return classes?.classes?.[classId] || {
    base_hp: 100, base_melee_damage: 15, base_ranged_damage: 0,
    base_armor: 5, base_vision_range: 6, ranged_range: 1,
  };
}

function applyRarityScaling(enemy, rarity, championType, affixes, rarityConfig) {
  const tier = rarityConfig?.rarity_tiers?.[rarity];
  if (!tier || rarity === 'normal') return { ...enemy };

  let hp = enemy.base_hp;
  let melee = enemy.base_melee_damage;
  let ranged = enemy.base_ranged_damage;
  let armor = enemy.base_armor;

  // Rarity tier scaling
  if (tier.hp_multiplier) hp = Math.round(hp * tier.hp_multiplier);
  if (tier.damage_multiplier) {
    melee = Math.round(melee * tier.damage_multiplier);
    ranged = Math.round(ranged * tier.damage_multiplier);
  }
  if (tier.armor_bonus) armor += tier.armor_bonus;

  // Champion type bonuses
  if (championType && rarity === 'champion') {
    const ct = rarityConfig?.champion_types?.[championType];
    if (ct) {
      if (ct.damage_bonus) {
        melee = Math.round(melee * (1 + ct.damage_bonus));
        ranged = Math.round(ranged * (1 + ct.damage_bonus));
      }
      if (ct.hp_multiplier) hp = Math.round(hp * ct.hp_multiplier);
      if (ct.armor_bonus) armor += ct.armor_bonus;
    }
  }

  // Affix stat multipliers
  (affixes || []).forEach(affixId => {
    const affix = rarityConfig?.affixes?.[affixId];
    if (!affix) return;
    (affix.effects || []).forEach(eff => {
      if (eff.type === 'stat_multiplier') {
        if (eff.stat === 'attack_damage') {
          melee = Math.round(melee * eff.value);
          ranged = Math.round(ranged * eff.value);
        }
        if (eff.stat === 'armor') armor = Math.round(armor * eff.value);
      }
      if (eff.type === 'set_stat' && eff.stat === 'thorns') {
        // Thorns tracked but not HP/damage
      }
    });
  });

  return {
    ...enemy,
    base_hp: hp,
    base_melee_damage: melee,
    base_ranged_damage: ranged,
    base_armor: armor,
  };
}

/**
 * J4.1 — Resolve an enemy's class_id → skills with typed effect extraction.
 * Returns { skills: [...], effects: { enrage, boneShield, frenzyAura, darkPact, profaneWard } }
 */
function resolveEnemySkills(enemy, skillsConfig) {
  if (!enemy?.class_id || !skillsConfig?.class_skills) return { skills: [], effects: {} };
  const classSkillIds = skillsConfig.class_skills[enemy.class_id];
  if (!classSkillIds) return { skills: [], effects: {} };

  const resolved = classSkillIds
    .map(sid => skillsConfig.skills?.[sid])
    .filter(Boolean);

  const effects = {};
  for (const skill of resolved) {
    for (const eff of (skill.effects || [])) {
      if (eff.type === 'passive_enrage') {
        effects.enrage = { ...eff, skillId: skill.skill_id, cooldown: skill.cooldown_turns };
      }
      if (eff.type === 'damage_absorb') {
        effects.boneShield = { ...eff, skillId: skill.skill_id, cooldown: skill.cooldown_turns };
      }
      if (eff.type === 'passive_aura_ally_buff') {
        effects.frenzyAura = { ...eff, skillId: skill.skill_id };
      }
      if (eff.type === 'buff' && eff.stat === 'melee_damage_multiplier') {
        effects.darkPact = { ...eff, skillId: skill.skill_id, cooldown: skill.cooldown_turns };
      }
      if (eff.type === 'buff' && eff.stat === 'damage_reduction_pct') {
        effects.profaneWard = { ...eff, skillId: skill.skill_id, cooldown: skill.cooldown_turns };
      }
    }
  }

  return { skills: resolved, effects };
}

/**
 * Run a skill-aware combat simulation.
 * J4.2 Enrage, J4.3 Bone Shield, J4.4 Frenzy Aura (group),
 * J4.5-J4.7 Support Enemy (Dark Pact / Profane Ward), J4.8 Skill Impact
 */
function simulateEncounter(heroes, enemy, nTrials, options = {}) {
  const { enemyCount = 1, supportEnemy = null, skillsConfig = null } = options;

  const primarySkills = resolveEnemySkills(enemy, skillsConfig);
  const supportSkills = supportEnemy ? resolveEnemySkills(supportEnemy, skillsConfig) : null;

  // Frenzy aura: +value per other living ally of same type
  const frenzyBonus = (primarySkills.effects.frenzyAura && enemyCount > 1)
    ? primarySkills.effects.frenzyAura.value * (enemyCount - 1)
    : 0;

  const results = [];
  const agg = {
    enrageTriggerCount: 0, enrageTriggerTurnSum: 0,
    bsActiveTurnsSum: 0, bsAbsorbedSum: 0,
    dpUptimeSum: 0, dpBonusDmgSum: 0,
    pwUptimeSum: 0, pwReducedSum: 0,
    frenzyBonusDmgSum: 0, totalTurnsSum: 0,
  };

  for (let t = 0; t < nTrials; t++) {
    // ── Initialize enemy group ──
    const units = [];
    for (let e = 0; e < enemyCount; e++) {
      units.push({
        hp: enemy.base_hp, maxHp: enemy.base_hp,
        baseMelee: enemy.base_melee_damage,
        melee: enemy.base_melee_damage + frenzyBonus,
        armor: enemy.base_armor,
        enraged: false,
        shieldAbs: 0, shieldDur: 0, shieldCD: 0,
      });
    }

    // ── Initialize support enemy ──
    let sup = supportEnemy ? {
      hp: supportEnemy.base_hp,
      melee: supportEnemy.base_melee_damage || supportEnemy.base_ranged_damage || 0,
      armor: supportEnemy.base_armor,
      dpCD: 0, dpDur: 0, pwCD: 0, pwDur: 0,
    } : null;

    let heroesHp = heroes.map(h => h.hp);
    let turn = 0;
    const maxTurns = 100;

    // Per-trial trackers
    let tEnrageFired = false, tEnrageTurn = 0;
    let tBSActive = 0, tBSAbsorbed = 0;
    let tDPUp = 0, tDPBonus = 0;
    let tPWUp = 0, tPWReduced = 0;
    let tFrenzyBonus = 0;

    while (units.some(u => u.hp > 0) && heroesHp.some(hp => hp > 0) && turn < maxTurns) {
      turn++;

      // ── 1. Support buffs (before combat) ──
      if (sup && sup.hp > 0 && supportSkills) {
        const { darkPact, profaneWard } = supportSkills.effects;
        // Dark Pact cast
        if (darkPact && sup.dpCD <= 0 && sup.dpDur <= 0) {
          sup.dpDur = darkPact.duration_turns;
          sup.dpCD = darkPact.cooldown;
        }
        if (sup.dpDur > 0) { tDPUp++; sup.dpDur--; }
        if (sup.dpCD > 0) sup.dpCD--;
        // Profane Ward cast
        if (profaneWard && sup.pwCD <= 0 && sup.pwDur <= 0) {
          sup.pwDur = profaneWard.duration_turns;
          sup.pwCD = profaneWard.cooldown;
        }
        if (sup.pwDur > 0) { tPWUp++; sup.pwDur--; }
        if (sup.pwCD > 0) sup.pwCD--;
      }

      // ── 2. Bone Shield cast (each unit) ──
      const bsEff = primarySkills.effects.boneShield;
      if (bsEff) {
        units.forEach(u => {
          if (u.hp <= 0) return;
          if (u.shieldCD <= 0 && u.shieldAbs <= 0) {
            u.shieldAbs = bsEff.absorb_amount;
            u.shieldDur = bsEff.duration_turns;
            u.shieldCD = bsEff.cooldown;
          }
        });
      }

      // ── 3. Heroes attack (focus-fire first alive primary, then support) ──
      heroes.forEach((hero, i) => {
        if (heroesHp[i] <= 0) return;
        let targetUnit = null;
        let isPrimary = true;
        const pIdx = units.findIndex(u => u.hp > 0);
        if (pIdx >= 0) {
          targetUnit = units[pIdx];
        } else if (sup && sup.hp > 0) {
          targetUnit = sup;
          isPrimary = false;
        }
        if (!targetUnit) return;

        let dmg = Math.max(1, hero.damage - targetUnit.armor);

        // Profane Ward damage reduction on primary
        if (isPrimary && sup && sup.pwDur > 0 && supportSkills?.effects?.profaneWard) {
          const red = Math.round(dmg * supportSkills.effects.profaneWard.magnitude);
          tPWReduced += red;
          dmg = Math.max(1, dmg - red);
        }

        // Bone Shield absorb
        if (isPrimary && targetUnit.shieldAbs > 0) {
          const abs = Math.min(dmg, targetUnit.shieldAbs);
          targetUnit.shieldAbs -= abs;
          dmg = Math.max(0, dmg - abs);
          tBSAbsorbed += abs;
        }

        targetUnit.hp -= dmg;

        // Enrage check
        if (isPrimary && primarySkills.effects.enrage && !targetUnit.enraged && targetUnit.hp > 0) {
          if (targetUnit.hp / targetUnit.maxHp <= primarySkills.effects.enrage.hp_threshold) {
            targetUnit.enraged = true;
            targetUnit.melee = Math.round(targetUnit.melee * primarySkills.effects.enrage.damage_multiplier);
            if (!tEnrageFired) { tEnrageFired = true; tEnrageTurn = turn; }
          }
        }
      });

      if (!units.some(u => u.hp > 0) && (!sup || sup.hp <= 0)) break;

      // ── 4. Bone Shield duration tick ──
      if (bsEff) {
        units.forEach(u => {
          if (u.hp <= 0) return;
          if (u.shieldDur > 0) {
            u.shieldDur--;
            tBSActive++;
            if (u.shieldDur <= 0) u.shieldAbs = 0;
          }
          if (u.shieldCD > 0) u.shieldCD--;
        });
      }

      // ── 5. Enemies attack heroes ──
      const living = heroesHp.map((hp, i) => i).filter(i => heroesHp[i] > 0);
      if (living.length === 0) break;

      units.forEach(u => {
        if (u.hp <= 0) return;
        let eDmg = u.melee;
        // Dark Pact active buff
        if (sup && sup.dpDur > 0 && supportSkills?.effects?.darkPact) {
          const bonus = Math.round(eDmg * (supportSkills.effects.darkPact.magnitude - 1));
          eDmg += bonus;
          tDPBonus += bonus;
        }
        if (frenzyBonus > 0) tFrenzyBonus += frenzyBonus;
        const tgt = living[Math.floor(Math.random() * living.length)];
        heroesHp[tgt] -= Math.max(1, eDmg - heroes[tgt].armor);
      });

      // Support enemy attacks
      if (sup && sup.hp > 0) {
        const stillLiving = heroesHp.map((hp, i) => i).filter(i => heroesHp[i] > 0);
        if (stillLiving.length > 0) {
          const tgt = stillLiving[Math.floor(Math.random() * stillLiving.length)];
          heroesHp[tgt] -= Math.max(1, sup.melee - heroes[tgt].armor);
        }
      }
    }

    const anyAlive = units.some(u => u.hp > 0) || (sup && sup.hp > 0);
    results.push({
      turns: turn,
      enemyDead: !anyAlive,
      heroesAlive: heroesHp.filter(hp => hp > 0).length,
      totalHeroHpRemaining: heroesHp.reduce((s, hp) => s + Math.max(0, hp), 0),
    });

    // Accumulate skill metrics
    agg.totalTurnsSum += turn;
    if (tEnrageFired) { agg.enrageTriggerCount++; agg.enrageTriggerTurnSum += tEnrageTurn; }
    agg.bsActiveTurnsSum += tBSActive;
    agg.bsAbsorbedSum += tBSAbsorbed;
    agg.dpUptimeSum += tDPUp;
    agg.dpBonusDmgSum += tDPBonus;
    agg.pwUptimeSum += tPWUp;
    agg.pwReducedSum += tPWReduced;
    agg.frenzyBonusDmgSum += tFrenzyBonus;
  }

  // ── Aggregate ──
  const ttk = results.map(r => r.turns);
  const avgTtk = ttk.reduce((a, b) => a + b, 0) / ttk.length;
  const avgHeroHp = results.reduce((s, r) => s + r.totalHeroHpRemaining, 0) / results.length;
  const avgAlive = results.reduce((s, r) => s + r.heroesAlive, 0) / results.length;
  const wipeRate = results.filter(r => r.heroesAlive === 0).length / results.length;
  const killRate = results.filter(r => r.enemyDead).length / results.length;
  const dangerScore = Math.round((wipeRate * 100) + ((1 - (avgAlive / heroes.length)) * 50));

  // ── J4.8 Build skill impact metrics ──
  const n = nTrials;
  const skillImpact = {};

  if (primarySkills.effects.enrage) {
    const rate = agg.enrageTriggerCount / n;
    skillImpact.enrage = {
      icon: '🔥', name: 'Enrage', active: true,
      triggerRate: (rate * 100).toFixed(0),
      avgTriggerTurn: agg.enrageTriggerCount > 0
        ? (agg.enrageTriggerTurnSum / agg.enrageTriggerCount).toFixed(1) : '-',
      threshold: `${(primarySkills.effects.enrage.hp_threshold * 100).toFixed(0)}%`,
      multiplier: `${primarySkills.effects.enrage.damage_multiplier}×`,
      preDmg: enemy.base_melee_damage + frenzyBonus,
      postDmg: Math.round((enemy.base_melee_damage + frenzyBonus) * primarySkills.effects.enrage.damage_multiplier),
    };
  }

  if (primarySkills.effects.boneShield) {
    skillImpact.boneShield = {
      icon: '🦴', name: 'Bone Shield', active: true,
      avgActiveTurns: (agg.bsActiveTurnsSum / n).toFixed(1),
      avgAbsorbed: (agg.bsAbsorbedSum / n).toFixed(0),
      absorbAmount: primarySkills.effects.boneShield.absorb_amount,
      cooldown: primarySkills.effects.boneShield.cooldown,
    };
  }

  if (primarySkills.effects.frenzyAura && enemyCount > 1) {
    skillImpact.frenzyAura = {
      icon: '👹', name: 'Frenzy Aura', active: true,
      bonusPerUnit: frenzyBonus,
      enemyCount,
      baseDmg: enemy.base_melee_damage,
      buffedDmg: enemy.base_melee_damage + frenzyBonus,
      totalGroupDps: (enemy.base_melee_damage + frenzyBonus) * enemyCount,
    };
  }

  if (supportSkills?.effects?.darkPact) {
    const avgUp = agg.dpUptimeSum / n;
    const avgTotalT = agg.totalTurnsSum / n;
    skillImpact.darkPact = {
      icon: '🩸', name: 'Dark Pact', active: true,
      avgUptime: avgUp.toFixed(1),
      uptimePct: avgTotalT > 0 ? ((avgUp / avgTotalT) * 100).toFixed(0) : '0',
      avgBonusDmg: (agg.dpBonusDmgSum / n).toFixed(0),
      multiplier: `${supportSkills.effects.darkPact.magnitude}×`,
    };
  }

  if (supportSkills?.effects?.profaneWard) {
    const avgUp = agg.pwUptimeSum / n;
    const avgTotalT = agg.totalTurnsSum / n;
    skillImpact.profaneWard = {
      icon: '🛡️', name: 'Profane Ward', active: true,
      avgUptime: avgUp.toFixed(1),
      uptimePct: avgTotalT > 0 ? ((avgUp / avgTotalT) * 100).toFixed(0) : '0',
      avgReduced: (agg.pwReducedSum / n).toFixed(0),
      magnitude: `${(supportSkills.effects.profaneWard.magnitude * 100).toFixed(0)}%`,
    };
  }

  return {
    avgTtk: avgTtk.toFixed(1),
    avgHeroHp: avgHeroHp.toFixed(0),
    avgAlive: avgAlive.toFixed(1),
    wipeRate: (wipeRate * 100).toFixed(1),
    killRate: (killRate * 100).toFixed(1),
    dangerScore: Math.min(100, dangerScore),
    heroeDps: heroes.map((h) => ({
      classId: h.classId,
      dpsPerTurn: Math.max(1, h.damage - enemy.base_armor),
    })),
    skillImpact,
    hasSkills: Object.keys(skillImpact).length > 0,
  };
}

export default function Simulator({ enemies, rarity, classes, combat, skills, meta }) {
  const [partySize, setPartySize] = useState(3);
  const [heroConfigs, setHeroConfigs] = useState([
    { ...DEFAULT_HERO, class_id: 'crusader' },
    { ...DEFAULT_HERO, class_id: 'confessor' },
    { ...DEFAULT_HERO, class_id: 'ranger' },
  ]);
  const [enemyType, setEnemyType] = useState(Object.keys(enemies)[0] || 'demon');
  const [rarityTier, setRarityTier] = useState('normal');
  const [championType, setChampionType] = useState('berserker');
  const [selectedAffixes, setSelectedAffixes] = useState([]);
  const [numTrials, setNumTrials] = useState(200);
  const [result, setResult] = useState(null);
  const [batchResults, setBatchResults] = useState(null);
  const [enemyCount, setEnemyCount] = useState(1);
  const [supportEnemyType, setSupportEnemyType] = useState('');

  const enemyData = enemies[enemyType];
  const scaledEnemy = useMemo(() => {
    if (!enemyData) return null;
    return applyRarityScaling(enemyData, rarityTier, championType, selectedAffixes, rarity);
  }, [enemyData, rarityTier, championType, selectedAffixes, rarity]);

  const heroParty = useMemo(() => {
    return heroConfigs.slice(0, partySize).map(h => {
      const cs = getClassStats(h.class_id, classes);
      return {
        classId: h.class_id,
        hp: cs.base_hp + h.gear_bonus_hp,
        damage: cs.base_melee_damage + h.gear_bonus_damage + (cs.base_ranged_damage > cs.base_melee_damage ? cs.base_ranged_damage - cs.base_melee_damage : 0),
        armor: cs.base_armor + h.gear_bonus_armor,
      };
    });
  }, [heroConfigs, partySize, classes]);

  // Support enemy (resolved + normal-scaled)
  const supportEnemyData = useMemo(() => {
    if (!supportEnemyType || !enemies[supportEnemyType]) return null;
    return applyRarityScaling(enemies[supportEnemyType], 'normal', null, [], rarity);
  }, [supportEnemyType, enemies, rarity]);

  // Skill summary for the currently selected enemy
  const enemySkillInfo = useMemo(() => {
    if (!enemyData) return null;
    return resolveEnemySkills(enemyData, skills);
  }, [enemyData, skills]);

  // Enemies that provide support skills (dark_pact or profane_ward)
  const supportCandidates = useMemo(() => {
    const candidates = [];
    for (const [eid, e] of Object.entries(enemies)) {
      const info = resolveEnemySkills(e, skills);
      if (info.effects.darkPact || info.effects.profaneWard) {
        const labels = [];
        if (info.effects.darkPact) labels.push('Dark Pact');
        if (info.effects.profaneWard) labels.push('Profane Ward');
        candidates.push({ id: eid, name: e.name, label: labels.join(' + ') });
      }
    }
    return candidates;
  }, [enemies, skills]);

  const runSim = useCallback(() => {
    if (!scaledEnemy) return;
    const res = simulateEncounter(heroParty, scaledEnemy, numTrials, {
      enemyCount,
      supportEnemy: supportEnemyData,
      skillsConfig: skills,
    });
    setResult(res);
    setBatchResults(null);
  }, [heroParty, scaledEnemy, numTrials, enemyCount, supportEnemyData, skills]);

  const runBatchSim = useCallback(() => {
    const batch = [];
    const enemyIds = Object.keys(enemies);
    const tiers = ['normal', 'champion', 'rare'];
    for (const eid of enemyIds) {
      const e = enemies[eid];
      if (e.allow_rarity_upgrade === false && tiers.indexOf('champion') >= 0) continue;
      for (const tier of tiers) {
        if (tier !== 'normal' && e.allow_rarity_upgrade === false) continue;
        const scaled = applyRarityScaling(e, tier, tier === 'champion' ? 'berserker' : null, [], rarity);
        const res = simulateEncounter(heroParty, scaled, 50, { skillsConfig: skills });
        const skillInfo = resolveEnemySkills(e, skills);
        batch.push({
          enemyId: eid,
          enemyName: e.name,
          tier,
          hp: scaled.base_hp,
          damage: Math.max(scaled.base_melee_damage, scaled.base_ranged_damage),
          avgTtk: res.avgTtk,
          dangerScore: res.dangerScore,
          wipeRate: res.wipeRate,
          killRate: res.killRate,
          hasSkills: skillInfo.skills.length > 0,
          skillNames: skillInfo.skills.map(s => s.icon + ' ' + s.name).join(', '),
        });
      }
    }
    batch.sort((a, b) => b.dangerScore - a.dangerScore);
    setBatchResults(batch);
    setResult(null);
  }, [enemies, rarity, heroParty, skills]);

  const updateHero = (idx, field, value) => {
    const updated = [...heroConfigs];
    updated[idx] = { ...updated[idx], [field]: value };
    setHeroConfigs(updated);
  };

  return (
    <div className="sim-panel">
      {/* Controls */}
      <div className="sim-controls">
        <h3>⚔️ TTK Simulator</h3>

        {/* Party Config */}
        <div className="card mb-8">
          <h4>Party ({partySize} heroes)</h4>
          <div className="form-group">
            <label>Party Size</label>
            <input type="range" min="1" max="5" value={partySize} onChange={e => {
              const n = parseInt(e.target.value);
              setPartySize(n);
              while (heroConfigs.length < n) heroConfigs.push({ ...DEFAULT_HERO });
            }} />
            <span className="mono">{partySize}</span>
          </div>
          {heroConfigs.slice(0, partySize).map((h, i) => (
            <div key={i} className="hero-config-row">
              <select value={h.class_id} onChange={e => updateHero(i, 'class_id', e.target.value)}>
                {Object.keys(classes?.classes || {}).map(c => (
                  <option key={c} value={c}>{c}</option>
                ))}
              </select>
              <input type="number" value={h.gear_bonus_damage} onChange={e => updateHero(i, 'gear_bonus_damage', parseInt(e.target.value) || 0)} title="Gear +Damage" style={{ width: 50 }} />
              <input type="number" value={h.gear_bonus_armor} onChange={e => updateHero(i, 'gear_bonus_armor', parseInt(e.target.value) || 0)} title="Gear +Armor" style={{ width: 50 }} />
              <input type="number" value={h.gear_bonus_hp} onChange={e => updateHero(i, 'gear_bonus_hp', parseInt(e.target.value) || 0)} title="Gear +HP" style={{ width: 50 }} />
            </div>
          ))}
        </div>

        {/* Enemy Config */}
        <div className="card mb-8">
          <h4>Enemy</h4>
          <div className="form-group">
            <label>Type</label>
            <select value={enemyType} onChange={e => setEnemyType(e.target.value)}>
              {Object.entries(enemies).map(([id, e]) => (
                <option key={id} value={id}>{e.name} ({id})</option>
              ))}
            </select>
          </div>
          <div className="form-group">
            <label>Rarity</label>
            <select value={rarityTier} onChange={e => setRarityTier(e.target.value)}>
              <option value="normal">Normal</option>
              <option value="champion">Champion</option>
              <option value="rare">Rare</option>
            </select>
          </div>
          {rarityTier === 'champion' && (
            <div className="form-group">
              <label>Champion Type</label>
              <select value={championType} onChange={e => setChampionType(e.target.value)}>
                {Object.keys(rarity?.champion_types || {}).map(ct => (
                  <option key={ct} value={ct}>{ct}</option>
                ))}
              </select>
            </div>
          )}
          {rarityTier === 'rare' && (
            <div className="form-group">
              <label>Affixes (multi-select)</label>
              <div className="checkbox-group">
                {Object.keys(rarity?.affixes || {}).map(aid => (
                  <label key={aid}>
                    <input
                      type="checkbox"
                      checked={selectedAffixes.includes(aid)}
                      onChange={e => {
                        if (e.target.checked) setSelectedAffixes(prev => [...prev, aid]);
                        else setSelectedAffixes(prev => prev.filter(a => a !== aid));
                      }}
                    />
                    {rarity.affixes[aid].name}
                  </label>
                ))}
              </div>
            </div>
          )}
          {scaledEnemy && (
            <div className="stat-callout">
              <span>HP: <strong>{scaledEnemy.base_hp}</strong></span>
              <span>Melee: <strong>{scaledEnemy.base_melee_damage}</strong></span>
              <span>Ranged: <strong>{scaledEnemy.base_ranged_damage}</strong></span>
              <span>Armor: <strong>{scaledEnemy.base_armor}</strong></span>
            </div>
          )}
          {/* Skill summary for selected enemy */}
          {enemySkillInfo && enemySkillInfo.skills.length > 0 && (
            <div className="sim-skill-summary">
              {enemySkillInfo.skills.map(s => (
                <span key={s.skill_id} className="sim-skill-chip" title={s.description}>
                  {s.icon} {s.name}{s.is_passive ? ' [P]' : ''}
                </span>
              ))}
            </div>
          )}
        </div>

        {/* J4.4 — Group Simulation (Enemy Count) */}
        <div className="card mb-8">
          <h4>Group Simulation</h4>
          <div className="form-group">
            <label>Enemy Count</label>
            <input type="range" min="1" max="8" value={enemyCount} onChange={e => setEnemyCount(parseInt(e.target.value))} />
            <span className="mono">{enemyCount}</span>
          </div>
          {enemySkillInfo?.effects?.frenzyAura && enemyCount > 1 && (
            <div className="sim-aura-preview">
              <span className="text-dim">👹 Frenzy Aura: </span>
              <strong>+{enemySkillInfo.effects.frenzyAura.value * (enemyCount - 1)}</strong>
              <span className="text-dim"> dmg per {enemyData?.name || 'enemy'} ({enemyCount - 1} nearby)</span>
            </div>
          )}
        </div>

        {/* J4.5 — Support Enemy */}
        <div className="card mb-8">
          <h4>Support Enemy</h4>
          <div className="form-group">
            <label>Support</label>
            <select value={supportEnemyType} onChange={e => setSupportEnemyType(e.target.value)}>
              <option value="">(none — no support)</option>
              {supportCandidates.map(c => (
                <option key={c.id} value={c.id}>{c.name} — {c.label}</option>
              ))}
            </select>
          </div>
          {supportEnemyData && (
            <div className="stat-callout">
              <span>HP: <strong>{supportEnemyData.base_hp}</strong></span>
              <span>Melee: <strong>{supportEnemyData.base_melee_damage}</strong></span>
              <span>Armor: <strong>{supportEnemyData.base_armor}</strong></span>
            </div>
          )}
        </div>

        {/* Run Controls */}
        <div className="form-group">
          <label>Trials</label>
          <select value={numTrials} onChange={e => setNumTrials(parseInt(e.target.value))}>
            <option value="50">50</option>
            <option value="100">100</option>
            <option value="200">200</option>
            <option value="500">500</option>
            <option value="1000">1000</option>
          </select>
        </div>
        <button className="btn btn-primary" onClick={runSim} style={{ width: '100%', marginBottom: 8 }}>
          ⚔️ Simulate Encounter
        </button>
        <button className="btn btn-success" onClick={runBatchSim} style={{ width: '100%' }}>
          📊 Batch Simulate All
        </button>
      </div>

      {/* Results */}
      <div className="sim-results">
        {result && (
          <div className="card mb-8">
            <h4>
              Results: {scaledEnemy?.name || enemyType}
              <span style={{ color: meta?.rarity_colors?.[rarityTier] || '#fff', marginLeft: 8 }}>
                [{rarityTier}]
              </span>
            </h4>
            <div className="sim-stat-grid">
              <div className="sim-stat">
                <div className="sim-stat-label">Avg TTK</div>
                <div className="sim-stat-value">{result.avgTtk} turns</div>
              </div>
              <div className="sim-stat">
                <div className="sim-stat-label">Kill Rate</div>
                <div className="sim-stat-value" style={{ color: 'var(--success)' }}>{result.killRate}%</div>
              </div>
              <div className="sim-stat">
                <div className="sim-stat-label">Wipe Rate</div>
                <div className="sim-stat-value" style={{ color: parseFloat(result.wipeRate) > 20 ? 'var(--danger)' : 'var(--text)' }}>{result.wipeRate}%</div>
              </div>
              <div className="sim-stat">
                <div className="sim-stat-label">Avg Heroes Alive</div>
                <div className="sim-stat-value">{result.avgAlive} / {partySize}</div>
              </div>
              <div className="sim-stat">
                <div className="sim-stat-label">Avg Hero HP Left</div>
                <div className="sim-stat-value">{result.avgHeroHp}</div>
              </div>
              <div className="sim-stat">
                <div className="sim-stat-label">Danger Score</div>
                <div className="sim-stat-value" style={{
                  color: result.dangerScore > 60 ? 'var(--danger)' : result.dangerScore > 30 ? 'var(--warning)' : 'var(--success)'
                }}>
                  {result.dangerScore}/100
                </div>
              </div>
            </div>

            {/* DPS Breakdown */}
            <h4 style={{ marginTop: 16 }}>DPS per Hero</h4>
            <table className="data-table">
              <thead>
                <tr><th>Class</th><th>DPS/Turn</th></tr>
              </thead>
              <tbody>
                {(result.heroeDps || []).map((h, i) => (
                  <tr key={i}>
                    <td>{h.classId}</td>
                    <td className="mono">{h.dpsPerTurn}</td>
                  </tr>
                ))}
              </tbody>
            </table>

            {/* J4.8 — Skill Effects Impact */}
            {result.hasSkills && (
              <div className="sim-skill-impact">
                <h4 style={{ marginTop: 16 }}>Skill Effects Impact</h4>
                {result.skillImpact.enrage && (
                  <div className="skill-impact-row">
                    <span className="skill-impact-icon">{result.skillImpact.enrage.icon}</span>
                    <div className="skill-impact-detail">
                      <strong>{result.skillImpact.enrage.name}</strong>
                      <span className="text-dim"> triggered at turn {result.skillImpact.enrage.avgTriggerTurn} avg ({result.skillImpact.enrage.threshold} HP threshold)</span>
                      <div className="skill-impact-stat">
                        → Post-enrage DPS: {result.skillImpact.enrage.preDmg} → <strong style={{ color: 'var(--danger)' }}>{result.skillImpact.enrage.postDmg}</strong>/turn ({result.skillImpact.enrage.multiplier})
                      </div>
                      <div className="skill-impact-stat text-dim">Trigger rate: {result.skillImpact.enrage.triggerRate}% of fights</div>
                    </div>
                  </div>
                )}
                {result.skillImpact.boneShield && (
                  <div className="skill-impact-row">
                    <span className="skill-impact-icon">{result.skillImpact.boneShield.icon}</span>
                    <div className="skill-impact-detail">
                      <strong>{result.skillImpact.boneShield.name}</strong>
                      <span className="text-dim"> active {result.skillImpact.boneShield.avgActiveTurns} turns per fight avg</span>
                      <div className="skill-impact-stat">
                        → Damage absorbed: <strong style={{ color: 'var(--info)' }}>{result.skillImpact.boneShield.avgAbsorbed}</strong> avg ({result.skillImpact.boneShield.absorbAmount} per cast, {result.skillImpact.boneShield.cooldown}t CD)
                      </div>
                    </div>
                  </div>
                )}
                {result.skillImpact.frenzyAura && (
                  <div className="skill-impact-row">
                    <span className="skill-impact-icon">{result.skillImpact.frenzyAura.icon}</span>
                    <div className="skill-impact-detail">
                      <strong>{result.skillImpact.frenzyAura.name}</strong>
                      <span className="text-dim"> +{result.skillImpact.frenzyAura.bonusPerUnit} damage per unit ({result.skillImpact.frenzyAura.enemyCount - 1} nearby)</span>
                      <div className="skill-impact-stat">
                        → Per-unit DPS: {result.skillImpact.frenzyAura.baseDmg} → <strong style={{ color: 'var(--warning)' }}>{result.skillImpact.frenzyAura.buffedDmg}</strong>
                        &nbsp;| Group DPS: <strong style={{ color: 'var(--danger)' }}>{result.skillImpact.frenzyAura.totalGroupDps}</strong>/turn
                      </div>
                    </div>
                  </div>
                )}
                {result.skillImpact.darkPact && (
                  <div className="skill-impact-row">
                    <span className="skill-impact-icon">{result.skillImpact.darkPact.icon}</span>
                    <div className="skill-impact-detail">
                      <strong>{result.skillImpact.darkPact.name}</strong>
                      <span className="text-dim"> uptime: {result.skillImpact.darkPact.uptimePct}% of fight ({result.skillImpact.darkPact.avgUptime} turns)</span>
                      <div className="skill-impact-stat">
                        → Avg bonus damage: <strong style={{ color: 'var(--danger)' }}>+{result.skillImpact.darkPact.avgBonusDmg}</strong> per fight ({result.skillImpact.darkPact.multiplier} multiplier)
                      </div>
                    </div>
                  </div>
                )}
                {result.skillImpact.profaneWard && (
                  <div className="skill-impact-row">
                    <span className="skill-impact-icon">{result.skillImpact.profaneWard.icon}</span>
                    <div className="skill-impact-detail">
                      <strong>{result.skillImpact.profaneWard.name}</strong>
                      <span className="text-dim"> uptime: {result.skillImpact.profaneWard.uptimePct}% of fight ({result.skillImpact.profaneWard.avgUptime} turns)</span>
                      <div className="skill-impact-stat">
                        → Avg damage reduced: <strong style={{ color: 'var(--info)' }}>-{result.skillImpact.profaneWard.avgReduced}</strong> per fight ({result.skillImpact.profaneWard.magnitude} reduction)
                      </div>
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        )}

        {batchResults && (
          <div className="card">
            <h4>📊 Batch Results — All Enemies × Rarity Tiers</h4>
            <p className="text-dim" style={{ fontSize: 12 }}>
              {batchResults.length} combinations tested with {numTrials > 50 ? 50 : numTrials} trials each.
              Sorted by danger score (highest first).
            </p>
            <div style={{ maxHeight: 500, overflowY: 'auto' }}>
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Enemy</th>
                    <th>Tier</th>
                    <th>HP</th>
                    <th>Damage</th>
                    <th>Avg TTK</th>
                    <th>Kill %</th>
                    <th>Wipe %</th>
                    <th>Danger</th>
                    <th>Skills</th>
                  </tr>
                </thead>
                <tbody>
                  {batchResults.map((r, i) => (
                    <tr key={i}>
                      <td>{r.enemyName}</td>
                      <td style={{ color: meta?.rarity_colors?.[r.tier] || '#fff' }}>{r.tier}</td>
                      <td className="mono">{r.hp}</td>
                      <td className="mono">{r.damage}</td>
                      <td className="mono">{r.avgTtk}</td>
                      <td className="mono">{r.killRate}%</td>
                      <td className="mono" style={{ color: parseFloat(r.wipeRate) > 20 ? 'var(--danger)' : 'inherit' }}>{r.wipeRate}%</td>
                      <td className="mono" style={{
                        color: r.dangerScore > 60 ? 'var(--danger)' : r.dangerScore > 30 ? 'var(--warning)' : 'var(--success)'
                      }}>{r.dangerScore}</td>
                      <td className="text-dim" style={{ fontSize: 11 }}>{r.hasSkills ? r.skillNames : '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {!result && !batchResults && (
          <div className="empty-state">
            <h3>Configure & Run</h3>
            <p>Set up your party and enemy, then simulate encounters to see TTK and danger scores.</p>
          </div>
        )}
      </div>
    </div>
  );
}
