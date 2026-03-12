/**
 * Client-side A* Pathfinding — ported from server/app/core/ai_behavior.py
 *
 * Uses Chebyshev distance (8-directional diagonal movement).
 * Handles occupied tiles: if the goal is occupied (e.g. an enemy),
 * terminates when reaching any tile adjacent to the goal.
 */

/**
 * Chebyshev distance — allows diagonal movement at cost 1.
 */
function heuristic(ax, ay, bx, by) {
  return Math.max(Math.abs(ax - bx), Math.abs(ay - by));
}

/**
 * Return all 8-directional neighbors within bounds.
 */
function getNeighbors(x, y, gridW, gridH) {
  const result = [];
  for (let dx = -1; dx <= 1; dx++) {
    for (let dy = -1; dy <= 1; dy++) {
      if (dx === 0 && dy === 0) continue;
      const nx = x + dx;
      const ny = y + dy;
      if (nx >= 0 && nx < gridW && ny >= 0 && ny < gridH) {
        result.push([nx, ny]);
      }
    }
  }
  return result;
}

/**
 * Min-heap for A* open set.
 * Stores [priority, x, y] entries.
 */
class MinHeap {
  constructor() {
    this.data = [];
  }

  push(priority, x, y) {
    this.data.push([priority, x, y]);
    this._bubbleUp(this.data.length - 1);
  }

  pop() {
    const top = this.data[0];
    const last = this.data.pop();
    if (this.data.length > 0) {
      this.data[0] = last;
      this._sinkDown(0);
    }
    return top;
  }

  get length() {
    return this.data.length;
  }

  _bubbleUp(i) {
    while (i > 0) {
      const parent = (i - 1) >> 1;
      if (this.data[i][0] < this.data[parent][0]) {
        [this.data[i], this.data[parent]] = [this.data[parent], this.data[i]];
        i = parent;
      } else {
        break;
      }
    }
  }

  _sinkDown(i) {
    const n = this.data.length;
    while (true) {
      let smallest = i;
      const left = 2 * i + 1;
      const right = 2 * i + 2;
      if (left < n && this.data[left][0] < this.data[smallest][0]) smallest = left;
      if (right < n && this.data[right][0] < this.data[smallest][0]) smallest = right;
      if (smallest !== i) {
        [this.data[i], this.data[smallest]] = [this.data[smallest], this.data[i]];
        i = smallest;
      } else {
        break;
      }
    }
  }
}

/**
 * A* pathfinding from start to goal.
 *
 * Returns the full path as an array of [x, y] (excluding start),
 * or null if no path exists. Returns [] if start === goal.
 *
 * If the goal is in the occupied set, A* will path to an adjacent tile
 * instead of stepping onto the goal itself (for attacking enemies, interacting with doors, etc.).
 *
 * @param {number} startX - Start X coordinate
 * @param {number} startY - Start Y coordinate
 * @param {number} goalX - Goal X coordinate
 * @param {number} goalY - Goal Y coordinate
 * @param {number} gridWidth - Map width
 * @param {number} gridHeight - Map height
 * @param {Set<string>} obstacles - Set of "x,y" strings for impassable tiles
 * @param {Set<string>} occupied - Set of "x,y" strings for occupied tiles (units)
 * @param {Set<string>} [doorTiles] - Phase 7D-1: Set of "x,y" strings for closed-door tiles.
 *   These are excluded from the blocked set so A* can path through them, but at elevated
 *   traversal cost (+3 instead of +1). Makes A* prefer open routes but allows cross-room paths.
 * @returns {Array<[number, number]>|null} Path excluding start, or null if unreachable
 */
export function aStar(startX, startY, goalX, goalY, gridWidth, gridHeight, obstacles, occupied, doorTiles = null) {
  if (startX === goalX && startY === goalY) return [];

  const goalKey = `${goalX},${goalY}`;
  const goalIsOccupied = occupied.has(goalKey) || obstacles.has(goalKey);

  // Build combined blocked set (obstacles + occupied, minus goal if walkable)
  // Phase 7D-1: Remove door tiles from blocked so A* can path through them
  const blocked = new Set(obstacles);
  for (const occ of occupied) {
    if (occ !== goalKey) blocked.add(occ);
  }
  if (doorTiles) {
    for (const dk of doorTiles) {
      blocked.delete(dk);
    }
  }

  const openSet = new MinHeap();
  openSet.push(0, startX, startY);

  const cameFrom = new Map(); // "x,y" -> "px,py"
  const gScore = new Map();
  const startKey = `${startX},${startY}`;
  gScore.set(startKey, 0);

  while (openSet.length > 0) {
    const [, cx, cy] = openSet.pop();
    const currentKey = `${cx},${cy}`;

    // Check if we've reached the goal
    const reached =
      (cx === goalX && cy === goalY) ||
      (goalIsOccupied && heuristic(cx, cy, goalX, goalY) === 1);

    if (reached) {
      // Reconstruct path
      const path = [];
      let key = currentKey;
      while (cameFrom.has(key)) {
        const [px, py] = key.split(',').map(Number);
        path.push([px, py]);
        key = cameFrom.get(key);
      }
      path.reverse();
      return path;
    }

    for (const [nx, ny] of getNeighbors(cx, cy, gridWidth, gridHeight)) {
      const nbKey = `${nx},${ny}`;
      if (blocked.has(nbKey)) continue;
      // Don't step onto goal if it's occupied (stop adjacent)
      if (nbKey === goalKey && goalIsOccupied) continue;

      // Diagonal moves get a tiny extra cost so cardinal straight-line paths
      // are preferred over zigzag diagonals of the same Chebyshev length.
      // Phase 7D-1: Elevated cost (+3) for stepping through a closed door tile.
      const isDiagonal = (nx !== cx) && (ny !== cy);
      const baseCost = isDiagonal ? 1.001 : 1;
      const doorCost = (doorTiles && doorTiles.has(nbKey)) ? 3 : 0;
      const stepCost = baseCost + doorCost;
      const tentativeG = (gScore.get(currentKey) ?? Infinity) + stepCost;
      if (tentativeG < (gScore.get(nbKey) ?? Infinity)) {
        cameFrom.set(nbKey, currentKey);
        gScore.set(nbKey, tentativeG);
        const f = tentativeG + heuristic(nx, ny, goalX, goalY);
        openSet.push(f, nx, ny);
      }
    }
  }

  return null; // No path found
}

/**
 * Phase 7D-1: Build an action list from a path, inserting INTERACT actions
 * before any step that crosses a closed door tile.
 *
 * When A* plans a path through a closed door (because doorSet removed it
 * from the blocked set), this function detects those door crossings and
 * inserts INTERACT actions so the turn resolver opens the door (phase 1.5)
 * before the unit attempts to MOVE onto it (phase 2).
 *
 * Action sequence for a door crossing:
 *   [...MOVE, MOVE] → INTERACT(door_x, door_y) → MOVE(door_x, door_y) → [MOVE, MOVE...]
 *
 * @param {Array<[number, number]>} path - A* path (excluding start)
 * @param {Object} doorStates - Map of "x,y" -> "open"/"closed" (or null)
 * @param {number} maxActions - Maximum actions to generate
 * @returns {Array<{action_type: string, target_x: number, target_y: number}>}
 */
function _buildActionsWithDoorInteractions(path, doorStates, maxActions) {
  const actions = [];

  for (let i = 0; i < path.length && actions.length < maxActions; i++) {
    const [px, py] = path[i];
    const stepKey = `${px},${py}`;

    // Check if this step lands on a closed door
    if (doorStates && doorStates[stepKey] === 'closed') {
      // Insert INTERACT before the MOVE onto the door tile
      if (actions.length < maxActions) {
        actions.push({ action_type: 'interact', target_x: px, target_y: py });
      }
      // Then MOVE onto the (now-open) door tile
      if (actions.length < maxActions) {
        actions.push({ action_type: 'move', target_x: px, target_y: py });
      }
    } else {
      actions.push({ action_type: 'move', target_x: px, target_y: py });
    }
  }

  return actions;
}

/**
 * Generate a queue of actions from a right-click smart action.
 *
 * Determines intent from what's at the target tile and builds
 * the appropriate sequence of move + action commands.
 *
 * @param {number} startX - Player's current (or simulated) position X
 * @param {number} startY - Player's current (or simulated) position Y
 * @param {number} targetX - Clicked tile X
 * @param {number} targetY - Clicked tile Y
 * @param {number} gridWidth - Map width
 * @param {number} gridHeight - Map height
 * @param {Set<string>} obstacleSet - Impassable tiles
 * @param {Object} occupiedMap - Map of "x,y" -> occupant info
 * @param {Object} doorStates - Map of "x,y" -> "open"/"closed"
 * @param {Object} chestStates - Map of "x,y" -> "unopened"/"opened"
 * @param {Object} groundItems - Map of "x,y" -> [items]
 * @param {string} myTeam - Player's team
 * @param {string} playerId - Player's ID
 * @param {number} maxActions - Maximum actions to generate (queue limit)
 * @param {Set<string>} [friendlyUnitKeys] - Set of "x,y" strings for same-team units to exclude from pathfinding
 * @param {Map<string, string>} [pendingMoves] - Phase 7A-3: Map of "x,y" (current) -> "x,y" (target) for
 *   units with queued moves. Current positions are excluded from occupied set (will vacate),
 *   target positions are added (will be occupied). Enables movement prediction for group paths.
 * @param {Set<string>} [doorSet] - Phase 7D-1: Set of "x,y" strings for closed-door tiles.
 *   Passed to A* so it can path through doors at elevated cost. Also used for post-processing:
 *   when the path passes through a closed door, INTERACT actions are inserted before the step.
 * @param {number|null} [autoAttackRange] - If set to a value > 1, the unit has a ranged auto-attack.
 *   The path will be truncated to stop at this range instead of going adjacent, and the final
 *   melee attack action is omitted (auto-target handles the ranged attack on the server).
 * @returns {{ actions: Array, intent: string, path: Array }|null}
 *   actions: Array of { action_type, target_x, target_y }
 *   intent: 'move' | 'attack' | 'interact' | 'loot' | 'loot_chest'
 *   path: Array of [x,y] for preview rendering
 *   Returns null if target is unreachable or invalid
 */
export function generateSmartActions(
  startX, startY, targetX, targetY,
  gridWidth, gridHeight, obstacleSet, occupiedMap,
  doorStates, chestStates, groundItems,
  myTeam, playerId, maxActions = 10,
  friendlyUnitKeys = null,
  pendingMoves = null,
  doorSet = null,
  autoAttackRange = null
) {
  const targetKey = `${targetX},${targetY}`;

  // Build occupied set — exclude friendly units so allies don't block pathfinding
  // (Phase 7A-2: server batch resolver handles cooperative movement)
  // Phase 7A-3: Also apply pending move predictions — vacating positions are
  // excluded so subsequent units can path through tiles being left.
  // We do NOT add claimed target positions — the batch resolver handles
  // conflicts at resolution time, and adding them would break A* in hallways.
  const vacating = new Set();
  if (pendingMoves) {
    for (const fromKey of pendingMoves.keys()) {
      vacating.add(fromKey);
    }
  }

  const occupied = new Set();
  for (const key of Object.keys(occupiedMap)) {
    if (friendlyUnitKeys && friendlyUnitKeys.has(key)) continue;
    if (vacating.has(key)) continue; // Phase 7A-3: unit will vacate this tile
    occupied.add(key);
  }

  // --- Determine intent based on tile content ---

  // 1. Enemy on tile → attack intent
  const occupant = occupiedMap[targetKey];
  if (occupant && occupant.pid !== playerId && occupant.team !== myTeam) {
    // Attack intent: path toward enemy
    // Phase 7D-1: Pass doorSet so A* can route through closed doors to reach enemies in other rooms
    const path = aStar(startX, startY, targetX, targetY, gridWidth, gridHeight, obstacleSet, occupied, doorSet);
    if (path === null) return null; // Unreachable

    // Ranged auto-attack: truncate path to stop at auto-attack range instead of adjacent
    if (autoAttackRange && autoAttackRange > 1 && path.length > 0) {
      let truncateIndex = path.length; // default: use full path
      for (let i = 0; i < path.length; i++) {
        const [px, py] = path[i];
        const dist = Math.sqrt((px - targetX) ** 2 + (py - targetY) ** 2);
        if (dist <= autoAttackRange) {
          truncateIndex = i + 1; // include this step, stop here
          break;
        }
      }
      const truncatedPath = path.slice(0, truncateIndex);
      // Build movement-only actions (no final attack — auto-target handles ranged attack)
      const actions = _buildActionsWithDoorInteractions(truncatedPath, doorStates, maxActions);
      return { actions, intent: 'attack', path: truncatedPath };
    }

    // Melee auto-attack (default): path to adjacent + melee attack
    // Phase 7D-1: Insert INTERACT actions for door crossings, accounting for queue limit
    const actions = _buildActionsWithDoorInteractions(path, doorStates, maxActions - 1);

    // Only add attack if we have room in the queue
    if (actions.length < maxActions) {
      actions.push({ action_type: 'attack', target_x: targetX, target_y: targetY, target_id: occupant.pid });
    }

    return { actions, intent: 'attack', path };
  }

  // 2. Closed door → interact intent (path to adjacent + interact)
  //    This is when the player clicks DIRECTLY on a door tile — preserved as-is.
  if (doorStates && doorStates[targetKey] === 'closed') {
    // For direct door click, A* paths adjacent to the door (door is in obstacleSet
    // and also in occupied set via goalIsOccupied). No doorSet needed here — we
    // want to stop adjacent, not walk through.
    const path = aStar(startX, startY, targetX, targetY, gridWidth, gridHeight, obstacleSet, occupied);
    if (path === null) return null;

    // Phase 7D-1: Insert INTERACT for any intermediate doors on the way to this door
    const actions = _buildActionsWithDoorInteractions(path, doorStates, maxActions - 1);

    if (actions.length < maxActions) {
      actions.push({ action_type: 'interact', target_x: targetX, target_y: targetY });
    }

    return { actions, intent: 'interact', path };
  }

  // 3. Unopened chest → loot intent (path to adjacent + loot)
  if (chestStates && chestStates[targetKey] === 'unopened') {
    // Phase 7D-1: Pass doorSet so A* can route through doors to reach chests in other rooms
    const path = aStar(startX, startY, targetX, targetY, gridWidth, gridHeight, obstacleSet, occupied, doorSet);
    if (path === null) return null;

    const actions = _buildActionsWithDoorInteractions(path, doorStates, maxActions - 1);

    if (actions.length < maxActions) {
      actions.push({ action_type: 'loot', target_x: targetX, target_y: targetY });
    }

    return { actions, intent: 'loot_chest', path };
  }

  // 4. Ground items on tile → loot intent (path to tile + loot)
  if (groundItems && groundItems[targetKey] && groundItems[targetKey].length > 0) {
    // For ground items, we need to stand ON the tile, not adjacent
    // Phase 7D-1: Pass doorSet so A* can route through doors
    const path = aStar(startX, startY, targetX, targetY, gridWidth, gridHeight, obstacleSet, occupied, doorSet);
    if (path === null) return null;

    const actions = _buildActionsWithDoorInteractions(path, doorStates, maxActions - 1);

    if (actions.length < maxActions) {
      actions.push({ action_type: 'loot', target_x: targetX, target_y: targetY });
    }

    return { actions, intent: 'loot', path };
  }

  // 5. Empty walkable tile → move intent
  //    Phase 7D-1: Also handles tiles beyond closed doors. The target tile may
  //    be walkable but unreachable without going through a door. With doorSet,
  //    A* can plan a path through the door and post-processing inserts INTERACT.
  //    Check: target is either not in obstacleSet, OR it's a tile that becomes
  //    reachable when door-aware A* is used (target itself is not a door).
  if (!obstacleSet.has(targetKey) && !occupied.has(targetKey)) {
    const path = aStar(startX, startY, targetX, targetY, gridWidth, gridHeight, obstacleSet, occupied, doorSet);
    if (path === null) return null;

    // Phase 7D-1: Insert INTERACT actions for any door crossings in the path.
    // maxActions applies to the total including INTERACTs.
    const actions = _buildActionsWithDoorInteractions(path, doorStates, maxActions);

    return { actions, intent: 'move', path };
  }

  // 6. Clicked on obstacle, own unit, or invalid tile → no action
  return null;
}

/**
 * Phase 7A-3: Generate paths for multiple units with movement prediction.
 *
 * Computes paths sequentially — each unit's path accounts for the movement
 * intents of previously-computed units.  A unit that has been assigned a move
 * is recorded as "vacating" its current position and "claiming" its target,
 * so subsequent units can path through the tile being vacated.
 *
 * This is the client-side counterpart of the server's `run_ai_decisions()`
 * pending-moves tracking, and will be used by Phase 7B group right-click.
 *
 * @param {Array<{unitId: string, startX: number, startY: number, targetX: number, targetY: number}>} unitMoves
 *   Array of units to compute paths for, in priority order (leader first).
 * @param {number} gridWidth - Map width
 * @param {number} gridHeight - Map height
 * @param {Set<string>} obstacleSet - Impassable tiles
 * @param {Object} occupiedMap - Map of "x,y" -> occupant info
 * @param {Object} doorStates - Map of "x,y" -> "open"/"closed"
 * @param {Object} chestStates - Map of "x,y" -> "unopened"/"opened"
 * @param {Object} groundItems - Map of "x,y" -> [items]
 * @param {string} myTeam - Player's team
 * @param {string} playerId - Player's ID
 * @param {number} maxActions - Maximum actions per unit
 * @param {Set<string>} [friendlyUnitKeys] - Same-team units to exclude
 * @param {Set<string>} [doorSet] - Phase 7D-1: Closed-door tiles for door-aware A*
 * @returns {Array<{unitId: string, result: Object|null}>}
 *   Array of results, one per unit, each containing the unitId and
 *   the generateSmartActions result (or null if unreachable).
 */
export function generateGroupPaths(
  unitMoves,
  gridWidth, gridHeight, obstacleSet, occupiedMap,
  doorStates, chestStates, groundItems,
  myTeam, playerId, maxActions = 10,
  friendlyUnitKeys = null,
  doorSet = null
) {
  const results = [];
  // Track pending moves: Map<"x,y" (current), "x,y" (target)>
  const pendingMoves = new Map();

  for (const { unitId, startX, startY, targetX, targetY } of unitMoves) {
    const result = generateSmartActions(
      startX, startY, targetX, targetY,
      gridWidth, gridHeight, obstacleSet, occupiedMap,
      doorStates, chestStates, groundItems,
      myTeam, playerId, maxActions,
      friendlyUnitKeys,
      pendingMoves.size > 0 ? pendingMoves : null,
      doorSet
    );

    results.push({ unitId, result });

    // Record this unit's move intent for subsequent units' prediction
    if (result && result.intent === 'move' && result.path && result.path.length > 0) {
      const fromKey = `${startX},${startY}`;
      const firstStep = result.path[0];
      const toKey = `${firstStep[0]},${firstStep[1]}`;
      if (fromKey !== toKey) {
        pendingMoves.set(fromKey, toKey);
      }
    }
  }

  return results;
}
/**
 * Phase 7B-3: Spread destinations around a target tile using BFS.
 *
 * Starting from the target tile, performs a breadth-first search outward
 * to find N walkable tiles near the target. Used to assign destinations
 * to group-selected units when right-clicking.
 *
 * If the area is a hallway (1-tile wide), destinations will naturally
 * line up behind the target in single file.
 *
 * @param {number} targetX - Leader's destination tile X
 * @param {number} targetY - Leader's destination tile Y
 * @param {number} count - Number of additional tiles to find (excludes the target itself)
 * @param {number} gridWidth - Map width
 * @param {number} gridHeight - Map height
 * @param {Set<string>} obstacleSet - Impassable tiles
 * @param {Set<string>} reservedKeys - Already-claimed tile keys (e.g. leader's destination)
 * @param {Set<string>} [doorSet] - Phase 7D-1: Closed-door tiles to exclude from obstacles during BFS
 * @returns {Array<{x: number, y: number}>} - Up to `count` walkable tiles near the target
 */
export function spreadDestinations(targetX, targetY, count, gridWidth, gridHeight, obstacleSet, reservedKeys, doorSet = null) {
  if (count <= 0) return [];

  const results = [];
  const visited = new Set();
  const targetKey = `${targetX},${targetY}`;
  visited.add(targetKey);

  // Also mark reserved tiles as visited so we don't assign them
  for (const rk of reservedKeys) {
    visited.add(rk);
  }

  // BFS queue: start from the target tile
  const queue = [[targetX, targetY]];
  let head = 0;

  while (head < queue.length && results.length < count) {
    const [cx, cy] = queue[head++];

    // Explore 8-directional neighbors (prefer cardinal first for natural spreading)
    const neighbors = [];
    // Cardinal directions first (up, right, down, left)
    for (const [dx, dy] of [[0, -1], [1, 0], [0, 1], [-1, 0], [-1, -1], [1, -1], [1, 1], [-1, 1]]) {
      const nx = cx + dx;
      const ny = cy + dy;
      if (nx < 0 || nx >= gridWidth || ny < 0 || ny >= gridHeight) continue;
      const nk = `${nx},${ny}`;
      if (visited.has(nk)) continue;
      visited.add(nk);

      // Phase 7D-1: Allow BFS expansion through closed doors so group
      // destinations can be found in rooms beyond doors. Door tiles
      // themselves are not valid destinations (they're obstacles), but
      // BFS can pass through them to reach floor tiles on the other side.
      const isDoor = doorSet && doorSet.has(nk);
      const isBlocked = obstacleSet.has(nk) && !isDoor;

      if (!isBlocked) {
        // Don't assign door tiles as destinations — they're transitional
        if (!isDoor) {
          neighbors.push({ x: nx, y: ny });
        }
        queue.push([nx, ny]);
      }
    }

    // Add walkable neighbors as destinations
    for (const nb of neighbors) {
      if (results.length >= count) break;
      results.push(nb);
    }
  }

  return results;
}

/**
 * Phase 7B-3: Compute group right-click movement for multiple selected units.
 *
 * When multiple units are selected and the player right-clicks a tile:
 * 1. Determine the "leader" (player character if selected, else nearest unit to target)
 * 2. Assign the target tile to the leader
 * 3. Spread remaining units to nearby walkable tiles around the target (BFS)
 * 4. Compute individual paths via generateGroupPaths()
 *
 * @param {Array<string>} selectedUnitIds - All selected unit IDs
 * @param {string} playerId - Player's own ID
 * @param {number} targetX - Right-clicked tile X
 * @param {number} targetY - Right-clicked tile Y
 * @param {number} gridWidth - Map width
 * @param {number} gridHeight - Map height
 * @param {Set<string>} obstacleSet - Impassable tiles
 * @param {Object} occupiedMap - Map of "x,y" -> occupant info
 * @param {Object} doorStates - Map of "x,y" -> "open"/"closed"
 * @param {Object} chestStates - Map of "x,y" -> "unopened"/"opened"
 * @param {Object} groundItems - Map of "x,y" -> [items]
 * @param {string} myTeam - Player's team
 * @param {Object} players - All player states keyed by ID
 * @param {number} maxActions - Maximum actions per unit
 * @param {Set<string>} [friendlyUnitKeys] - Same-team units to exclude from pathfinding
 * @param {Set<string>} [doorSet] - Phase 7D-1: Closed-door tiles for door-aware A* and BFS spreading
 * @returns {Array<{unitId: string, result: Object|null}>|null}
 *   Array of per-unit path results, or null if no valid paths could be computed.
 */
export function computeGroupRightClick(
  selectedUnitIds, playerId,
  targetX, targetY,
  gridWidth, gridHeight, obstacleSet, occupiedMap,
  doorStates, chestStates, groundItems,
  myTeam, players, maxActions = 10,
  friendlyUnitKeys = null,
  doorSet = null
) {
  if (!selectedUnitIds || selectedUnitIds.length === 0) return null;

  // Filter to alive units with known positions
  const aliveUnits = selectedUnitIds.filter(uid => {
    const p = players[uid];
    return p && p.is_alive !== false && p.position;
  });
  if (aliveUnits.length === 0) return null;

  // Determine leader: prefer player character if selected, else nearest unit to target
  let leaderId;
  if (aliveUnits.includes(playerId)) {
    leaderId = playerId;
  } else {
    // Pick the unit nearest to the target
    let bestDist = Infinity;
    for (const uid of aliveUnits) {
      const p = players[uid];
      const dist = Math.max(Math.abs(p.position.x - targetX), Math.abs(p.position.y - targetY));
      if (dist < bestDist) {
        bestDist = dist;
        leaderId = uid;
      }
    }
  }

  // Separate leader from followers
  const followers = aliveUnits.filter(uid => uid !== leaderId);

  // Spread destinations for followers around the target
  // Phase 7D-1: Pass doorSet so BFS can find tiles in rooms beyond doors
  const reservedKeys = new Set([`${targetX},${targetY}`]);
  const spreadTiles = spreadDestinations(
    targetX, targetY, followers.length,
    gridWidth, gridHeight, obstacleSet, reservedKeys, doorSet
  );

  // Assign destinations: leader to target, followers to spread tiles (sorted by proximity)
  // Sort followers by distance to target so closest unit gets closest spread tile
  const followersByDist = [...followers].sort((a, b) => {
    const pa = players[a].position;
    const pb = players[b].position;
    const da = Math.max(Math.abs(pa.x - targetX), Math.abs(pa.y - targetY));
    const db = Math.max(Math.abs(pb.x - targetX), Math.abs(pb.y - targetY));
    return da - db;
  });

  // Build unitMoves array for generateGroupPaths (leader first)
  const leaderPos = players[leaderId].position;
  const unitMoves = [{
    unitId: leaderId,
    startX: leaderPos.x, startY: leaderPos.y,
    targetX, targetY,
  }];

  for (let i = 0; i < followersByDist.length; i++) {
    const uid = followersByDist[i];
    const pos = players[uid].position;
    if (i < spreadTiles.length) {
      unitMoves.push({
        unitId: uid,
        startX: pos.x, startY: pos.y,
        targetX: spreadTiles[i].x, targetY: spreadTiles[i].y,
      });
    }
    // If no spread tile available (map too constrained), skip this unit
  }

  // Compute all paths with movement prediction
  // Phase 7D-1: Pass doorSet for door-aware individual paths
  const results = generateGroupPaths(
    unitMoves,
    gridWidth, gridHeight, obstacleSet, occupiedMap,
    doorStates, chestStates, groundItems,
    myTeam, playerId, maxActions,
    friendlyUnitKeys,
    doorSet
  );

  // Check if at least the leader got a valid path
  const leaderResult = results.find(r => r.unitId === leaderId);
  if (!leaderResult || !leaderResult.result) return null;

  return results;
}

/**
 * Phase 7E-1: Compute hover path previews for all selected units.
 *
 * Returns per-unit path data for real-time rendering as the cursor moves.
 * For a single selected unit, computes one path via generateSmartActions.
 * For multi-selected units, reuses computeGroupRightClick to get group
 * paths with formation spreading.
 *
 * @param {string[]} selectedUnitIds - All currently selected unit IDs
 * @param {string} playerId - The player's own ID
 * @param {string} effectiveUnitId - Currently active unit (selected or self)
 * @param {number} targetX - Hovered tile X
 * @param {number} targetY - Hovered tile Y
 * @param {number} gridWidth - Map width
 * @param {number} gridHeight - Map height
 * @param {Set<string>} obstacleSet - Impassable tiles
 * @param {Object} occupiedMap - Map of "x,y" -> occupant info
 * @param {Object} doorStates - Map of "x,y" -> "open"/"closed"
 * @param {Object} chestStates - Map of "x,y" -> "unopened"/"opened"
 * @param {Object} groundItems - Map of "x,y" -> [items]
 * @param {string} myTeam - Player's team
 * @param {Object} players - All players/units keyed by ID
 * @param {number} maxActions - Queue limit
 * @param {Set<string>} [friendlyUnitKeys] - Same-team ally positions to exclude from blocking
 * @param {Set<string>} [doorSet] - Closed-door tiles for door-aware A*
 * @returns {Array<{unitId: string, path: Array, actions: Array, destTile: {x,y}|null, intent: string}>|null}
 */
export function computeHoverPreview(
  selectedUnitIds, playerId, effectiveUnitId,
  targetX, targetY,
  gridWidth, gridHeight, obstacleSet, occupiedMap,
  doorStates, chestStates, groundItems,
  myTeam, players, maxActions = 10,
  friendlyUnitKeys = null,
  doorSet = null
) {
  if (targetX == null || targetY == null) return null;

  const targetKey = `${targetX},${targetY}`;

  // Don't preview if target is a hard obstacle (not a door, not an enemy, not a chest)
  const isTargetDoor = doorStates && doorStates[targetKey] === 'closed';
  const isTargetChest = chestStates && chestStates[targetKey] === 'unopened';
  const occupant = occupiedMap[targetKey];
  const isTargetEnemy = occupant && occupant.pid !== playerId && occupant.team !== myTeam;
  if (obstacleSet.has(targetKey) && !isTargetDoor && !isTargetEnemy && !isTargetChest) return null;

  // Determine which units to preview paths for
  const unitsToPreview = (selectedUnitIds && selectedUnitIds.length > 0)
    ? selectedUnitIds
    : (effectiveUnitId ? [effectiveUnitId] : []);

  if (unitsToPreview.length === 0) return null;

  // Filter to alive units with known positions
  const aliveUnits = unitsToPreview.filter(uid => {
    const p = players[uid];
    return p && p.is_alive !== false && p.position;
  });
  if (aliveUnits.length === 0) return null;

  // --- Single unit preview ---
  if (aliveUnits.length === 1) {
    const uid = aliveUnits[0];
    const unit = players[uid];

    // Skip if unit is already at the target
    if (unit.position.x === targetX && unit.position.y === targetY) return null;

    const result = generateSmartActions(
      unit.position.x, unit.position.y,
      targetX, targetY,
      gridWidth, gridHeight, obstacleSet, occupiedMap,
      doorStates, chestStates, groundItems,
      myTeam, uid, maxActions,
      friendlyUnitKeys, null, doorSet
    );

    if (!result || !result.path || result.path.length === 0) return null;

    // Destination = last MOVE action target, or last path step
    let destTile = null;
    if (result.actions && result.actions.length > 0) {
      const lastMove = [...result.actions].reverse().find(a => a.action_type === 'move');
      if (lastMove) destTile = { x: lastMove.target_x, y: lastMove.target_y };
    }
    if (!destTile && result.path.length > 0) {
      const last = result.path[result.path.length - 1];
      destTile = { x: last[0], y: last[1] };
    }

    return [{
      unitId: uid,
      path: result.path,
      actions: result.actions || [],
      destTile,
      intent: result.intent,
    }];
  }

  // --- Multi-unit preview: use group right-click logic ---
  const groupResults = computeGroupRightClick(
    aliveUnits, playerId,
    targetX, targetY,
    gridWidth, gridHeight, obstacleSet, occupiedMap,
    doorStates, chestStates, groundItems,
    myTeam, players, maxActions,
    friendlyUnitKeys, doorSet
  );

  if (!groupResults) return null;

  return groupResults.map(({ unitId, result }) => {
    if (!result || !result.actions || result.actions.length === 0) return null;

    // Determine destination from last MOVE in actions
    let destTile = null;
    const lastMove = [...result.actions].reverse().find(a => a.action_type === 'move');
    if (lastMove) destTile = { x: lastMove.target_x, y: lastMove.target_y };
    if (!destTile && result.path && result.path.length > 0) {
      const last = result.path[result.path.length - 1];
      destTile = { x: last[0], y: last[1] };
    }

    return {
      unitId,
      path: result.path || [],
      actions: result.actions || [],
      destTile,
      intent: result.intent,
    };
  }).filter(Boolean);
}