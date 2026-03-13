import React from 'react';
import { getSpriteRegion, SPRITESHEET_WIDTH, SPRITESHEET_HEIGHT, SPRITE_CELL_SIZE } from '../../canvas/SpriteLoader';

/**
 * HeroSprite — renders a hero's sprite from the spritesheet using CSS background positioning.
 *
 * Uses the same spritesheet.png as the canvas renderer but displays it inline
 * in React UI components (roster cards, hiring hall, merchant tabs, etc.).
 *
 * @param {string} classId - Hero class ID (crusader, confessor, etc.)
 * @param {number} [variant=1] - Sprite variant (1, 2, or 3)
 * @param {number} [size=32] - Display size in pixels
 * @param {boolean} [grayscale=false] - Apply grayscale filter (for fallen heroes)
 * @param {string} [className=''] - Additional CSS class names
 */
export default function HeroSprite({ classId, variant = 1, size = 32, grayscale = false, className = '' }) {
  const region = getSpriteRegion(classId, variant);

  if (!region) {
    // Fallback: colored circle if no sprite found
    return (
      <span
        className={`hero-sprite-fallback ${className}`}
        style={{
          display: 'inline-block',
          width: size,
          height: size,
          borderRadius: '50%',
          background: '#555',
        }}
      />
    );
  }

  // Scale factor: how much to shrink the 270px source cell to display size
  const scale = size / SPRITE_CELL_SIZE;
  const bgWidth = SPRITESHEET_WIDTH * scale;
  const bgHeight = SPRITESHEET_HEIGHT * scale;
  const bgX = -(region.x * scale);
  const bgY = -(region.y * scale);

  const spritesheetUrl = `${import.meta.env.BASE_URL}spritesheet.png`;

  return (
    <span
      className={`hero-sprite ${className}`}
      style={{
        display: 'inline-block',
        width: size,
        height: size,
        backgroundImage: `url(${spritesheetUrl})`,
        backgroundPosition: `${bgX}px ${bgY}px`,
        backgroundSize: `${bgWidth}px ${bgHeight}px`,
        backgroundRepeat: 'no-repeat',
        imageRendering: size >= 64 ? 'auto' : 'auto',
        filter: grayscale ? 'grayscale(100%) opacity(0.5)' : undefined,
        flexShrink: 0,
        borderRadius: size >= 64 ? 4 : 2,
      }}
      role="img"
      aria-label={`${classId} sprite`}
    />
  );
}
