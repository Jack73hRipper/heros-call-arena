import React, { useEffect, useState, useRef } from 'react';
import {
  loadSkillIconSheet,
  hasSkillSprite,
  getSkillSpriteRegion,
  getSkillEmoji,
  getSkillIconImage,
  isSkillIconSheetLoaded,
} from './SkillIconMap';

/**
 * SkillIcon — Renders a skill icon from the sprite sheet, or falls back to emoji.
 *
 * Uses a hidden canvas to extract the sprite region and display it as an <img>.
 * This allows proper scaling and CSS styling of the icon within the action bar.
 *
 * Props:
 *   skillId  — skill_id from skills_config.json
 *   size     — icon display size in px (default: 40)
 *   emoji    — emoji fallback from skill config (optional override)
 */
export default function SkillIcon({ skillId, size = 40, emoji }) {
  const [dataUrl, setDataUrl] = useState(null);
  const canvasRef = useRef(null);

  useEffect(() => {
    if (!hasSkillSprite(skillId)) return;

    const extract = () => {
      const img = getSkillIconImage();
      if (!img) return;

      const region = getSkillSpriteRegion(skillId);
      if (!region) return;

      // Use an offscreen canvas to extract the sprite region
      const canvas = document.createElement('canvas');
      canvas.width = region.w;
      canvas.height = region.h;
      const ctx = canvas.getContext('2d');
      ctx.drawImage(img, region.x, region.y, region.w, region.h, 0, 0, region.w, region.h);
      setDataUrl(canvas.toDataURL());
    };

    if (isSkillIconSheetLoaded()) {
      extract();
    } else {
      loadSkillIconSheet().then(extract).catch(() => {});
    }
  }, [skillId]);

  // Sprite icon available → render as image
  if (dataUrl) {
    return (
      <img
        className="skill-icon-sprite"
        src={dataUrl}
        alt={skillId}
        width={size}
        height={size}
        draggable={false}
      />
    );
  }

  // Fallback to emoji (scaled up)
  const fallbackEmoji = emoji || getSkillEmoji(skillId);
  return (
    <span
      className="skill-icon-emoji"
      style={{ fontSize: `${Math.round(size * 0.65)}px`, lineHeight: 1 }}
    >
      {fallbackEmoji}
    </span>
  );
}
