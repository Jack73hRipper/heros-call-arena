# Pending Changes

> **Purpose:** AI agents and developers log changes here as they work.  
> When it's time to publish, clear this file after transferring entries  
> into `build/patch-notes.md` and `docs/changelog.md`.

---

## Unreleased

### Bug Fixes

- **Town Hub hero portraits missing** — `HeroSprite.jsx` used a hardcoded absolute path `url(/spritesheet.png)` for the CSS `backgroundImage`. Under Electron's `file://` protocol this resolved to the filesystem root instead of the app's `dist/` folder. Fixed to use `import.meta.env.BASE_URL` like all other asset paths. *(File: `client/src/components/TownHub/HeroSprite.jsx`)*

### New Features

*(none yet)*

### Balance Changes

*(none yet)*

### Known Issues

- Lobby chat between connected players not yet working — investigation in progress.
