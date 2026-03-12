"""
Maps Routes — List available maps, upload new maps from WFC Dungeon Lab.
Module library routes — Export/import canonical WFC module library.

Provides auto-discovery of map JSON files in server/configs/maps/,
eliminating the need to hardcode map lists on the client.
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter()

_maps_dir = Path(__file__).resolve().parent.parent.parent / "configs" / "maps"
_wfc_modules_dir = Path(__file__).resolve().parent.parent.parent / "configs" / "wfc-modules"


class MapInfo(BaseModel):
    """Summary info for a map, returned by the list endpoint."""
    id: str
    name: str
    width: int
    height: int
    map_type: str
    label: str  # Human-friendly label for dropdowns


def _build_label(data: dict, map_id: str) -> str:
    """Build a human-readable label like 'Open Arena 15×15' from map data."""
    name = data.get("name", map_id.replace("_", " ").title())
    w = data.get("width", "?")
    h = data.get("height", "?")
    return f"{name} {w}×{h}"


@router.get("/", response_model=list[MapInfo])
async def list_maps():
    """List all available maps by scanning configs/maps/*.json."""
    maps = []
    if not _maps_dir.exists():
        return maps

    for map_file in sorted(_maps_dir.glob("*.json")):
        try:
            with open(map_file, "r") as f:
                data = json.load(f)
            map_id = map_file.stem
            maps.append(MapInfo(
                id=map_id,
                name=data.get("name", map_id),
                width=data.get("width", 0),
                height=data.get("height", 0),
                map_type=data.get("map_type", "arena"),
                label=_build_label(data, map_id),
            ))
        except (json.JSONDecodeError, Exception) as e:
            # Skip malformed files
            print(f"[Maps] Skipping {map_file.name}: {e}")
            continue

    return maps


class MapUpload(BaseModel):
    """Payload for uploading a map from WFC Dungeon Lab."""
    map_data: dict
    filename: str | None = None  # Optional override; derived from map name if omitted


@router.post("/upload")
async def upload_map(payload: MapUpload):
    """Save a map JSON to server/configs/maps/. Used by WFC Dungeon Lab."""
    data = payload.map_data

    # Validate required fields
    if "width" not in data or "height" not in data:
        raise HTTPException(status_code=400, detail="Map must have width and height fields.")
    if "tiles" not in data and "obstacles" not in data:
        raise HTTPException(status_code=400, detail="Map must have tiles or obstacles.")

    # Derive filename
    if payload.filename:
        filename = payload.filename
    else:
        name = data.get("name", "wfc_dungeon")
        filename = re.sub(r'[^a-z0-9]+', '_', name.lower()).strip('_') + '.json'

    # Sanitize: only allow safe filename characters
    if not re.match(r'^[a-z0-9_]+\.json$', filename):
        raise HTTPException(status_code=400, detail=f"Invalid filename: {filename}")

    filepath = _maps_dir / filename
    map_id = filepath.stem

    # Write the file
    _maps_dir.mkdir(parents=True, exist_ok=True)
    with open(filepath, "w") as f:
        json.dump(data, f, indent=2)

    # Clear the map_loader cache so it picks up the new file
    from app.core.map_loader import _loaded_maps
    _loaded_maps.pop(map_id, None)

    return {
        "status": "ok",
        "map_id": map_id,
        "filename": filename,
        "label": _build_label(data, map_id),
    }


# ═══════════════════════════════════════════════════════════
# WFC Module Library endpoints
# ═══════════════════════════════════════════════════════════

@router.post("/wfc-modules/library")
async def upload_module_library(payload: dict):
    """Save a canonical module library JSON to server/configs/wfc-modules/library.json.

    Used by the WFC Dungeon Tool's "Export Library to Server" button.
    The server's ``presets.py`` will load this file on next generation.
    """
    # Validate required structure
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="Payload must be a JSON object")
    if "modules" not in payload:
        raise HTTPException(status_code=400, detail="Library must have a 'modules' key")

    modules = payload["modules"]
    if not isinstance(modules, list) or len(modules) == 0:
        raise HTTPException(status_code=400, detail="Library must have at least one module")

    version = payload.get("version", 1)
    if version < 2:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported library version {version} (need >= 2)",
        )

    # Validate each module has required fields
    required = {"id", "name", "tiles", "purpose", "width", "height"}
    for i, mod in enumerate(modules):
        if not isinstance(mod, dict):
            raise HTTPException(
                status_code=400,
                detail=f"Module at index {i} is not an object",
            )
        missing = required - mod.keys()
        if missing:
            raise HTTPException(
                status_code=400,
                detail=f"Module '{mod.get('id', f'index {i}')}' missing: {', '.join(missing)}",
            )

    # Write the file
    _wfc_modules_dir.mkdir(parents=True, exist_ok=True)
    library_path = _wfc_modules_dir / "library.json"
    with open(library_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)

    logger.info("WFC module library saved: %d modules → %s", len(modules), library_path)

    return {
        "status": "ok",
        "module_count": len(modules),
        "version": version,
        "filename": "library.json",
    }


@router.get("/wfc-modules/library")
async def get_module_library():
    """Return the current canonical module library JSON.

    Returns the library.json if it exists, otherwise exports the
    built-in presets in the canonical format.
    """
    library_path = _wfc_modules_dir / "library.json"
    if library_path.exists():
        try:
            with open(library_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Failed to read library.json: %s", exc)

    # Fallback: export builtins
    from app.core.wfc.presets import _BUILTIN_MODULES, _BUILTIN_SIZE_PRESETS
    return {
        "version": 2,
        "module_size": 8,
        "generated_from": "server/app/core/wfc/presets.py (builtin fallback)",
        "modules": _BUILTIN_MODULES,
        "size_presets": _BUILTIN_SIZE_PRESETS,
    }
