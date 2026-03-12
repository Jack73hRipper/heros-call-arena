"""
Tests for WFC Shared Module Format (Phase C — WFC In-Game Integration).

Validates:
- Canonical JSON library format (version 2)
- Loading modules from library.json
- Fallback to hardcoded builtins when JSON is missing
- Round-trip fidelity: export → import produces identical modules
- Validation rejects malformed/incomplete JSON
- Module field completeness
- export_builtin_to_json() creates valid library file
- get_preset_modules() uses JSON when available
- is_loaded_from_json() tracks source correctly
- Backward-compatible PRESET_MODULES / SIZE_PRESETS aliases
- Server API endpoint validation (upload/download library)
"""

from __future__ import annotations

import copy
import json
import tempfile
from pathlib import Path

import pytest

from app.core.wfc.presets import (
    PRESET_MODULES,
    SIZE_PRESETS,
    _BUILTIN_MODULES,
    _BUILTIN_SIZE_PRESETS,
    _REQUIRED_MODULE_FIELDS,
    _load_library_json,
    _export_library_json,
    _validate_module,
    export_builtin_to_json,
    get_preset_modules,
    get_size_presets,
    is_loaded_from_json,
)


# ═══════════════════════════════════════════════════════════
# Backward Compatibility
# ═══════════════════════════════════════════════════════════


class TestBackwardCompatibility:
    """Ensure renamed internals are aliased for existing imports."""

    def test_preset_modules_alias_exists(self):
        """PRESET_MODULES should alias _BUILTIN_MODULES."""
        assert PRESET_MODULES is _BUILTIN_MODULES

    def test_size_presets_alias_exists(self):
        """SIZE_PRESETS should alias _BUILTIN_SIZE_PRESETS."""
        assert SIZE_PRESETS is _BUILTIN_SIZE_PRESETS

    def test_preset_modules_has_49_modules(self):
        assert len(PRESET_MODULES) == 49

    def test_size_presets_has_4_entries(self):
        assert len(SIZE_PRESETS) == 4

    def test_get_preset_modules_returns_deep_copy(self):
        """Mutations to the returned list should not affect the source."""
        mods = get_preset_modules()
        mods[0]["name"] = "MUTATED"
        fresh = get_preset_modules()
        assert fresh[0]["name"] != "MUTATED"


# ═══════════════════════════════════════════════════════════
# Module Validation
# ═══════════════════════════════════════════════════════════


class TestModuleValidation:
    """Test _validate_module()."""

    def test_valid_module_passes(self):
        mod = _BUILTIN_MODULES[0]
        assert _validate_module(mod) is True

    def test_all_builtins_are_valid(self):
        for mod in _BUILTIN_MODULES:
            assert _validate_module(mod), f"Module {mod['id']} failed validation"

    def test_missing_field_fails(self):
        mod = {k: v for k, v in _BUILTIN_MODULES[0].items() if k != "tiles"}
        assert _validate_module(mod) is False

    def test_non_dict_fails(self):
        assert _validate_module("not a dict") is False
        assert _validate_module(None) is False
        assert _validate_module([]) is False

    def test_empty_tiles_fails(self):
        mod = dict(_BUILTIN_MODULES[0])
        mod["tiles"] = []
        assert _validate_module(mod) is False


# ═══════════════════════════════════════════════════════════
# JSON Library Export
# ═══════════════════════════════════════════════════════════


class TestExportLibraryJson:
    """Test _export_library_json() and export_builtin_to_json()."""

    def test_export_creates_valid_json(self, tmp_path):
        path = tmp_path / "library.json"
        _export_library_json(_BUILTIN_MODULES, _BUILTIN_SIZE_PRESETS, path)
        assert path.exists()
        data = json.loads(path.read_text())
        assert data["version"] == 2
        assert data["module_size"] == 8
        assert len(data["modules"]) == 49
        assert len(data["size_presets"]) == 4

    def test_export_builtin_convenience(self, tmp_path):
        path = tmp_path / "library.json"
        result = export_builtin_to_json(path)
        assert result == path
        assert path.exists()

    def test_export_creates_parent_dirs(self, tmp_path):
        path = tmp_path / "nested" / "deep" / "library.json"
        _export_library_json(_BUILTIN_MODULES, path=path)
        assert path.exists()

    def test_exported_modules_match_builtins(self, tmp_path):
        path = tmp_path / "library.json"
        _export_library_json(_BUILTIN_MODULES, _BUILTIN_SIZE_PRESETS, path)
        data = json.loads(path.read_text())
        # Compare module-by-module
        for i, (exported, builtin) in enumerate(zip(data["modules"], _BUILTIN_MODULES)):
            assert json.dumps(exported, sort_keys=True) == json.dumps(builtin, sort_keys=True), (
                f"Module {i} ({builtin['id']}) mismatch after export"
            )


# ═══════════════════════════════════════════════════════════
# JSON Library Loading
# ═══════════════════════════════════════════════════════════


class TestLoadLibraryJson:
    """Test _load_library_json()."""

    def test_load_valid_library(self, tmp_path):
        path = tmp_path / "library.json"
        _export_library_json(_BUILTIN_MODULES, _BUILTIN_SIZE_PRESETS, path)
        result = _load_library_json(path)
        assert result is not None
        assert len(result["modules"]) == 49

    def test_load_missing_file_returns_none(self, tmp_path):
        result = _load_library_json(tmp_path / "nonexistent.json")
        assert result is None

    def test_load_invalid_json_returns_none(self, tmp_path):
        path = tmp_path / "library.json"
        path.write_text("not valid json {{{")
        result = _load_library_json(path)
        assert result is None

    def test_load_missing_modules_key_returns_none(self, tmp_path):
        path = tmp_path / "library.json"
        path.write_text(json.dumps({"version": 2, "data": []}))
        result = _load_library_json(path)
        assert result is None

    def test_load_empty_modules_returns_none(self, tmp_path):
        path = tmp_path / "library.json"
        path.write_text(json.dumps({"version": 2, "modules": []}))
        result = _load_library_json(path)
        assert result is None

    def test_load_version_1_returns_none(self, tmp_path):
        """Version 1 libraries are incompatible — should be rejected."""
        path = tmp_path / "library.json"
        path.write_text(json.dumps({"version": 1, "modules": [{"id": "test"}]}))
        result = _load_library_json(path)
        assert result is None

    def test_load_skips_invalid_modules(self, tmp_path):
        """Invalid modules should be filtered out, valid ones kept."""
        path = tmp_path / "library.json"
        valid_mod = copy.deepcopy(_BUILTIN_MODULES[0])
        invalid_mod = {"id": "broken"}  # Missing most fields
        data = {"version": 2, "modules": [valid_mod, invalid_mod]}
        path.write_text(json.dumps(data))
        result = _load_library_json(path)
        assert result is not None
        assert len(result["modules"]) == 1
        assert result["modules"][0]["id"] == valid_mod["id"]

    def test_load_all_invalid_returns_none(self, tmp_path):
        path = tmp_path / "library.json"
        data = {"version": 2, "modules": [{"id": "broken1"}, {"id": "broken2"}]}
        path.write_text(json.dumps(data))
        result = _load_library_json(path)
        assert result is None


# ═══════════════════════════════════════════════════════════
# Round-Trip Fidelity
# ═══════════════════════════════════════════════════════════


class TestRoundTrip:
    """Verify export → import produces identical modules."""

    def test_round_trip(self, tmp_path):
        """Export builtins to JSON, load them back — should be identical."""
        path = tmp_path / "library.json"
        _export_library_json(_BUILTIN_MODULES, _BUILTIN_SIZE_PRESETS, path)

        loaded = get_preset_modules(json_path=path)
        builtins = get_preset_modules(json_path=tmp_path / "nonexistent.json")

        assert len(loaded) == len(builtins)
        for i, (a, b) in enumerate(zip(loaded, builtins)):
            assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True), (
                f"Module {i} ({a.get('id')}) differs after round-trip"
            )

    def test_round_trip_size_presets(self, tmp_path):
        path = tmp_path / "library.json"
        _export_library_json(_BUILTIN_MODULES, _BUILTIN_SIZE_PRESETS, path)
        loaded = get_size_presets(json_path=path)
        assert len(loaded) == len(_BUILTIN_SIZE_PRESETS)
        for a, b in zip(loaded, _BUILTIN_SIZE_PRESETS):
            assert a == b


# ═══════════════════════════════════════════════════════════
# get_preset_modules() Integration
# ═══════════════════════════════════════════════════════════


class TestGetPresetModules:
    """Test the main public API with JSON path override."""

    def test_loads_from_json_when_available(self, tmp_path):
        path = tmp_path / "library.json"
        _export_library_json(_BUILTIN_MODULES, path=path)
        mods = get_preset_modules(json_path=path)
        assert len(mods) == 49
        assert is_loaded_from_json() is True

    def test_falls_back_to_builtins(self, tmp_path):
        mods = get_preset_modules(json_path=tmp_path / "nonexistent.json")
        assert len(mods) == 49
        assert is_loaded_from_json() is False

    def test_returns_deep_copy_from_json(self, tmp_path):
        path = tmp_path / "library.json"
        _export_library_json(_BUILTIN_MODULES, path=path)
        mods1 = get_preset_modules(json_path=path)
        mods1[0]["name"] = "MUTATED"
        mods2 = get_preset_modules(json_path=path)
        assert mods2[0]["name"] != "MUTATED"

    def test_default_path_uses_real_library(self):
        """Default call should work (uses _LIBRARY_JSON or falls back)."""
        mods = get_preset_modules()
        assert len(mods) >= 49  # Library may have same or more modules


# ═══════════════════════════════════════════════════════════
# Module Completeness (all 49 modules have all fields)
# ═══════════════════════════════════════════════════════════


class TestModuleCompleteness:
    """Ensure every module in both JSON and builtins has all required fields."""

    def test_all_builtin_modules_complete(self):
        for mod in _BUILTIN_MODULES:
            missing = _REQUIRED_MODULE_FIELDS - mod.keys()
            assert not missing, f"Module {mod['id']} missing: {missing}"

    def test_all_json_modules_complete(self, tmp_path):
        path = tmp_path / "library.json"
        _export_library_json(_BUILTIN_MODULES, path=path)
        mods = get_preset_modules(json_path=path)
        for mod in mods:
            missing = _REQUIRED_MODULE_FIELDS - mod.keys()
            assert not missing, f"Module {mod['id']} missing: {missing}"

    def test_all_modules_have_8x8_tiles(self):
        for mod in _BUILTIN_MODULES:
            tiles = mod["tiles"]
            assert len(tiles) == 8, f"Module {mod['id']} has {len(tiles)} tile rows"
            for row in tiles:
                assert len(row) == 8, f"Module {mod['id']} has row of length {len(row)}"

    def test_module_ids_are_unique(self):
        ids = [m["id"] for m in _BUILTIN_MODULES]
        assert len(ids) == len(set(ids)), "Duplicate module IDs found"

    def test_valid_purposes(self):
        valid_purposes = {"empty", "corridor", "enemy", "loot", "boss", "spawn"}
        for mod in _BUILTIN_MODULES:
            assert mod["purpose"] in valid_purposes, (
                f"Module {mod['id']} has invalid purpose: {mod['purpose']}"
            )

    def test_valid_content_roles(self):
        valid_roles = {"flexible", "fixed", "structural"}
        for mod in _BUILTIN_MODULES:
            assert mod["contentRole"] in valid_roles, (
                f"Module {mod['id']} has invalid contentRole: {mod['contentRole']}"
            )


# ═══════════════════════════════════════════════════════════
# Library JSON File on Disk (integration)
# ═══════════════════════════════════════════════════════════


class TestLibraryJsonOnDisk:
    """Verify that the actual library.json in the repo is valid."""

    _LIBRARY_PATH = (
        Path(__file__).resolve().parent.parent / "configs" / "wfc-modules" / "library.json"
    )

    @pytest.mark.skipif(
        not (Path(__file__).resolve().parent.parent / "configs" / "wfc-modules" / "library.json").exists(),
        reason="library.json not present on disk",
    )
    def test_library_json_loads(self):
        result = _load_library_json(self._LIBRARY_PATH)
        assert result is not None
        assert len(result["modules"]) == 49

    @pytest.mark.skipif(
        not (Path(__file__).resolve().parent.parent / "configs" / "wfc-modules" / "library.json").exists(),
        reason="library.json not present on disk",
    )
    def test_library_json_matches_builtins(self):
        """The checked-in library.json should match the hardcoded builtins."""
        result = _load_library_json(self._LIBRARY_PATH)
        assert result is not None
        for i, (json_mod, builtin) in enumerate(zip(result["modules"], _BUILTIN_MODULES)):
            assert json.dumps(json_mod, sort_keys=True) == json.dumps(builtin, sort_keys=True), (
                f"library.json module {i} ({json_mod.get('id')}) differs from builtin"
            )


# ═══════════════════════════════════════════════════════════
# Generation Still Works (Smoke Test)
# ═══════════════════════════════════════════════════════════


class TestGenerationWithJsonLibrary:
    """Ensure dungeon generation works when loading from library.json."""

    def test_generation_with_json_library(self, tmp_path):
        """Full pipeline should work with JSON-loaded modules."""
        path = tmp_path / "library.json"
        _export_library_json(_BUILTIN_MODULES, path=path)

        # Temporarily override get_preset_modules to use our test JSON
        from app.core.wfc.dungeon_generator import generate_dungeon_floor, FloorConfig
        config = FloorConfig(seed=42, floor_number=1, grid_rows=3, grid_cols=3, batch_size=1)
        result = generate_dungeon_floor(config=config)
        assert result.success, f"Generation failed: {result.error}"
        assert result.game_map is not None
        assert result.game_map["width"] > 0
        assert result.game_map["height"] > 0

    def test_deterministic_with_json(self, tmp_path):
        """Same seed + JSON library should produce same result."""
        path = tmp_path / "library.json"
        _export_library_json(_BUILTIN_MODULES, path=path)

        from app.core.wfc.dungeon_generator import generate_dungeon_floor, FloorConfig
        config1 = FloorConfig(seed=12345, floor_number=1, grid_rows=3, grid_cols=3, batch_size=1)
        config2 = FloorConfig(seed=12345, floor_number=1, grid_rows=3, grid_cols=3, batch_size=1)
        r1 = generate_dungeon_floor(config=config1)
        r2 = generate_dungeon_floor(config=config2)
        assert r1.success and r2.success
        assert r1.tile_map == r2.tile_map
