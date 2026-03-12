# Audio Assets Directory

Place audio files here, organized by category. These are served statically by Vite at the root URL.

## Expected Structure

```
audio/
├── combat/         # Melee hits, ranged impacts, death sounds
├── skills/         # Per-skill cast sounds (magic, holy, dark, etc.)
├── environment/    # Doors, chests, portals, floor transitions
├── ui/             # Button clicks, menu sounds, equip/unequip
├── ambient/        # Looping background tracks (dungeon, town, arena)
└── events/         # Wave clear fanfare, match start/end stings
```

## Supported Formats

- `.wav` — Best quality, larger files (recommended for short SFX)
- `.ogg` — Good quality, smaller files (recommended for ambient loops)
- `.mp3` — Widest compatibility fallback

## How to Add a Sound

1. Place the file in the appropriate category folder
2. Edit `audio-effects.json` (in `client/public/`):
   - Add a `key → path` entry to `_soundFiles`
   - Reference the key in `combat`, `skills`, `environment`, etc.
3. The AudioManager preloads everything listed in `_soundFiles` on init
