"""
JSON file-based persistence for player profiles.

Phase 4E-1: Saves/loads PlayerProfile to/from disk as JSON files.
Each player gets their own file: server/data/players/{username}.json

Designed to be simple and upgradeable to a real DB later.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from app.models.profile import PlayerProfile, STARTING_GOLD

logger = logging.getLogger(__name__)

# ---------- Storage Directory ----------

_data_dir = Path(__file__).resolve().parent.parent.parent / "data" / "players"


def get_data_dir() -> Path:
    """Return the player data directory, creating it if needed."""
    _data_dir.mkdir(parents=True, exist_ok=True)
    return _data_dir


def _profile_path(username: str) -> Path:
    """Get the file path for a player's profile."""
    # Sanitize username for filesystem safety (alphanumeric + underscores only)
    safe_name = "".join(c if c.isalnum() or c == "_" else "_" for c in username)
    return get_data_dir() / f"{safe_name}.json"


# ---------- Core CRUD ----------

def save_profile(profile: PlayerProfile) -> bool:
    """Save a player profile to disk atomically.

    Writes to a temp file first, then renames to avoid corruption.
    Returns True on success, False on failure.
    """
    filepath = _profile_path(profile.username)
    temp_path = filepath.with_suffix(".tmp")

    try:
        data = profile.model_dump(mode="json")
        with open(temp_path, "w") as f:
            json.dump(data, f, indent=2)
        # Atomic rename (on Windows this replaces if exists)
        temp_path.replace(filepath)
        return True
    except Exception as e:
        logger.error(f"Failed to save profile for '{profile.username}': {e}")
        # Clean up temp file if it exists
        if temp_path.exists():
            try:
                temp_path.unlink()
            except OSError:
                pass
        return False


def load_profile(username: str) -> PlayerProfile | None:
    """Load a player profile from disk.

    Returns None if the file doesn't exist.
    Raises no exceptions — corrupt files are handled gracefully.
    """
    filepath = _profile_path(username)
    if not filepath.exists():
        return None

    try:
        with open(filepath, "r") as f:
            data = json.load(f)
        return PlayerProfile(**data)
    except (json.JSONDecodeError, Exception) as e:
        logger.warning(
            f"Corrupt profile file for '{username}' — creating fresh profile. Error: {e}"
        )
        return None


def create_default_profile(username: str) -> PlayerProfile:
    """Create a new default profile for a first-time player.

    Starts with STARTING_GOLD, empty hero roster, empty tavern.
    Automatically saves to disk.
    """
    profile = PlayerProfile(
        username=username,
        gold=STARTING_GOLD,
    )
    save_profile(profile)
    return profile


def load_or_create_profile(username: str) -> PlayerProfile:
    """Load an existing profile or create a new one if it doesn't exist.

    This is the primary entry point — auto-creates on first access.
    """
    profile = load_profile(username)
    if profile is None:
        profile = create_default_profile(username)
    return profile


def delete_profile(username: str) -> bool:
    """Delete a player's profile file. Returns True if deleted, False if not found."""
    filepath = _profile_path(username)
    if filepath.exists():
        try:
            filepath.unlink()
            return True
        except OSError as e:
            logger.error(f"Failed to delete profile for '{username}': {e}")
            return False
    return False


def list_profiles() -> list[str]:
    """List all saved player usernames (from filenames)."""
    data_dir = get_data_dir()
    return [f.stem for f in data_dir.glob("*.json")]
