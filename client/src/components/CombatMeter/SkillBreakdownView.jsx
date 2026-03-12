import React, { useMemo, useState } from 'react';
import { createPortal } from 'react-dom';
import { getSkillInfo, SKILL_TYPE_COLORS } from './skillInfo';

/**
 * SkillBreakdownView — Per-skill detail panel for a single unit.
 *
 * Shown when a player row is clicked in any meter view.
 * Displays:
 *   - Sticky header with unit summary (name, class, totals)
 *   - Skill-by-skill table sorted by contribution (damage + healing combined)
 *   - Horizontal % bars showing each skill's share of total damage/healing
 *   - Per-skill: total damage, total healing, casts, avg per cast, best hit
 *   - Damage source breakdown (melee/ranged/skill/dot/reflect)
 *   - Healing source breakdown (skill/potion/hot)
 *   - Back button to return to the parent view
 */
export default function SkillBreakdownView({ unit, currentTurn, onBack }) {
  if (!unit) return null;

  const { skillRows, totalDamage, totalHealing } = useMemo(() => {
    const breakdown = unit.skill_breakdown || {};
    const rows = Object.entries(breakdown)
      .map(([skillId, data]) => {
        const info = getSkillInfo(skillId);
        const totalContrib = (data.damage || 0) + (data.heals || 0);
        const avgDmg = data.casts > 0 && data.damage > 0 ? (data.damage / data.casts) : 0;
        const avgHeal = data.casts > 0 && data.heals > 0 ? (data.heals / data.casts) : 0;
        return {
          skillId,
          name: info.name,
          icon: info.icon,
          type: info.type,
          damage: data.damage || 0,
          heals: data.heals || 0,
          casts: data.casts || 0,
          highestHit: data.highest_hit || 0,
          totalContrib,
          avgDmg,
          avgHeal,
        };
      })
      .filter(r => r.totalContrib > 0 || r.casts > 0)
      .sort((a, b) => b.totalContrib - a.totalContrib);

    const td = rows.reduce((sum, r) => sum + r.damage, 0);
    const th = rows.reduce((sum, r) => sum + r.heals, 0);
    return { skillRows: rows, totalDamage: td, totalHealing: th };
  }, [unit]);

  // Damage source breakdown from damage_by_type
  const damageByType = unit.damage_by_type || {};
  const dmgTypeEntries = useMemo(() => {
    const entries = [
      { label: 'Melee', value: damageByType.melee || 0, color: '#e04040' },
      { label: 'Ranged', value: damageByType.ranged || 0, color: '#40c040' },
      { label: 'Skill', value: damageByType.skill || 0, color: '#a050f0' },
      { label: 'DoT', value: damageByType.dot || 0, color: '#ff8844' },
      { label: 'Reflect', value: damageByType.reflect || 0, color: '#4a8fd0' },
    ].filter(e => e.value > 0);
    const total = entries.reduce((s, e) => s + e.value, 0);
    return entries.map(e => ({ ...e, pct: total > 0 ? (e.value / total) * 100 : 0 }));
  }, [damageByType]);

  // Healing source breakdown from healing_by_type
  const healByType = unit.healing_by_type || {};
  const healTypeEntries = useMemo(() => {
    const entries = [
      { label: 'Skill', value: healByType.skill || 0, color: '#40cc40' },
      { label: 'Potion', value: healByType.potion || 0, color: '#4a8fd0' },
      { label: 'HoT', value: healByType.hot || 0, color: '#88ffaa' },
    ].filter(e => e.value > 0);
    const total = entries.reduce((s, e) => s + e.value, 0);
    return entries.map(e => ({ ...e, pct: total > 0 ? (e.value / total) * 100 : 0 }));
  }, [healByType]);

  const dpt = currentTurn > 0 ? (unit.damage_dealt / currentTurn).toFixed(1) : '0.0';
  const hpt = currentTurn > 0 ? (unit.healing_done / currentTurn).toFixed(1) : '0.0';

  const maxSkillContrib = skillRows.length > 0 ? skillRows[0].totalContrib : 0;

  // Hover tooltip — tracks skill id + bounding rect for portal positioning
  const [hoveredSkill, setHoveredSkill] = useState(null); // { skillId, rect }

  const handleSkillMouseEnter = (skillId, e) => {
    const rect = e.currentTarget.getBoundingClientRect();
    setHoveredSkill({ skillId, rect });
  };

  const handleSkillMouseLeave = () => {
    setHoveredSkill(null);
  };

  return (
    <div className="skill-breakdown">
      {/* Back button */}
      <button className="skill-breakdown-back" onClick={onBack} title="Back (Esc)">
        ← Back
      </button>

      {/* Sticky unit summary header */}
      <div className="skill-breakdown-header">
        <span className="skill-breakdown-name">{unit.username}</span>
        {unit.classId && (
          <span className="skill-breakdown-class">{unit.classId}</span>
        )}
        <div className="skill-breakdown-totals">
          <span className="skill-breakdown-stat skill-breakdown-dmg">
            {unit.damage_dealt.toLocaleString()} dmg
            <small> ({dpt}/t)</small>
          </span>
          {unit.healing_done > 0 && (
            <span className="skill-breakdown-stat skill-breakdown-heal">
              {unit.healing_done.toLocaleString()} heal
              <small> ({hpt}/t)</small>
            </span>
          )}
          <span className="skill-breakdown-stat skill-breakdown-kills">
            {unit.kills} kill{unit.kills !== 1 ? 's' : ''}
          </span>
        </div>
      </div>

      {/* Skill-by-skill table */}
      {skillRows.length > 0 ? (
        <div className="skill-breakdown-skills">
          <div className="skill-breakdown-section-title">Ability Breakdown</div>
          <table className="meter-table skill-breakdown-table">
            <thead>
              <tr>
                <th>Ability</th>
                <th>Dmg</th>
                <th>Heal</th>
                <th>Casts</th>
                <th>Avg</th>
                <th>Best</th>
                <th>%</th>
              </tr>
            </thead>
            <tbody>
              {skillRows.map((row) => {
                const dmgPct = totalDamage > 0 ? ((row.damage / totalDamage) * 100).toFixed(1) : '—';
                const healPct = totalHealing > 0 ? ((row.heals / totalHealing) * 100).toFixed(1) : null;
                const barPct = maxSkillContrib > 0 ? (row.totalContrib / maxSkillContrib) * 100 : 0;
                const barColor = SKILL_TYPE_COLORS[row.type] || '#888';

                const info = getSkillInfo(row.skillId);
                const targetLabel = {
                  enemy_adjacent: 'Enemy (Melee)', enemy_ranged: 'Enemy (Ranged)',
                  ally_or_self: 'Ally or Self', self: 'Self',
                  empty_tile: 'Ground Target', ground_aoe: 'Ground (AoE)',
                }[info.targeting] || info.targeting || '';

                return (
                  <tr
                    key={row.skillId}
                    className="skill-breakdown-row"
                  >
                    <td className="skill-breakdown-ability">
                      <span
                        className="skill-breakdown-name-hover"
                        onMouseEnter={(e) => handleSkillMouseEnter(row.skillId, e)}
                        onMouseLeave={handleSkillMouseLeave}
                      >
                        <span className="skill-breakdown-icon">{row.icon}</span>
                        <span className="skill-breakdown-skill-name">{row.name}</span>
                      </span>
                      {/* % bar under the name */}
                      <div className="skill-breakdown-bar-track">
                        <div
                          className="skill-breakdown-bar-fill"
                          style={{ width: `${barPct}%`, backgroundColor: barColor }}
                        />
                      </div>
                    </td>
                    <td className="meter-val skill-col-dmg">
                      {row.damage > 0 ? row.damage.toLocaleString() : '—'}
                    </td>
                    <td className="meter-val skill-col-heal">
                      {row.heals > 0 ? row.heals.toLocaleString() : '—'}
                    </td>
                    <td className="meter-val skill-col-casts">{row.casts}</td>
                    <td className="meter-val skill-col-avg">
                      {row.avgDmg > 0
                        ? row.avgDmg.toFixed(1)
                        : row.avgHeal > 0
                          ? row.avgHeal.toFixed(1)
                          : '—'}
                    </td>
                    <td className="meter-val skill-col-best">
                      {row.highestHit > 0 ? row.highestHit : '—'}
                    </td>
                    <td className="meter-val skill-col-pct">
                      {row.damage > 0 ? `${dmgPct}%` : ''}
                      {row.damage > 0 && healPct ? ' / ' : ''}
                      {healPct ? `${healPct}%` : (row.damage === 0 ? '—' : '')}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="meter-empty">No ability data recorded</div>
      )}

      {/* Source type breakdowns */}
      <div className="skill-breakdown-sources">
        {/* Damage sources */}
        {dmgTypeEntries.length > 0 && (
          <div className="skill-breakdown-source-group">
            <div className="skill-breakdown-section-title">Damage Sources</div>
            <div className="skill-breakdown-source-bars">
              {dmgTypeEntries.map(e => (
                <div key={e.label} className="skill-breakdown-source-row">
                  <span className="skill-breakdown-source-label">{e.label}</span>
                  <div className="skill-breakdown-source-track">
                    <div
                      className="skill-breakdown-source-fill"
                      style={{ width: `${e.pct}%`, backgroundColor: e.color }}
                    />
                  </div>
                  <span className="skill-breakdown-source-val">
                    {e.value.toLocaleString()} ({e.pct.toFixed(0)}%)
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Healing sources */}
        {healTypeEntries.length > 0 && (
          <div className="skill-breakdown-source-group">
            <div className="skill-breakdown-section-title">Healing Sources</div>
            <div className="skill-breakdown-source-bars">
              {healTypeEntries.map(e => (
                <div key={e.label} className="skill-breakdown-source-row">
                  <span className="skill-breakdown-source-label">{e.label}</span>
                  <div className="skill-breakdown-source-track">
                    <div
                      className="skill-breakdown-source-fill"
                      style={{ width: `${e.pct}%`, backgroundColor: e.color }}
                    />
                  </div>
                  <span className="skill-breakdown-source-val">
                    {e.value.toLocaleString()} ({e.pct.toFixed(0)}%)
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Floating tooltip — rendered via portal so it escapes overflow containers */}
      {hoveredSkill && (() => {
        const info = getSkillInfo(hoveredSkill.skillId);
        if (!info.description) return null;
        const targetLabel = {
          enemy_adjacent: 'Enemy (Melee)', enemy_ranged: 'Enemy (Ranged)',
          ally_or_self: 'Ally or Self', self: 'Self',
          empty_tile: 'Ground Target', ground_aoe: 'Ground (AoE)',
        }[info.targeting] || info.targeting || '';
        return createPortal(
          <div
            className="meter-skill-tooltip-portal"
            style={{
              position: 'fixed',
              top: hoveredSkill.rect.bottom + 4,
              left: hoveredSkill.rect.left,
              zIndex: 99999,
            }}
          >
            <div className="skill-tooltip">
              <div className="skill-tooltip-name">{info.name}</div>
              <div className="skill-tooltip-type">
                {targetLabel}
                {info.range != null && info.range > 0 && ` · Range: ${info.range}`}
              </div>
              {info.cooldown != null && info.cooldown > 0 && (
                <div className="skill-tooltip-cooldown">
                  Cooldown: {info.cooldown} turns
                </div>
              )}
              <div className="skill-tooltip-desc">{info.description}</div>
            </div>
          </div>,
          document.body
        );
      })()}
    </div>
  );
}
