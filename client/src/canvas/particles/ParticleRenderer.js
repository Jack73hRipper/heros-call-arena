// ─────────────────────────────────────────────────────────
// ParticleRenderer.js — Canvas 2D drawing for particles
// Zero dependencies. Portable into game client.
// ─────────────────────────────────────────────────────────

/**
 * Renders an array of Particle objects to a Canvas 2D context.
 * Supports shapes: circle, square, triangle, star, line.
 * Supports blend modes via globalCompositeOperation.
 */
export class ParticleRenderer {
  /**
   * Draw all alive particles from an emitter to the canvas.
   * @param {CanvasRenderingContext2D} ctx
   * @param {Particle[]} particles - Array of Particle objects
   * @param {string} blendMode - Canvas composite operation
   */
  render(ctx, particles, blendMode = 'lighter') {
    if (particles.length === 0) return;

    ctx.save();
    ctx.globalCompositeOperation = blendMode;

    for (const p of particles) {
      if (!p.alive || p.alpha <= 0 || p.size <= 0) continue;

      // Draw trail first (behind the particle)
      if (p.trail && p.trail.length > 1) {
        this._drawTrail(ctx, p);
      }

      ctx.save();
      ctx.translate(p.x, p.y);
      ctx.rotate(p.rotation);
      ctx.globalAlpha = p.alpha;
      ctx.fillStyle = p.color;

      this._drawShape(ctx, p.shape, p.size);

      ctx.restore();
    }

    ctx.restore();
  }

  /**
   * Draw a single particle shape centered at (0,0).
   * @param {CanvasRenderingContext2D} ctx
   * @param {string} shape
   * @param {number} size - Radius or half-extent
   */
  _drawShape(ctx, shape, size) {
    switch (shape) {
      case 'square':
        ctx.fillRect(-size, -size, size * 2, size * 2);
        break;

      case 'triangle':
        ctx.beginPath();
        ctx.moveTo(0, -size);
        ctx.lineTo(-size * 0.866, size * 0.5);
        ctx.lineTo(size * 0.866, size * 0.5);
        ctx.closePath();
        ctx.fill();
        break;

      case 'star': {
        const spikes = 5;
        const outerR = size;
        const innerR = size * 0.4;
        ctx.beginPath();
        for (let i = 0; i < spikes * 2; i++) {
          const r = i % 2 === 0 ? outerR : innerR;
          const angle = (Math.PI / spikes) * i - Math.PI / 2;
          const px = Math.cos(angle) * r;
          const py = Math.sin(angle) * r;
          if (i === 0) ctx.moveTo(px, py);
          else ctx.lineTo(px, py);
        }
        ctx.closePath();
        ctx.fill();
        break;
      }

      case 'diamond': {
        // Elongated diamond — narrow and pointed, ideal for arrow/projectile heads
        const hw = size * 0.35; // half-width (narrow)
        const hl = size;        // half-length (long axis)
        ctx.beginPath();
        ctx.moveTo(hl, 0);        // sharp front tip
        ctx.lineTo(0, hw);        // upper side
        ctx.lineTo(-hl * 1.2, 0); // rear (slightly longer for a tail feel)
        ctx.lineTo(0, -hw);       // lower side
        ctx.closePath();
        ctx.fill();
        break;
      }

      case 'line':
        ctx.strokeStyle = ctx.fillStyle;
        ctx.lineWidth = Math.max(1, size * 0.3);
        ctx.beginPath();
        ctx.moveTo(-size, 0);
        ctx.lineTo(size, 0);
        ctx.stroke();
        break;

      case 'circle':
      default:
        ctx.beginPath();
        ctx.arc(0, 0, size, 0, Math.PI * 2);
        ctx.fill();
        break;
    }
  }

  /**
   * Draw a fading trail behind a particle.
   * @param {CanvasRenderingContext2D} ctx
   * @param {Particle} p
   */
  _drawTrail(ctx, p) {
    const trail = p.trail;
    if (trail.length < 2) return;

    ctx.save();
    ctx.strokeStyle = p.color;
    ctx.lineCap = 'round';

    for (let i = 1; i < trail.length; i++) {
      const t0 = trail[i - 1];
      const t1 = trail[i];
      const frac = i / trail.length;
      ctx.globalAlpha = frac * p.alpha * 0.5;
      ctx.lineWidth = Math.max(0.5, t1.size * 0.5 * frac);
      ctx.beginPath();
      ctx.moveTo(t0.x, t0.y);
      ctx.lineTo(t1.x, t1.y);
      ctx.stroke();
    }

    ctx.restore();
  }
}
