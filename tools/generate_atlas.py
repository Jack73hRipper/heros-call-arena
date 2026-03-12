"""
Generate a comprehensive sprite atlas JSON for mainlevbuild.png.
Maps, names, categorizes, and tags every occupied 16x16 cell.
Output format matches the Sprite Cataloger's expected import schema.
"""
from PIL import Image
import json, time

img = Image.open(r'c:\Users\xjobi\OneDrive\Desktop\MMO PROJECT\Arena\Assets\Walls and Objects\mainlevbuild.png')
W, H = img.size
CELL = 16
COLS = W // CELL  # 64
ROWS = H // CELL  # 40

# ── Build occupancy grid ─────────────────────────────────────────────────────
grid = {}
for row in range(ROWS):
    for col in range(COLS):
        x0, y0 = col * CELL, row * CELL
        region = img.crop((x0, y0, x0 + CELL, y0 + CELL))
        pixels = list(region.getdata())
        opaque = [p for p in pixels if p[3] > 10]
        if not opaque:
            continue
        avg_r = sum(p[0] for p in opaque) // len(opaque)
        avg_g = sum(p[1] for p in opaque) // len(opaque)
        avg_b = sum(p[2] for p in opaque) // len(opaque)
        coverage = len(opaque) / len(pixels)
        brightness = (avg_r + avg_g + avg_b) / 3
        grid[(row, col)] = {
            'r': avg_r, 'g': avg_g, 'b': avg_b,
            'coverage': round(coverage, 2),
            'brightness': round(brightness, 1)
        }

print(f"Found {len(grid)} occupied cells")

# ── Sprite data collector ────────────────────────────────────────────────────
sprites = {}
used = set()  # track which cells have been assigned
counter = [0]

def uid():
    counter[0] += 1
    return f"sprite_{counter[0]}_{int(time.time()*1000)}"

def add_sprite(name, row, col, category, tags=None, group=None, group_part=None):
    """Register one 16x16 sprite."""
    if (row, col) not in grid:
        return
    if (row, col) in used:
        return
    used.add((row, col))
    entry = {
        "id": uid(),
        "x": col * CELL,
        "y": row * CELL,
        "w": CELL,
        "h": CELL,
        "category": category,
        "row": row,
        "col": col,
    }
    if tags:
        entry["tags"] = tags
    if group:
        entry["group"] = group
    if group_part:
        entry["groupPart"] = group_part
    sprites[name] = entry


# ═══════════════════════════════════════════════════════════════════════════════
# REGION 1: WALL PANELS (Left side — 7 wall sections)
# ═══════════════════════════════════════════════════════════════════════════════
#
# Each wall panel set has:
#   - Top cap / parapet row(s) — partial coverage, lighter
#   - Face rows — full brick/stone texture
#   - Bottom edge row — partial coverage
#   - Stone column frames on left/right edges
#
# Wall material variants (based on color analysis):
#   A = Brick (rows 3-6)   — dark, brightness ~21
#   B = Cobble (rows 7-11) — medium, brightness ~38
#   C = Stone (rows 12-16) — medium, brightness ~38
#   D = Brick fragments (rows 17-19)
#   E = Moss_Stone (rows 21-24) — medium brightness ~36
#   F = Dark_Stone (rows 25-30) — medium brightness ~36
#   G = fragments (rows 31-33)

# --- Wall decorative top pieces (row 0-2, scattered) ---
deco_top_positions = [
    (0, 4), (0, 5), (0, 7), (0, 9), (0, 11), (0, 12), (0, 14), (0, 15),
    (1, 4), (1, 5), (1, 7), (1, 8), (1, 9), (1, 11), (1, 12), (1, 14), (1, 15),
    (2, 4), (2, 9), (2, 10), (2, 15),
]
for i, (r, c) in enumerate(deco_top_positions):
    if (r, c) in grid and (r, c) not in used:
        add_sprite(f"Wall_Top_Deco_{i+1}", r, c, "Wall_Top",
                   tags=["brick", "wall-accent", "top"])

# --- Wall Panel A: Brick (rows 3-6) ---
wall_a_rows = {
    3: "top",
    4: "upper",
    5: "lower",
    6: "base",
}
for r, part_label in wall_a_rows.items():
    n = 1
    for c in range(0, 20):
        if (r, c) in grid and (r, c) not in used:
            # Determine sub-type based on position
            if c <= 2 or c >= 17:
                sub = "Frame"
                cat = "Wall_Edge"
                tags = ["brick", "stone", "frame", part_label]
            else:
                sub = "Face"
                cat = "Wall_Face"
                tags = ["brick", part_label]
            add_sprite(f"Wall_Brick_{sub}_{part_label.title()}_{n}", r, c, cat, tags=tags,
                       group=f"Wall_Brick_Panel", group_part=f"r{r-3}c{c}")
            n += 1

# --- Wall Panel B: Cobble (rows 7-11) ---
wall_b_labels = {7: "top", 8: "upper", 9: "mid", 10: "lower", 11: "base"}
for r, part_label in wall_b_labels.items():
    n = 1
    for c in range(0, 20):
        if (r, c) in grid and (r, c) not in used:
            if c <= 2 or c >= 17:
                sub = "Frame"
                cat = "Wall_Edge"
                tags = ["cobble", "stone", "frame", part_label]
            else:
                sub = "Face"
                cat = "Wall_Face"
                tags = ["cobble", part_label]
            add_sprite(f"Wall_Cobble_{sub}_{part_label.title()}_{n}", r, c, cat, tags=tags,
                       group=f"Wall_Cobble_Panel", group_part=f"r{r-7}c{c}")
            n += 1

# --- Wall Panel C: Stone (rows 12-16) ---
wall_c_labels = {12: "top", 13: "upper", 14: "mid", 15: "lower", 16: "base"}
for r, part_label in wall_c_labels.items():
    n = 1
    for c in range(0, 20):
        if (r, c) in grid and (r, c) not in used:
            if c <= 4 or c >= 15:
                sub = "Frame"
                cat = "Wall_Edge"
                tags = ["stone", "frame", part_label]
            else:
                sub = "Face"
                cat = "Wall_Face"
                tags = ["stone", part_label]
            add_sprite(f"Wall_Stone_{sub}_{part_label.title()}_{n}", r, c, cat, tags=tags,
                       group=f"Wall_Stone_Panel", group_part=f"r{r-12}c{c}")
            n += 1

# --- Wall Small D: Brick fragments (rows 17-19, cols 5-20) ---
for r in range(17, 20):
    n = 1
    for c in range(0, 21):
        if (r, c) in grid and (r, c) not in used:
            label = ["top", "mid", "bot"][r - 17]
            add_sprite(f"Wall_Brick_Frag_{label.title()}_{n}", r, c, "Wall_Face",
                       tags=["brick", "fragment", label])
            n += 1

# --- Wall Panel E: Moss Stone (rows 21-24) ---
wall_e_labels = {21: "top", 22: "upper", 23: "lower", 24: "base"}
for r, part_label in wall_e_labels.items():
    n = 1
    for c in range(0, 20):
        if (r, c) in grid and (r, c) not in used:
            if c <= 2 or c >= 17:
                sub = "Frame"
                cat = "Wall_Edge"
                tags = ["moss", "stone", "frame", part_label]
            else:
                sub = "Face"
                cat = "Wall_Face"
                tags = ["moss", "stone", part_label]
            add_sprite(f"Wall_Moss_{sub}_{part_label.title()}_{n}", r, c, cat, tags=tags,
                       group=f"Wall_Moss_Panel", group_part=f"r{r-21}c{c}")
            n += 1

# --- Wall Panel F: Dark Stone (rows 25-30) ---
wall_f_labels = {25: "top", 26: "upper", 27: "mid_a", 28: "mid_b", 29: "lower", 30: "base"}
for r, part_label in wall_f_labels.items():
    n = 1
    for c in range(0, 20):
        if (r, c) in grid and (r, c) not in used:
            if c <= 4 or c >= 15:
                sub = "Frame"
                cat = "Wall_Edge"
                tags = ["dark-stone", "frame", part_label]
            else:
                sub = "Face"
                cat = "Wall_Face"
                tags = ["dark-stone", part_label]
            add_sprite(f"Wall_Dark_{sub}_{part_label.title()}_{n}", r, c, cat, tags=tags,
                       group=f"Wall_Dark_Panel", group_part=f"r{r-25}c{c}")
            n += 1

# --- Wall Small G: fragments (rows 31-33) ---
for r in range(31, 34):
    n = 1
    for c in range(0, 16):
        if (r, c) in grid and (r, c) not in used:
            label = ["top", "mid", "bot"][r - 31]
            add_sprite(f"Wall_Dark_Frag_{label.title()}_{n}", r, c, "Wall_Face",
                       tags=["dark-stone", "fragment", label])
            n += 1


# ═══════════════════════════════════════════════════════════════════════════════
# REGION 2: ARCHWAYS & GATES (Center-top)
# ═══════════════════════════════════════════════════════════════════════════════

# --- Stone Archway (cols 19-23, rows 1-11) — includes column extensions ---
for r in range(0, 12):
    for c in range(19, 24):
        if (r, c) in grid and (r, c) not in used:
            if r <= 1:
                part = "top"
            elif r >= 7:
                part = "column_ext"
            elif r >= 6:
                part = "base"
            else:
                if c == 19 or c == 23:
                    part = "pillar"
                elif c == 20 or c == 22:
                    part = "inner_edge"
                else:
                    part = "keystone"
            add_sprite(f"Arch_Stone_R{r}_C{c-19}", r, c, "Door",
                       tags=["stone", "arch", part],
                       group="Arch_Stone", group_part=f"r{r}c{c-19}")

# --- Gate / Portcullis (cols 25-29, rows 1-11) — includes column extensions ---
for r in range(0, 12):
    for c in range(25, 30):
        if (r, c) in grid and (r, c) not in used:
            if r <= 1:
                part = "top"
            elif r >= 7:
                part = "column_ext"
            elif c == 25 or c == 29:
                part = "pillar"
            else:
                part = "bars"
            add_sprite(f"Gate_Iron_R{r}_C{c-25}", r, c, "Door",
                       tags=["iron", "gate", "portcullis", part],
                       group="Gate_Iron", group_part=f"r{r}c{c-25}")


# ═══════════════════════════════════════════════════════════════════════════════
# REGION 3: LARGE GRATE / BARRED WINDOW (cols 32-39, rows 2-6)
# ═══════════════════════════════════════════════════════════════════════════════

for r in range(0, 8):
    for c in range(30, 40):
        if (r, c) in grid and (r, c) not in used:
            if r <= 2:
                part = "top"
            elif r >= 6:
                part = "base"
            else:
                part = "face"
            add_sprite(f"Window_Barred_R{r}_C{c-30}", r, c, "Door",
                       tags=["iron", "window", "barred", part],
                       group="Window_Barred", group_part=f"r{r}c{c-30}")


# ═══════════════════════════════════════════════════════════════════════════════
# REGION 4: STAIR / ENTRANCE STRUCTURES (Top-right)
# ═══════════════════════════════════════════════════════════════════════════════

# --- Stair Structure A (cols 40-44, rows 0-6) + shadow tiles below ---
for r in range(0, 7):
    for c in range(40, 45):
        if (r, c) in grid and (r, c) not in used:
            if r == 0:
                part = "top"
            elif r <= 2:
                part = "upper"
            elif r <= 4:
                part = "mid"
            else:
                part = "base"
            add_sprite(f"Stair_Stone_A_R{r}_C{c-40}", r, c, "Stair",
                       tags=["stone", "stair", "entrance", part],
                       group="Stair_Stone_A", group_part=f"r{r}c{c-40}")

# --- Central Arch/Gate elements (cols 45-53, rows 3-6) ---
for r in range(0, 7):
    for c in range(45, 54):
        if (r, c) in grid and (r, c) not in used:
            if c <= 47 or c >= 50:
                part = "pillar"
            else:
                part = "opening"
            add_sprite(f"Arch_Gate_Mid_R{r}_C{c-45}", r, c, "Door",
                       tags=["stone", "arch", "gate", part],
                       group="Arch_Gate_Mid", group_part=f"r{r}c{c-45}")

# --- Stair Structure B (cols 55-58, rows 0-6) ---
for r in range(0, 7):
    for c in range(55, 59):
        if (r, c) in grid and (r, c) not in used:
            if r == 0:
                part = "top"
            elif r <= 2:
                part = "upper"
            elif r <= 4:
                part = "mid"
            else:
                part = "base"
            add_sprite(f"Stair_Stone_B_R{r}_C{c-55}", r, c, "Stair",
                       tags=["stone", "stair", "entrance", part],
                       group="Stair_Stone_B", group_part=f"r{r}c{c-55}")


# ═══════════════════════════════════════════════════════════════════════════════
# REGION 5: PILLAR / COLUMN PIECES (rows 7-11, cols 40-46)
# ═══════════════════════════════════════════════════════════════════════════════

for r in range(7, 16):
    for c in range(40, 46):
        if (r, c) in grid and (r, c) not in used:
            idx = (r - 7) * 6 + (c - 40)
            if r <= 8:
                part = "top"
            elif r <= 11:
                part = "mid"
            else:
                part = "base"
            add_sprite(f"Column_Stone_{idx+1}", r, c, "Column",
                       tags=["stone", "column", "pillar", part])


# ═══════════════════════════════════════════════════════════════════════════════
# REGION 6: GRATE / METAL GRID (rows 8-11, cols 32-39)
# ═══════════════════════════════════════════════════════════════════════════════

for r in range(7, 12):
    for c in range(30, 40):
        if (r, c) in grid and (r, c) not in used:
            idx = (r - 7) * 10 + (c - 30) + 1
            add_sprite(f"Grate_Iron_{idx}", r, c, "Deco_Floor",
                       tags=["iron", "grate", "metal"])


# ═══════════════════════════════════════════════════════════════════════════════
# REGION 7: LARGE DECORATIVE OBJECTS (center area, rows 12-20)
# ═══════════════════════════════════════════════════════════════════════════════

# --- Block tiles / wall sections (cols 20-35, various rows) ---
for r in range(12, 25):
    for c in range(20, 36):
        if (r, c) in grid and (r, c) not in used:
            if r <= 16:
                variant = "A"
            elif r <= 19:
                variant = "B"
            else:
                variant = "C"
            add_sprite(f"Wall_Block_{variant}_R{r}_C{c}", r, c, "Wall_Accent",
                       tags=["stone", "block", "accent"])

# --- Large mosaic / decorative floor (cols 30-37, rows 12-20) ---
for r in range(12, 21):
    for c in range(30, 40):
        if (r, c) in grid and (r, c) not in used:
            # This area contains: large square tiles, round elements
            if r <= 16:
                sub = "Square"
            else:
                sub = "Round"
            idx = (r - 12) * 10 + (c - 30) + 1
            add_sprite(f"Deco_Floor_{sub}_{idx}", r, c, "Deco_Floor",
                       tags=["stone", "decorative", sub.lower()])


# ═══════════════════════════════════════════════════════════════════════════════
# REGION 8: FLOOR TILE GRID (Right side, cols 46-62, rows 13-24)
# ═══════════════════════════════════════════════════════════════════════════════
#
# 6 color columns × 5 variant rows = 30 floor tile groups (each 2×2 tiles)
# Color analysis:
#   Col A (46-47): Purple-brown  rgb ~(40,36,38)
#   Col B (49-50): Dark purple   rgb ~(36,31,33)  
#   Col C (52-53): Teal-green    rgb ~(35,42,41)
#   Col D (55-56): Dark green    rgb ~(32,37,35)
#   Col E (58-59): Yellow-green  rgb ~(36,40,34)
#   Col F (61-62): Olive-grey    rgb ~(33,36,32)

floor_color_names = {
    46: "Mauve",
    49: "Plum",
    52: "Teal",
    55: "Jade",
    58: "Olive",
    61: "Moss",
}

floor_row_groups = [
    (13, 14, "1"),
    (15, 16, "2"),
    (17, 18, "3"),
    (20, 21, "4"),
    (23, 24, "5"),
    (26, 27, "6"),
    (28, 29, "7"),
]

for base_col, color_name in floor_color_names.items():
    for (row_a, row_b, var_num) in floor_row_groups:
        group_name = f"Floor_{color_name}_{var_num}"
        positions = [
            (row_a, base_col, "tl"),
            (row_a, base_col + 1, "tr"),
            (row_b, base_col, "bl"),
            (row_b, base_col + 1, "br"),
        ]
        for r, c, part in positions:
            if (r, c) in grid and (r, c) not in used:
                add_sprite(f"Floor_{color_name}_{var_num}_{part.upper()}", r, c, "Floor_Stone",
                           tags=["floor", color_name.lower(), f"variant-{var_num}"],
                           group=group_name, group_part=part)


# ═══════════════════════════════════════════════════════════════════════════════
# REGION 9: LARGE FLOOR / PLATFORM TILES (cols 38-44, rows 16-22)
# ═══════════════════════════════════════════════════════════════════════════════

for r in range(16, 23):
    for c in range(38, 45):
        if (r, c) in grid and (r, c) not in used:
            if r <= 17:
                part = "top"
            elif r <= 19:
                part = "mid"
            else:
                part = "bot"
            idx = (r - 16) * 7 + (c - 38) + 1
            add_sprite(f"Platform_Stone_{idx}", r, c, "Floor_Stone",
                       tags=["stone", "platform", "dark", part])


# ═══════════════════════════════════════════════════════════════════════════════
# REGION 10: SMALL OBJECTS & ACCENTS (rows 25-33, cols ~20-50)
# ═══════════════════════════════════════════════════════════════════════════════

# Block sections cols 20-25 for rows 25+
for r in range(25, 34):
    for c in range(20, 30):
        if (r, c) in grid and (r, c) not in used:
            add_sprite(f"Wall_Accent_R{r}_C{c}", r, c, "Wall_Accent",
                       tags=["stone", "accent", "block"])

# Small objects cols 38-62 rows 23-30 (catches floor accent separators too)
for r in range(23, 31):
    for c in range(38, 62):
        if (r, c) in grid and (r, c) not in used:
            add_sprite(f"Deco_Small_R{r}_C{c}", r, c, "Deco_Floor",
                       tags=["stone", "decorative", "small"])


# ═══════════════════════════════════════════════════════════════════════════════
# REGION 11: REMAINING UNCATEGORIZED — catch any leftover occupied tiles
# ═══════════════════════════════════════════════════════════════════════════════

remaining = 0
for (r, c) in sorted(grid.keys()):
    if (r, c) not in used:
        remaining += 1
        add_sprite(f"Uncategorized_R{r}_C{c}", r, c, "Uncategorized",
                   tags=["unknown"])

print(f"Cataloged: {len(sprites)} sprites")
print(f"Remaining uncategorized: {remaining}")
print(f"Total occupied: {len(grid)}")

# ═══════════════════════════════════════════════════════════════════════════════
# BUILD ATLAS JSON
# ═══════════════════════════════════════════════════════════════════════════════

categories = sorted(set(s["category"] for s in sprites.values()))
# Ensure Uncategorized is always present and last
if "Uncategorized" in categories:
    categories.remove("Uncategorized")
categories.append("Uncategorized")

atlas = {
    "version": 1,
    "sheetFile": "mainlevbuild.png",
    "sheetWidth": W,
    "sheetHeight": H,
    "gridDefaults": {
        "cellW": CELL,
        "cellH": CELL,
        "offsetX": 0,
        "offsetY": 0,
        "spacingX": 0,
        "spacingY": 0
    },
    "categories": categories,
    "sprites": sprites,
    "animations": {}
}

# Save
output_path = r'c:\Users\xjobi\OneDrive\Desktop\MMO PROJECT\Arena\Assets\Walls and Objects\Json\mainlevbuild-atlas.json'
with open(output_path, 'w') as f:
    json.dump(atlas, f, indent=2)

print(f"\nAtlas saved to: {output_path}")
print(f"Categories: {categories}")

# Print category counts
cat_counts = {}
for s in sprites.values():
    cat = s["category"]
    cat_counts[cat] = cat_counts.get(cat, 0) + 1

print("\nCategory breakdown:")
for cat in categories:
    print(f"  {cat}: {cat_counts.get(cat, 0)} sprites")

# Print sample sprites from each category
print("\nSample sprites per category:")
for cat in categories:
    samples = [name for name, s in sprites.items() if s["category"] == cat][:3]
    print(f"  {cat}: {', '.join(samples)}")
