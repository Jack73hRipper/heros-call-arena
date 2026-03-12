/**
 * Grid Auto-Detection Utility
 *
 * Analyzes a sprite sheet image to detect the most likely grid cell dimensions.
 * Works by scanning for repeating patterns of transparency or uniform color rows/columns
 * which typically indicate cell boundaries.
 */

/**
 * Detect likely grid dimensions from a sprite sheet image.
 * @param {HTMLImageElement} img - loaded <img> element
 * @returns {{ cellW: number, cellH: number, offsetX: number, offsetY: number, spacingX: number, spacingY: number, confidence: number }}
 */
export function detectGrid(img) {
  const canvas = document.createElement('canvas');
  canvas.width = img.naturalWidth;
  canvas.height = img.naturalHeight;
  const ctx = canvas.getContext('2d');
  ctx.drawImage(img, 0, 0);
  const imageData = ctx.getImageData(0, 0, canvas.width, canvas.height);
  const { data, width, height } = imageData;

  // Scan each row and each column for "emptiness" (transparent or near-uniform)
  const rowScores = new Float32Array(height);
  const colScores = new Float32Array(width);

  // A row/col is "empty" if most pixels are transparent or very similar
  for (let y = 0; y < height; y++) {
    let transparentCount = 0;
    for (let x = 0; x < width; x++) {
      const idx = (y * width + x) * 4;
      if (data[idx + 3] < 20) transparentCount++; // alpha < 20 = transparent
    }
    rowScores[y] = transparentCount / width;
  }

  for (let x = 0; x < width; x++) {
    let transparentCount = 0;
    for (let y = 0; y < height; y++) {
      const idx = (y * width + x) * 4;
      if (data[idx + 3] < 20) transparentCount++;
    }
    colScores[x] = transparentCount / height;
  }

  // Find periodicity using autocorrelation on the empty-row/col signals
  const bestCellH = findPeriod(rowScores, height, 8, Math.min(256, Math.floor(height / 2)));
  const bestCellW = findPeriod(colScores, width, 8, Math.min(256, Math.floor(width / 2)));

  // Detect offset (first non-empty row/col)
  const offsetY = findFirstContent(rowScores, 0.8);
  const offsetX = findFirstContent(colScores, 0.8);

  // Detect spacing (look at the gap around detected boundaries)
  const spacingY = detectSpacing(rowScores, bestCellH, offsetY);
  const spacingX = detectSpacing(colScores, bestCellW, offsetX);

  // Confidence: how periodic is the signal?
  const confidence = Math.min(
    measurePeriodicity(rowScores, bestCellH, offsetY),
    measurePeriodicity(colScores, bestCellW, offsetX)
  );

  return {
    cellW: bestCellW || 32,
    cellH: bestCellH || 32,
    offsetX: offsetX || 0,
    offsetY: offsetY || 0,
    spacingX: spacingX || 0,
    spacingY: spacingY || 0,
    confidence: Math.round(confidence * 100),
  };
}

/**
 * Find the dominant period in a 1D signal using autocorrelation.
 */
function findPeriod(scores, length, minPeriod, maxPeriod) {
  let bestPeriod = 32;
  let bestScore = -Infinity;

  for (let period = minPeriod; period <= maxPeriod; period++) {
    let score = 0;
    let count = 0;
    for (let i = 0; i + period < length; i++) {
      // Correlation: how similar is scores[i] to scores[i + period]?
      score += scores[i] * scores[i + period];
      count++;
    }
    score /= count || 1;
    if (score > bestScore) {
      bestScore = score;
      bestPeriod = period;
    }
  }

  // Also try common sprite sizes and see which aligns best with empty rows/cols
  const commonSizes = [8, 16, 24, 32, 48, 64, 96, 128];
  for (const size of commonSizes) {
    if (size < minPeriod || size > maxPeriod) continue;
    let hits = 0;
    let total = 0;
    for (let pos = 0; pos < length; pos += size) {
      if (scores[pos] > 0.5) hits++;
      total++;
    }
    const hitRate = hits / (total || 1);
    // If a common size has >40% boundary hits, prefer it (cleaner grids)
    if (hitRate > 0.4 && size > 0) {
      // Weight common sizes
      const score = hitRate * 1.3;
      if (score > bestScore * 0.9) {
        bestPeriod = size;
        bestScore = score;
      }
    }
  }

  return bestPeriod;
}

/**
 * Find the first row/col that has content (not mostly transparent).
 */
function findFirstContent(scores, threshold) {
  for (let i = 0; i < scores.length; i++) {
    if (scores[i] < threshold) return i;
  }
  return 0;
}

/**
 * Detect spacing between cells by looking at gap width at boundary positions.
 */
function detectSpacing(scores, period, offset) {
  if (!period) return 0;
  const gapWidths = [];

  for (let pos = offset; pos < scores.length; pos += period) {
    // Count how many consecutive "empty" pixels around this boundary
    let gapWidth = 0;
    for (let d = -3; d <= 3; d++) {
      const idx = pos + d;
      if (idx >= 0 && idx < scores.length && scores[idx] > 0.7) {
        gapWidth++;
      }
    }
    if (gapWidth > 0) gapWidths.push(gapWidth);
  }

  if (gapWidths.length === 0) return 0;
  // Median gap width
  gapWidths.sort((a, b) => a - b);
  return gapWidths[Math.floor(gapWidths.length / 2)];
}

/**
 * Measure how periodic the signal is at a given period.
 * Returns 0-1 where 1 = perfectly periodic.
 */
function measurePeriodicity(scores, period, offset) {
  if (!period || period < 2) return 0;
  let matches = 0;
  let total = 0;

  for (let pos = offset; pos < scores.length; pos += period) {
    // Check if there's a high-transparency row/col at this position (±1 pixel)
    let found = false;
    for (let d = -1; d <= 1; d++) {
      const idx = pos + d;
      if (idx >= 0 && idx < scores.length && scores[idx] > 0.3) {
        found = true;
        break;
      }
    }
    if (found) matches++;
    total++;
  }

  return total > 0 ? matches / total : 0;
}

/**
 * Suggest multiple possible grid sizes by trying common sprite dimensions.
 * Returns sorted by likelihood.
 */
export function suggestGridSizes(img) {
  const canvas = document.createElement('canvas');
  canvas.width = img.naturalWidth;
  canvas.height = img.naturalHeight;
  const ctx = canvas.getContext('2d');
  ctx.drawImage(img, 0, 0);

  const w = img.naturalWidth;
  const h = img.naturalHeight;

  const commonSizes = [8, 16, 24, 32, 48, 64, 96, 128, 256];
  const suggestions = [];

  for (const cw of commonSizes) {
    for (const ch of commonSizes) {
      if (cw > w || ch > h) continue;
      const cols = Math.floor(w / cw);
      const rows = Math.floor(h / ch);
      if (cols < 1 || rows < 1) continue;
      // Score: prefer sizes that divide evenly
      const remainderX = w % cw;
      const remainderY = h % ch;
      const evenness = 1 - (remainderX / w + remainderY / h) / 2;
      suggestions.push({
        cellW: cw,
        cellH: ch,
        cols,
        rows,
        totalCells: cols * rows,
        evenness: Math.round(evenness * 100),
      });
    }
  }

  suggestions.sort((a, b) => b.evenness - a.evenness);
  return suggestions.slice(0, 15); // top 15 suggestions
}
